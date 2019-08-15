import json
import os
import subprocess
import sys
from threading import Thread

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x

from cricket.events import EventSource, debug
from cricket.model import TestMethod
from cricket.pipes import PipedTestResult, PipedTestRunner


def enqueue_output(out, queue):
    """A utility method for consuming piped output from a subprocess.

    Run this as a thread to get non-blocking data from out.

    Reads content from `out` one line at a time, strip trailing
    whitespace, and puts it onto queue for consumption
    """
    for line in iter(out.readline, b''):  # read until EOF
        queue.put(line.rstrip().decode('utf-8'))
    debug("enqueue_output closing %r", out)
    out.close()


def parse_status_and_error(post):
    if post['status'] == 'OK':
        status = TestMethod.STATUS_PASS
        error = None
    elif post['status'] == 's':
        status = TestMethod.STATUS_SKIP
        error = 'Skipped: ' + post.get('error')
    elif post['status'] == 'F':
        status = TestMethod.STATUS_FAIL
        error = post.get('error')
    elif post['status'] == 'x':
        status = TestMethod.STATUS_EXPECTED_FAIL
        error = post.get('error')
    elif post['status'] == 'u':
        status = TestMethod.STATUS_UNEXPECTED_SUCCESS
        error = None
    elif post['status'] == 'E':
        status = TestMethod.STATUS_ERROR
        error = post.get('error')
    else:
        status = 0              # live logging output
        error = None

    return status, error


def format_time(duration):
    """Return a human friendly string from duration (in seconds)."""
    if duration > 4800:
        ret = '%s hours' % int(duration / 2400)
    elif duration > 2400:
        ret = '%s hour' % int(duration / 2400)
    elif duration > 120:
        ret = '%s mins' % int(duration / 60)
    elif duration > 60:
        ret = '%s min' % int(duration / 60)
    else:
        ret = '%ss' % int(duration)

    return ret


