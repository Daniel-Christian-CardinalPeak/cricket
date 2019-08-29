import datetime
import os
import re
import sys
import time

from cricket.events import debug
from cricket.model import TestSuite, TestModule, TestCase, TestMethod


class PyTestTestSuite(TestSuite):
    # on Windows, pytest discover returns unix style paths.  Match either for split
    SPLIT_RE = re.compile(r'[/\\]')

    def __init__(self, options=None):
        super(PyTestTestSuite, self).__init__() 
        if options:
            self.cli_args = {
                "log-cli-level" : options.log_cli_level,
                "junit-xml" : options.junit_xml,
            }                       # our command line options
        else:
            self.cli_args = {}

        # Don't assume commandline pytest is right one
        # Always use the one in current python, disable capture, and preload our plugin
        self._pytest_exec = [sys.executable, '-m', 'pytest',
                             '--capture=no', '-p', 'pytest_cricket']

    @classmethod
    def add_arguments(cls, parser):
        """Add test system specific settings to the argument parser.
        """
        # TODO: general way to add pytest arguments.  We do key ones here
        parser.add_argument('--log-cli-level', default="", action="store",
                            help="Output logging level: debug, info, warning, error")
        parser.add_argument('--junit-xml', default="", action="store",
                            help="Create junit-xml style report file at given path.")

    def discover_commandline(self):
        "Command line: Discover all available tests in a project."
        return self._pytest_exec + ['--cricket', 'discover']

    def execute_commandline(self, labels):
        "Return the command line to execute the specified test labels"
        args = self._pytest_exec + ['--cricket', 'execute']

        debug("cli_args: %r", self.cli_args)
        for aa in self.cli_args:
            value = self.cli_args[aa]
            if value:
                if aa == "junit-xml":
                    jpath = fix_file_path(self.cli_args["junit-xml"])  # fix slashes and timestamps
                    jdir = os.path.dirname(jpath)
                    if not os.path.exists(jdir):  # create directory if needed
                        os.makedirs(jdir)
                    value = jpath

                args.extend(['--'+aa, value])

        # TODO: need way to configure directories to run coverage against and other arguments
        # Breaks executor parsing
        # if self.coverage:
        #     args.append('--cov=')  # coverage over all directories

        if labels:
            args.extend(labels)

        return args

    def split_test_id(self, test_id):
        """Split label string into levels.

        Returns list of (class, string)

        Examples:
        top_dir/test_gui.py::TestGUIFunction::test_failure_1
        ->
        [(TestModule, "top_dir"),
        (TestModule, "test_gui.py"),
        (TestCase, "TestGUIFunction"),
        (TestMethod, "test_failure_1"), ]

        top_dir/test_gui.py::test_good_1
        ->
        [(TestModule, "top_dir"),
        (TestModule, "test_gui.py"),
        (TestMethod, "test_good_1"), ]
        """
        dirparts = self.SPLIT_RE.split(test_id)

        # all directories become modules
        parts = [
            (TestModule, dirpart)
            for dirpart in dirparts[:-1]
        ]
        #debug("pytest.split_path: dirparts=%r parts=%r", dirparts, parts)  # DEBUG

        # remainder is file, optional test case, and test method
        pathparts = dirparts[-1].split('::')
        if len(pathparts) == 1:
            # this isn't a valid test case, but stay uniform
            parts.extend([
                (TestModule, pathparts[0]),
            ])
        elif len(pathparts) == 2:
            parts.extend([
                (TestModule, pathparts[0]),
                (TestMethod, pathparts[1]),
            ])
        else:
            assert len(pathparts) == 3
            parts.extend([
                (TestModule, pathparts[0]),
                (TestCase, pathparts[1]),
                (TestMethod, pathparts[2]),
            ])

        #debug("pytest.split_path(%r) -> %r", test_id, parts)
        return parts

    def join_path(self, parents, parts):
        """Create a path given the parts."""
        # FIXME: this isn't the inverse of split_test_id
        # we need all the parts and to know what is module and what is within the file
        if isinstance(parts, (list, tuple)):
            part = '::'.join(parts)
        else:
            part = parts

        if parents is None:
            debug("pytest.join_path(None, %r) -> %r", parts, part)
            return part

        if isinstance(parents, (list, tuple)):
            # pytest seems to like /, even on Windows
            parent = '/'.join(parents)
        else:
            parent = parents

        if part:
            ret = '{}::{}'.format(parent, part)
        else:
            ret = parent

        debug("pytest.join_path(%r, %r) -> %r", parents, parts, ret)
        return ret


def fix_file_path(path):
    """Turn a configuration file path into one suitable for the local OS."""

    if not path:                # handle NULL case
        return path

    # Note: this is local timezone, but if your clock is set to UTC, you get that
    now = datetime.datetime.now()
    if "<DATE>" in path:        # insert date as YYMMDD
        path = path.replace("<DATE>", now.strftime("%Y%m%d"))
    elif "<DATETIME>" in path:  # insert datetime as YYMMDD-HHMMSS
        path = path.replace("<DATETIME>", now.strftime("%y%m%d-%H%M%S"))

    if '/' in path and os.sep != '/':  # convert slashes
        path = os.path.join(*path.split('/'))

    #debug("fix_file_path: end: %r", path)
    return path
