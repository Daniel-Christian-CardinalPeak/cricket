'''
The purpose of this module is to set up the Cricket GUI,
load a "project" for discovering and executing tests, and
to initiate the GUI main loop.
'''
from argparse import ArgumentParser
import os
import subprocess
import sys
from cricket.events import debug, set_debug, is_debug

try:
    from Tkinter import *
except ImportError:
    from tkinter import *

from cricket.view import (
    MainWindow,
    TestLoadErrorDialog,
    IgnorableTestLoadErrorDialog
)
from cricket.model import ModelLoadError


def main(Model):
    """Run the main loop of the app.

    Take the project Model as the argument. This model will be
    instantiated as part of the main loop.
    """
    parser = ArgumentParser()

    parser.add_argument("--version", action="store_true",
                        help="Display version number and exit")
    parser.add_argument("--debug", "-d", action="store_true",
                        help="Turn on debug prints (to console).  Also pass python '-u'")
    parser.add_argument("testdir", action="store", default="", nargs='?',
                        help="Test root directory.  Default is current directory")

    Model.add_arguments(parser)
    options = parser.parse_args()

    # Check the shortcut options
    if options.version:
        import cricket
        print(cricket.__version__)
        sys.exit(2)

    if options.debug:
        set_debug(True)

    if options.testdir:
        os.chdir(options.testdir)

    # Set up the root Tk context
    debug("Starting GUI init")
    root = Tk()

    # Construct an empty window
    view = MainWindow(root)

    # Try to load the test_suite. If any error occurs during
    # test_suite load, show an error dialog
    test_suite = None
    while test_suite is None:
        try:
            debug("Discovering initial test_suite")
            test_suite = Model(options)
            test_suite.refresh()
        except ModelLoadError as e:
            # Load failed; destroy the test_suite and show an error dialog.
            # If the user selects cancel, quit.
            debug("Test_Suite initial failed.  Find error dialog and click on quit")
            test_suite = None
            dialog = TestLoadErrorDialog(root, e.trace)
            if dialog.status == dialog.CANCEL:
                sys.exit(1)
    if test_suite.errors:
        dialog = IgnorableTestLoadErrorDialog(root, '\n'.join(test_suite.errors))
        if dialog.status == dialog.CANCEL:
            sys.exit(1)

    # Set the test_suite for the main window.
    # This populates the tree, and sets listeners for
    # future tree modifications.
    view.test_suite = test_suite
    if is_debug():
        count, labels = test_suite.find_tests(allow_all=True)
        debug("Found %d tests:", count)
        debug("%s", '\n'.join(labels))

    # Run the main loop
    try:
        debug("Starting GUI mainloop")
        view.mainloop()
    except KeyboardInterrupt:
        view.on_quit()