class Executor(EventSource):
    SEPARATOR_LINES = (PipedTestResult.RESULT_SEPARATOR,
                       PipedTestRunner.START_TEST_RESULTS,
                       PipedTestRunner.END_TEST_RESULTS)

    "A wrapper around the subprocess that executes tests."
    def __init__(self, test_suite, count, labels):
        self.test_suite = test_suite  # The test tree
        self.total_count = count  # The total count of tests under execution
        self.completed_count = 0  # The count of tests that have been executed.
        self.result_count = {}    # The count of specific test results { status : count }
        self.error_buffer = []    # An accumulator for error output from all the tests.
        self.current_test = None  # The TestMethod object currently under execution.
        self.test_start = None    # Info from test start {path : "", start_time : seconds}
        self.start_time = None    # The timestamp when current_test started

        cmd = self.test_suite.execute_commandline(labels)
        debug("Running(%r): %r", os.getcwd(), cmd)
        self.proc = subprocess.Popen(
            cmd,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            bufsize=1,
            close_fds='posix' in sys.builtin_module_names
        )

        # Piped stdout/stderr reads are blocking; therefore, we need to
        # do all our readline calls in a background thread, and use a
        # queue object to store lines that have been read.
        self.stdout = Queue()
        t = Thread(target=enqueue_output, args=(self.proc.stdout, self.stdout))
        t.daemon = True
        t.start()

        self.stderr = Queue()
        t = Thread(target=enqueue_output, args=(self.proc.stderr, self.stderr))
        t.daemon = True
        t.start()

    @property
    def is_running(self):
        "Return True if this runner currently running."
        return self.proc.poll() is None

    @property
    def any_failed(self):
        return sum(self.result_count.get(state, 0) for state in TestMethod.FAILING_STATES)

    def terminate(self):
        "Stop the executor."
        self.proc.terminate()

    def _read_all_lines(self, q, name=""):
        """Read all the lines in the queue and return as a list."""
        lines = []
        try:
            while True:
                line = q.get(block=False)
                lines.append(line)
                debug("%s%r", name, line)
        except Empty:           # queue is empty
            pass

        return lines

    def poll(self):
        """Poll the runner looking for new test output

        Returns:
          True if polling should continue
          False otherwise
        """

        finished = False  # saw suite end marker
        stopped = False   # process exited (which is bad if not finished)

        # Check to see if the subprocess is still running.
        if self.proc is None:   # process never started (should never happen)
            stopped = True
            debug("Process never started")
        elif self.proc.poll() is not None:  # process has exited
            stopped = True
            debug("Process exited with %d", self.proc.poll())
            # there still might be output in the pipes

        # grab all complete lines so far
        self.error_buffer.extend(self._read_all_lines(self.stderr, name="Stderr: "))
        for line in self._read_all_lines(self.stdout, name="Stdout: "):
            # Start of suite or new test. Next line will be test start
            if line in (PipedTestRunner.START_TEST_RESULTS, PipedTestResult.RESULT_SEPARATOR):
                debug("Test (or suite) start")
                self.current_test = None
                continue

            elif line == PipedTestRunner.END_TEST_RESULTS: # End of test suite execution.
                debug("Test suite finished")
                finished = True
                break

            if line.startswith('\x1b'):  # Some tools insert escape sequences, strip that
                nn = line.find('{')
                if nn > 0:
                    debug("Strip escape from: %r", line)
                    line = line[nn:]

            if line and (line[0] == '{') and (line[-1] == '}'):  # looks like json
                post = None
                try:
                    post = json.loads(line)
                except:         # wasn't valid json, just collect as output
                    debug("Wasn't really Json: %r", line)
                    pass

                if post is not None:
                    if ('start_time' in post) and ('path' in post):  # start of a test
                        if self.current_test is not None:
                            debug("test start didn't follow a test end")
                        self.test_start = post  # save test start info for later
                        self._handle_test_start(post)  # find test and set current_test
                        continue

                    elif ('end_time' in post) and ('status' in post):  # test end
                        # sub test may have multiple results for one start (unittest)
                        if self.current_test is None:
                            debug("test result didn't follow a test start")

                        else:
                            status, error = parse_status_and_error(post)
                            self._handle_test_end(status, error, self.test_start, post)
                            # TODO: aggregate sub test status
                            # we can't clear current_test if there are sub-tests
                        continue
            # if that wasn't json, or json that we recognized, fall through to output capture

            if self.current_test is None: # A test isn't running - send to status update line
                line = line.strip()
                debug("Between test input: %r", line)
                self.emit('test_status_update', update=line)
                continue

            else:
                self.current_test.add_output((line, ))
                # TODO: give new text to display
                # self.emit('test_output_update', self.current_test.path, self.current_test.get_new_output())
                # self.current_test.clear_new_output())
                continue

        if finished:            # saw suite end
            debug("Finished. %d in error buffer", len(self.error_buffer))
            if self.error_buffer:
                # YUCK:  This puts all stderr output into a popup
                self.emit('suite_end', error='\n'.join(self.error_buffer))
            else:
                self.emit('suite_end')
            return False

        elif stopped:  # subprocess has stopped before we saw finished
            debug("Process stopped. %d in error buffer", len(self.error_buffer))
            if self.error_buffer:
                # YUCK?:  This puts all stderr output into a popup ???
                self.emit('suite_error', error='\n'.join(self.error_buffer))
            else:
                self.emit('suite_error', error='Test output ended unexpectedly')
            return False

        return True           # Still running - requeue polling event.

    def _handle_test_start(self, pre):
        """Saw input with no current test.

        Arguments:
          pre  Dictionary with parsed json output from plugin

        Returns True if polling should continue
        """
        debug("Got new test: %r", pre)
        try:
            # No active test; first line tells us which test is running.
            path = None
            if 'path' in pre:
                path = pre['path']
            elif 'description' in pre:  # HACK? sometimes path is missing, but this isn't
                path = pre['description']

            if path is None:
                debug("Could not find path: %r", pre)
                self.current_test = None
                return True

            try:
                self.current_test = self.test_suite.get_node_from_label(path)
            except KeyError:
                # pytest likes to return just the last bit, search for it
                debug("Straight lookup of %r failed", path)
                matches = self.test_suite.find_tests_substring(path)
                if len(matches) == 1:
                    self.current_test = self.test_suite.get_node_from_label(
                        matches[0])
                else:
                    debug("Could not resolve path %r: %r", path, matches)
                    self.current_test = None
                    return True

            self.emit('test_start', test_path=self.current_test.path)

        except ValueError as e:
            debug("ValueError: %r", e)
            self.current_test = None
            self.emit('suite_end')
            return True

        return False

    def _handle_test_end(self, status, error, pre, post):
        """Saw test end, update state."""
        # Increase the count of executed tests
        self.completed_count = self.completed_count + 1

        # Get the start and end times for the test
        start_time = float(pre['start_time'])
        end_time = float(post['end_time'])

        self.current_test.set_result(
            description=post['description'],
            status=status,
            output=post.get('output'),
            error=error,
            duration=end_time - start_time,
        )

        # Work out how long the suite has left to run (approximately)
        if self.start_time is None:
            self.start_time = start_time
        total_duration = end_time - self.start_time
        time_per_test = total_duration / self.completed_count
        remaining_time = (self.total_count - self.completed_count) * time_per_test
        remaining = format_time(remaining_time)

        # Update test result counts
        self.result_count.setdefault(status, 0)
        self.result_count[status] = self.result_count[status] + 1

        # Notify the display to update.
        self.current_test.emit('status_update', node=self.current_test)
        self.emit('test_end', test_path=self.current_test.path,
                  result=status, remaining_time=remaining)
