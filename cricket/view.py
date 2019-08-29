"""A module containing a visual representation of the testModule.

This is the "View" of the MVC world.
"""
import os
import subprocess
try:
    from Tkinter import *
    from tkFont import *
    from ttk import *
    import tkMessageBox
except ImportError:
    from tkinter import *
    from tkinter.font import *
    from tkinter.ttk import *
    from tkinter import messagebox as tkMessageBox
import webbrowser
from cricket.events import debug, fix_file_path

# Check for the existence of coverage and duvet
try:
    import coverage
    try:
        import duvet
    except ImportError:
        duvet = None
except ImportError:
    coverage = None
    duvet = None

from tkreadonly import ReadOnlyText

from cricket.model import TestMethod, TestCase, TestModule
from cricket.executor import Executor


# Display constants for test status
STATUS = {
    TestMethod.STATUS_PASS: {
        'description': u'Pass',
        'symbol': u'\u25cf',
        'tag': 'pass',
        'color': '#28C025',
    },
    TestMethod.STATUS_SKIP: {
        'description': u'Skipped',
        'symbol': u'S',
        'tag': 'skip',
        'color': '#259EBF'
    },
    TestMethod.STATUS_FAIL: {
        'description': u'Failure',
        'symbol': u'F',
        'tag': 'fail',
        'color': '#E32C2E'
    },
    TestMethod.STATUS_EXPECTED_FAIL: {
        'description': u'Expected\n  failure',
        'symbol': u'X',
        'tag': 'expected',
        'color': '#3C25BF'
    },
    TestMethod.STATUS_UNEXPECTED_SUCCESS: {
        'description': u'Unexpected\n   success',
        'symbol': u'U',
        'tag': 'unexpected',
        'color': '#C82788'
    },
    TestMethod.STATUS_ERROR: {
        'description': 'Error',
        'symbol': u'E',
        'tag': 'error',
        'color': '#E4742C'
    },
}

STATUS_DEFAULT = {
    'description': 'Not\nexecuted',
    'symbol': u'',
    'tag': None,
    'color': '#BFBFBF',
}


class MainWindow(object):
    def __init__(self, root, options=None):
        '''
        -----------------------------------------------------
        | main button toolbar                               |
        -----------------------------------------------------
        |       < ma | in content area >                    |
        |            |                                      |
        |  left      |              right                   |
        |  control   |              details frame           |
        |  tree      |              / output viewer         |
        |  area      |                                      |
        -----------------------------------------------------
        |     status bar area                               |
        -----------------------------------------------------

        '''

        self.options = options  # command line options
        self.executor = None    # Executor object for currently running tests
        self._test_suite = None  # top of test tree
        self._save_selection = None  # save selected test list (tree, selection_list)

        # Root window
        self.root = root
        self._need_update = False  # Set when we want to force a refresh
        self.root.title('Cricket')
        self.root.geometry('1024x768')

        # Prevent the menus from having the empty tearoff entry
        self.root.option_add('*tearOff', FALSE)
        # Catch the close button
        self.root.protocol("WM_DELETE_WINDOW", self.cmd_quit)
        # Catch the "quit" event.
        self.root.createcommand('exit', self.cmd_quit)

        # Setup the menu
        self._setup_menubar()

        # Set up the main content for the window.
        self._setup_button_toolbar()
        self._setup_main_content()
        self._setup_status_bar()

        # Now configure the weights for the root frame
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=0)

        # Set up listeners for runner events.
        Executor.bind('test_status_update', self.on_executorStatusUpdate)
        Executor.bind('test_start', self.on_executorTestStart)
        Executor.bind('test_output_update', self.on_testOutputUpdate)
        Executor.bind('test_end', self.on_executorTestEnd)
        Executor.bind('suite_end', self.on_executorSuiteEnd)
        Executor.bind('suite_error', self.on_executorSuiteError)

        # Now that we've laid out the grid, hide the error and output text
        # until we actually have an error/output to display
        self._hide_test_output()
        self._hide_test_errors()

    ######################################################
    # Internal GUI layout methods.
    ######################################################

    def _setup_menubar(self):
        # Menubar
        self.menubar = Menu(self.root)

        # self.menu_Apple = Menu(self.menubar, name='Apple')
        # self.menubar.add_cascade(menu=self.menu_Apple)

        self.menu_file = Menu(self.menubar)
        self.menubar.add_cascade(menu=self.menu_file, label='File')

        self.menu_test = Menu(self.menubar)
        self.menubar.add_cascade(menu=self.menu_test, label='Test')

        #self.menu_beeware = Menu(self.menubar)
        #self.menubar.add_cascade(menu=self.menu_beeware, label='BeeWare')

        self.menu_help = Menu(self.menubar)
        self.menubar.add_cascade(menu=self.menu_help, label='Help')

        # self.menu_Apple.add_command(label='Test', command=self.cmd_dummy)

        # self.menu_file.add_command(label='New', command=self.cmd_dummy, accelerator="Command-N")
        # self.menu_file.add_command(label='Open...', command=self.cmd_dummy)
        # self.menu_file.add_command(label='Close', command=self.cmd_dummy)
        self.menu_file.add_command(label='Quit', command=self.cmd_quit)

        self.menu_test.add_command(label='Run all', command=self.cmd_run_all)
        self.menu_test.add_command(label='Run selected tests', command=self.cmd_run_selected)
        self.menu_test.add_command(label='Re-run failed tests', command=self.cmd_rerun)

        #self.menu_beeware.add_command(label='Open Duvet...', 
        # command=self.cmd_open_duvet, state=DISABLED if duvet is None else ACTIVE)

        self.menu_help.add_command(label='Open Documentation', command=self.cmd_cricket_docs)
        self.menu_help.add_command(label='Open Cricket project page',
                                   command=self.cmd_cricket_page)
        self.menu_help.add_command(label='Open Cricket on GitHub',
                                   command=self.cmd_cricket_github)
        #self.menu_help.add_command(label='Open BeeWare project page', 
        #command=self.cmd_beeware_page)

        # last step - configure the menubar
        self.root['menu'] = self.menubar

    def _setup_button_toolbar(self):
        '''
        The button toolbar runs as a horizontal area at the top of the GUI.
        It is a persistent GUI component
        '''

        # Main toolbar
        self.toolbar = Frame(self.root)
        self.toolbar.grid(column=0, row=0, sticky=(W, E))

        # Buttons on the toolbar
        self.stop_button = Button(self.toolbar, text='Stop', command=self.cmd_stop, state=DISABLED)
        self.stop_button.grid(column=0, row=0)

        self.run_all_button = Button(self.toolbar, text='Run all', command=self.cmd_run_all)
        self.run_all_button.grid(column=1, row=0)

        self.run_selected_button = Button(self.toolbar, text='Run selected',
                                          command=self.cmd_run_selected,
                                          state=DISABLED)
        self.run_selected_button.grid(column=2, row=0)

        self.rerun_button = Button(self.toolbar, text='Re-run', command=self.cmd_rerun, state=DISABLED)
        self.rerun_button.grid(column=3, row=0)

        self.coverage = StringVar()
        self.coverage_button = Button(self.toolbar, text='Coverage report', command=self.cmd_show_cov, state=DISABLED)
        self.coverage_button.grid(column=4, row=0)
        self.coverage_checkbox = Checkbutton(self.toolbar,
                                             text='Generate coverage',
                                             command=self.on_coverageChange,
                                             variable=self.coverage)
        self.coverage_checkbox.grid(column=5, row=0)

        # If coverage is available, enable it by default.
        # Otherwise, disable the widget
        if coverage:
            self.coverage.set('1')
        else:
            self.coverage.set('0')
            self.coverage_checkbox.configure(state=DISABLED)

        self.toolbar.columnconfigure(0, weight=0)
        self.toolbar.rowconfigure(0, weight=1)

    def _setup_main_content(self):
        '''
        Sets up the main content area. It is a persistent GUI component
        '''

        # Main content area
        self.content = PanedWindow(self.root, orient=HORIZONTAL)
        self.content.grid(column=0, row=1, sticky=(N, S, E, W))

        # Create the tree/control area on the left frame
        self._setup_left_frame()
        self._setup_all_tests_tree()
        self._setup_problem_tests_tree()

        # Create the output/viewer area on the right frame
        self._setup_right_frame()

        # Set up weights for the left frame's content
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.content.pane(0, weight=1)
        self.content.pane(1, weight=2)

    def _setup_left_frame(self):
        '''
        The left frame mostly consists of the tree widget
        '''

        # The left-hand side frame on the main content area
        # The tabs for the two trees
        self.tree_notebook = Notebook(self.content, padding=(0, 5, 0, 5))
        self.content.add(self.tree_notebook)

    def _setup_all_tests_tree(self):
        # The tree for all tests
        self.all_tests_tree_frame = Frame(self.content)
        self.all_tests_tree_frame.grid(column=0, row=0, sticky=(N, S, E, W))
        self.tree_notebook.add(self.all_tests_tree_frame, text='All tests')

        self.all_tests_tree = Treeview(self.all_tests_tree_frame)
        self.all_tests_tree.grid(column=0, row=0, sticky=(N, S, E, W))

        # Set up the tag colors for tree nodes.
        for status, config in STATUS.items():
            self.all_tests_tree.tag_configure(config['tag'], foreground=config['color'])
        self.all_tests_tree.tag_configure('inactive', foreground='lightgray')

        # Listen for button clicks on tree nodes
        self.all_tests_tree.tag_bind('TestModule', '<Double-Button-1>', self.on_testModuleClicked)
        self.all_tests_tree.tag_bind('TestCase', '<Double-Button-1>', self.on_testCaseClicked)
        self.all_tests_tree.tag_bind('TestMethod', '<Double-Button-1>', self.on_testMethodClicked)

        self.all_tests_tree.tag_bind('TestModule', '<<TreeviewSelect>>', self.on_testModuleSelected)
        self.all_tests_tree.tag_bind('TestCase', '<<TreeviewSelect>>', self.on_testCaseSelected)
        self.all_tests_tree.tag_bind('TestMethod', '<<TreeviewSelect>>', self.on_testMethodSelected)

        # The tree's vertical scrollbar
        self.all_tests_tree_scrollbar = Scrollbar(self.all_tests_tree_frame, orient=VERTICAL)
        self.all_tests_tree_scrollbar.grid(column=1, row=0, sticky=(N, S))

        # Tie the scrollbar to the text views, and the text views
        # to each other.
        self.all_tests_tree.config(yscrollcommand=self.all_tests_tree_scrollbar.set)
        self.all_tests_tree_scrollbar.config(command=self.all_tests_tree.yview)

        # Setup weights for the "All Tests" tree
        self.all_tests_tree_frame.columnconfigure(0, weight=1)
        self.all_tests_tree_frame.columnconfigure(1, weight=0)
        self.all_tests_tree_frame.rowconfigure(0, weight=1)

    def _setup_problem_tests_tree(self):
        # The tree for problem tests
        self.problem_tests_tree_frame = Frame(self.content)
        self.problem_tests_tree_frame.grid(column=0, row=0, sticky=(N, S, E, W))
        self.tree_notebook.add(self.problem_tests_tree_frame, text='Problems')

        self.problem_tests_tree = Treeview(self.problem_tests_tree_frame)
        self.problem_tests_tree.grid(column=0, row=0, sticky=(N, S, E, W))

        # Set up the tag colors for tree nodes.
        for status, config in STATUS.items():
            self.problem_tests_tree.tag_configure(config['tag'], foreground=config['color'])
        self.problem_tests_tree.tag_configure('inactive', foreground='lightgray')

        # Problem tree only deals with selection, not clicks.
        self.problem_tests_tree.tag_bind('TestModule', '<<TreeviewSelect>>', self.on_testModuleSelected)
        self.problem_tests_tree.tag_bind('TestCase', '<<TreeviewSelect>>', self.on_testCaseSelected)
        self.problem_tests_tree.tag_bind('TestMethod', '<<TreeviewSelect>>', self.on_testMethodSelected)

        # The tree's vertical scrollbar
        self.problem_tests_tree_scrollbar = Scrollbar(self.problem_tests_tree_frame, orient=VERTICAL)
        self.problem_tests_tree_scrollbar.grid(column=1, row=0, sticky=(N, S))

        # Tie the scrollbar to the text views, and the text views
        # to each other.
        self.problem_tests_tree.config(yscrollcommand=self.problem_tests_tree_scrollbar.set)
        self.problem_tests_tree_scrollbar.config(command=self.all_tests_tree.yview)

        # Setup weights for the problems tree
        self.problem_tests_tree_frame.columnconfigure(0, weight=1)
        self.problem_tests_tree_frame.columnconfigure(1, weight=0)
        self.problem_tests_tree_frame.rowconfigure(0, weight=1)

    def _setup_right_frame(self):
        '''
        The right frame is basically the "output viewer" space
        '''

        # The right-hand side frame on the main content area
        self.details_frame = Frame(self.content)
        self.details_frame.grid(column=0, row=0, sticky=(N, S, E, W))
        self.content.add(self.details_frame)

        # Set up the content in the details panel
        # Test Name
        self.name_label = Label(self.details_frame, text='Name:')
        self.name_label.grid(column=0, row=0, pady=5, sticky=(E,))

        self.name = StringVar()
        self.name_widget = Entry(self.details_frame, textvariable=self.name)
        self.name_widget.configure(state='readonly')
        self.name_widget.grid(column=1, row=0, pady=5, sticky=(W, E))

        # Test status
        self.test_status = StringVar()
        self.test_status_widget = Label(self.details_frame, textvariable=self.test_status, width=1, anchor=CENTER)
        f = Font(font=self.test_status_widget['font'])
        f['weight'] = 'bold'
        f['size'] = 50
        self.test_status_widget.config(font=f)
        self.test_status_widget.grid(column=2, row=0, padx=15, pady=5, rowspan=2, sticky=(N, W, E, S))

        # Test duration
        self.duration_label = Label(self.details_frame, text='Duration:')
        self.duration_label.grid(column=0, row=1, pady=5, sticky=(E,))

        self.duration = StringVar()
        self.duration_widget = Entry(self.details_frame, textvariable=self.duration)
        self.duration_widget.grid(column=1, row=1, pady=5, sticky=(E, W,))

        # Test description
        self.description_label = Label(self.details_frame, text='Description:')
        self.description_label.grid(column=0, row=2, pady=5, sticky=(N, E,))

        self.description = ReadOnlyText(self.details_frame, width=80, height=4)
        self.description.grid(column=1, row=2, pady=5, columnspan=2, sticky=(N, S, E, W,))

        self.description_scrollbar = Scrollbar(self.details_frame, orient=VERTICAL)
        self.description_scrollbar.grid(column=3, row=2, pady=5, sticky=(N, S))
        self.description.config(yscrollcommand=self.description_scrollbar.set)
        self.description_scrollbar.config(command=self.description.yview)

        # Test output
        self.output_label = Label(self.details_frame, text='Output:')
        self.output_label.grid(column=0, row=3, pady=5, sticky=(N, E,))

        self.output = ReadOnlyText(self.details_frame, width=80, height=4)
        self.output.grid(column=1, row=3, pady=5, columnspan=2, sticky=(N, S, E, W,))

        self.output_scrollbar = Scrollbar(self.details_frame, orient=VERTICAL)
        self.output_scrollbar.grid(column=3, row=3, pady=5, sticky=(N, S))
        self.output.config(yscrollcommand=self.output_scrollbar.set)
        self.output_scrollbar.config(command=self.output.yview)

        # Error message
        self.error_label = Label(self.details_frame, text='Error:')
        self.error_label.grid(column=0, row=4, pady=5, sticky=(N, E,))

        self.error = ReadOnlyText(self.details_frame, width=80)
        self.error.grid(column=1, row=4, pady=5, columnspan=2, sticky=(N, S, E, W))

        self.error_scrollbar = Scrollbar(self.details_frame, orient=VERTICAL)
        self.error_scrollbar.grid(column=3, row=4, pady=5, sticky=(N, S))
        self.error.config(yscrollcommand=self.error_scrollbar.set)
        self.error_scrollbar.config(command=self.error.yview)

        # Set up GUI weights for the details frame
        self.details_frame.columnconfigure(0, weight=0)
        self.details_frame.columnconfigure(1, weight=1)
        self.details_frame.columnconfigure(2, weight=0)
        self.details_frame.columnconfigure(3, weight=0)
        self.details_frame.columnconfigure(4, weight=0)
        self.details_frame.rowconfigure(0, weight=0)
        self.details_frame.rowconfigure(1, weight=0)
        self.details_frame.rowconfigure(2, weight=1)
        self.details_frame.rowconfigure(3, weight=5)
        self.details_frame.rowconfigure(4, weight=10)

    def _setup_status_bar(self):
        # Status bar
        self.statusbar = Frame(self.root)
        self.statusbar.grid(column=0, row=2, sticky=(W, E))

        # Current status
        self.run_status = StringVar()
        self.run_status_label = Label(self.statusbar, textvariable=self.run_status)
        self.run_status_label.grid(column=0, row=0, sticky=(W, E))
        self.run_status.set('Not running')

        # Test result summary
        self.run_summary = StringVar()
        self.run_summary_label = Label(self.statusbar, textvariable=self.run_summary)
        self.run_summary_label.grid(column=1, row=0, sticky=(W, E))
        self.run_summary.set('T:0 P:0 F:0 E:0 X:0 U:0 S:0')

        # Test progress
        self.progress_value = IntVar()
        self.progress = Progressbar(self.statusbar, orient=HORIZONTAL, length=200, mode='determinate', maximum=100, variable=self.progress_value)
        self.progress.grid(column=2, row=0, sticky=(W, E))

        # Main window resize handle
        self.grip = Sizegrip(self.statusbar)
        self.grip.grid(column=3, row=0, sticky=(S, E))

        # Set up weights for status bar frame
        self.statusbar.columnconfigure(0, weight=1)
        self.statusbar.columnconfigure(1, weight=0)
        self.statusbar.columnconfigure(2, weight=0)
        self.statusbar.columnconfigure(3, weight=0)
        self.statusbar.rowconfigure(0, weight=1)

    ######################################################
    # Utility methods for inspecting current GUI state
    ######################################################

    @property
    def current_test_tree(self):
        "Check the tree notebook to return the currently selected tree."
        current_tree_id = self.tree_notebook.select()
        if current_tree_id == self.problem_tests_tree_frame._w:
            return self.problem_tests_tree
        else:
            return self.all_tests_tree

    ######################################################
    # Handlers for setting a new test_suite
    ######################################################

    @property
    def test_suite(self):
        return self._test_suite

    def _add_test_module(self, parentNode, testModule):
        """Recursively walk test modules to build display tree."""
        # Need proper tag to get the right select function
        # We don't handle TestSuite, because it should aways be above this
        # try this:  tag = testModule.__class__.__name__
        if isinstance(testModule, TestModule):
            tag = 'TestModule'
        elif isinstance(testModule, TestCase):
            tag = 'TestCase'
        elif isinstance(testModule, TestMethod):
            tag = 'TestMethod'
        else:
            debug("add_test_module: Unknown testModule: %r", testModule)
            return

        debug("add_test_module: %r %r %r as %r", parentNode, tag, testModule, testModule.name)
        testModule_node = self.all_tests_tree.insert(
            parentNode, 'end', testModule.path,
            text=testModule.name,
            tags=[tag, 'active'],
            open=True)          # always insert a node

        if testModule.can_have_children():  # walk the children
            for subModuleName, subModule in sorted(testModule._child_nodes.items()):
                self._add_test_module(testModule_node, subModule)

    @test_suite.setter
    def test_suite(self, test_suite):
        self._test_suite = test_suite
        debug("view test_suite = %r", test_suite)

        # Get a count of active tests to display in the status bar.
        count, labels = self.test_suite.find_tests(active=True)
        self.run_summary.set('T:%s P:0 F:0 E:0 X:0 U:0 S:0' % count)

        # Populate the initial tree nodes. This is recursive, because
        # the tree could be of arbitrary depth.
        for testModule_name, testModule in sorted(test_suite._child_nodes.items()):
            self._add_test_module('', testModule)

        # Listen for any state changes on nodes in the tree
        TestModule.bind('active', self.on_nodeActive)
        TestCase.bind('active', self.on_nodeActive)
        TestMethod.bind('active', self.on_nodeActive)

        TestModule.bind('inactive', self.on_nodeInactive)
        TestCase.bind('inactive', self.on_nodeInactive)
        TestMethod.bind('inactive', self.on_nodeInactive)

        # Listen for new nodes added to the tree
        TestModule.bind('new', self.on_nodeAdded)
        TestCase.bind('new', self.on_nodeAdded)
        TestMethod.bind('new', self.on_nodeAdded)

        # Listen for any status updates on nodes in the tree.
        TestMethod.bind('status_update', self.on_nodeStatusUpdate)

        # Update the test_suite to make sure coverage status matches the GUI
        self.on_coverageChange()

    ######################################################
    # TK Main loop
    ######################################################

    def mainloop(self):
        self.root.mainloop()

    ######################################################
    # User commands
    ######################################################

    def cmd_quit(self):
        "Command: Quit"
        # If the runner is currently running, kill it.
        self.stop()

        self.root.quit()

    def cmd_stop(self, event=None):
        "Command: The stop button has been pressed"
        self.stop()

    def cmd_run_all(self, event=None):
        "Command: The Run all button has been pressed"
        # If the executor isn't currently running, we can
        # start a test run.
        if not self.executor or not self.executor.is_running:
            self.run(active=True)

    def cmd_run_selected(self, event=None):
        "Command: The 'run selected' button has been pressed"
        # If the executor isn't currently running, we can
        # start a test run.
        if not self.executor or not self.executor.is_running:
            current_tree = self.current_test_tree
            self._save_selection = (current_tree, current_tree.selection())  # save selection
            tests_to_run = set(self._save_selection[1])
            self.run(labels=tests_to_run)

    def cmd_rerun(self, event=None):
        "Command: The run/stop button has been pressed"
        # If the executor isn't currently running, we can
        # start a test run.
        if not self.executor or not self.executor.is_running:
            self.run(status=set(TestMethod.FAILING_STATES))

    def cmd_show_cov(self, event=None):
        pass

    def cmd_open_duvet(self, event=None):
        "Command: Open Duvet"
        try:
            subprocess.Popen('duvet')
        except Exception as e:
            tkMessageBox.showerror(message='Unable to start Duvet: %s' % e)

    def cmd_cricket_page(self):
        "Show the Cricket project page"
        webbrowser.open_new('http://pybee.org/cricket/')

    def cmd_beeware_page(self):
        "Show the Beeware project page"
        webbrowser.open_new('http://pybee.org/')

    def cmd_cricket_github(self):
        "Show the Cricket GitHub repo"
        #webbrowser.open_new('http://github.com/pybee/cricket')
        webbrowser.open_new('http://github.com/Daniel-Christian-CardinalPeak/cricket')

    def cmd_cricket_docs(self):
        "Show the Cricket documentation"
        webbrowser.open_new('https://cricket.readthedocs.io/')

    ######################################################
    # GUI Callbacks
    ######################################################

    def on_testModuleClicked(self, event):
        "Event handler: a module has been clicked in the tree"
        label = event.widget.focus()
        testModule = self.test_suite.get_node_from_label(label)
        debug("testModuleClicked: %r, %r", label, testModule)
        testModule.toggle_active()

    def on_testCaseClicked(self, event):
        "Event handler: a test case has been clicked in the tree"
        label = event.widget.focus()
        testCase = self.test_suite.get_node_from_label(label)
        debug("testCaseClicked: %r, %r", label, testCase)
        testCase.toggle_active()

    def on_testMethodClicked(self, event):
        "Event handler: a test method has been clicked in the tree"
        label = event.widget.focus()
        testMethod = self.test_suite.get_node_from_label(label)
        debug("testMethodClicked: %r, %r", label, testMethod)
        testMethod.toggle_active()

    def on_testModuleSelected(self, event):
        "Event handler: a test module has been selected in the tree"
        self.name.set('')
        self.test_status.set('')

        self.duration.set('')
        self.description.delete('1.0', END)

        self._hide_test_output()
        self._hide_test_errors()

        # update "run selected" button enabled state
        self.set_selected_button_state()

    def on_testCaseSelected(self, event):
        "Event handler: a test case has been selected in the tree"
        self.name.set('')
        self.test_status.set('')

        self.duration.set('')
        self.description.delete('1.0', END)

        self._hide_test_output()
        self._hide_test_errors()

        # update "run selected" button enabled state
        self.set_selected_button_state()

    def on_testMethodSelected(self, event):
        "Event handler: a test case has been selected in the tree"
        if len(event.widget.selection()) == 1:
            label = event.widget.selection()[0]
            debug("testMethodSelected 1: %r", event.widget.selection()[0])
            testMethod = self.test_suite.get_node_from_label(label)

            self.name.set(testMethod.path)

            try:
                if testMethod.description:
                    self.description.delete('1.0', END)
                    self.description.insert('1.0', testMethod.description)
            except AttributeError:  # not a testMethod node
                return

            if testMethod.status != testMethod.STATUS_UNKNOWN:
                config = STATUS.get(testMethod.status, STATUS_DEFAULT)
                self.test_status_widget.config(foreground=config['color'])
                self.test_status.set(config['symbol'])

            # Show output as test is running
            if ((testMethod.status != testMethod.STATUS_UNKNOWN)
                or testMethod.output or testMethod.error):
                # Test has been executed, so show status windows
                if testMethod._duration is not None:
                    self.duration.set('%0.3fs' % testMethod._duration)
                else:
                    self.duration.set('')

                if testMethod.output:
                    self._show_test_output(testMethod.output)
                else:
                    self._hide_test_output()

                if testMethod.error:
                    self._show_test_errors(testMethod.error)
                else:
                    self._hide_test_errors()
            else:               # Nothing to show
                self.duration.set('Not executed')

                self._hide_test_output()
                self._hide_test_errors()

        else:            # Multiple tests selected, hide result fields
            debug("testMethodSelected: %r", event.widget.selection())

            self.name.set('')
            self.test_status.set('')

            self.duration.set('')
            self.description.delete('1.0', END)

            self._hide_test_output()
            self._hide_test_errors()

        # update "run selected" button enabled state
        self.set_selected_button_state()

    def on_nodeAdded(self, node):
        "Event handler: a new node has been added to the tree"
        self.all_tests_tree.insert(
            node.parent.path, 'end', node.path,
            text=node.name,
            tags=[node.__class__.__name__, 'active'],
            open=True
        )

    def on_nodeActive(self, node):
        "Event handler: a node on the tree has been made active"
        self.all_tests_tree.item(node.path, tags=[node.__class__.__name__, 'active'])
        self.all_tests_tree.item(node.path, open=True)

    def on_nodeInactive(self, node):
        "Event handler: a node on the tree has been made inactive"
        self.all_tests_tree.item(node.path, tags=[node.__class__.__name__, 'inactive'])
        self.all_tests_tree.item(node.path, open=False)

    def on_nodeStatusUpdate(self, event, node):
        """Event handler: a node on the tree has received a status update. 
        Handles status_update"""
        self.all_tests_tree.item(node.path, tags=['TestMethod', STATUS[node.status]['tag']])

        if node.status in TestMethod.FAILING_STATES:
            # Test is in a failing state. Make sure it is on the problem tree,
            # with the correct current status.

            debug("nodeStatusUpdate: %r fail", node.path)
            parts = self.test_suite.split_test_id(node.path)
            parentModule = self.test_suite
            for part in parts:  # walk down tree so we can create missing levels
                testModule = parentModule[part[1]]

                if not self.problem_tests_tree.exists(testModule.path):
                    debug("Create problem node %r under %r", testModule, parentModule)
                    parent_path = parentModule.path if parentModule.path else ''
                    self.problem_tests_tree.insert(
                        parent_path, 'end', testModule.path,
                        text=testModule.name,
                        tags=[testModule.__class__.__name__, 'active'],
                        open=True
                    )

                parentModule = testModule

            self.problem_tests_tree.item(node.path, tags=['TestMethod', STATUS[node.status]['tag']])
        else:
            # Test passed; if it's on the problem tree, remove it.
            debug("nodeStatusUpdate: %r pass", node.path)
            if self.problem_tests_tree.exists(node.path):
                self.problem_tests_tree.delete(node.path)

                # Check all parents of this node. Recursively remove
                # any parent has no children as a result of this deletion.
                has_children = False
                node = node._source
                while node.path and not has_children:
                    if not self.problem_tests_tree.get_children(node.path):
                        self.problem_tests_tree.delete(node.path)
                    else:
                        has_children = True
                    node = node._source

    def on_coverageChange(self):
        "Event handler: when the coverage checkbox has been toggled"
        self.test_suite.coverage = self.coverage.get() == '1'

    def on_testProgress(self):
        "Event handler: a periodic update to poll the runner for output, generating GUI updates"
        if self.executor and self.executor.poll():
            self.root.after(50, self.on_testProgress)
            if self._need_update:
                self.root.update()  # force update on rapid changes
                self._need_update = False

    def on_executorStatusUpdate(self, event, update):
        """The executor has some progress to report.  Handles test_status_update"""
        # Update the status line with output that isn't tied to a running test
        self.run_status.set(update)

    def on_executorTestStart(self, event, test_path):
        """The executor has started running a new test.  Handles test_start"""
        # Update status line, and set the tree item to active.
        self.run_status.set('Running %s...' % test_path)
        try:
            self.all_tests_tree.item(test_path, tags=['TestMethod', 'active'])
            self.current_test_tree.selection_set((test_path, ))  # select only current test
            debug("Set selection to: %r", test_path)             # DEBUG
            self._need_update = True  # request a display update
        except TclError:
            debug("INTERNAL ERROR trying to set tags on %r", test_path)

    def on_testOutputUpdate(self, event, test_path, new_text, was_empty):
        """A running test got output.  Handles test_output_update"""
        current_tree = self.current_test_tree
        if ((len(current_tree.selection()) != 1)
            or (current_tree.selection()[0] != test_path)):  # do nothing if not selected
            debug("test_output_update: not selected")        # DEBUG
            return

        if was_empty:
            # trigger selection event to refresh result page, displaying output box
            # In this case, testMethod.output will be used, new_text is ignored
            debug("test_output_update: re-selecting to show output")        # DEBUG
            current_tree.selection_set(current_tree.selection())
        else:
            self.output.insert(END, new_text)  # insert new contents at end
            # TODO: detect if user has changed position and don't scroll
            self.output.see(END)               # scroll to bottom

        self._need_update = True  # request a display update

    def on_executorTestEnd(self, event, test_path, result, remaining_time):
        """The executor has finished running a test. Handles test_end"""
        # Update the progress meter
        self.progress_value.set(self.progress_value.get() + 1)

        self._set_run_summary(remaining_time)  # Update the run summary

        if self.options and self.options.save:  # write output to a file
            testMethod = self.test_suite.get_node_from_label(test_path)

            if testMethod.output:
                fpath = self.options.save
                if '<TESTNAME>' in fpath:
                    fpath = fpath.replace('<TESTNAME>', testMethod._name)
                fpath = fix_file_path(fpath)  # handles DATETIME and slashes
                add2 = os.path.exists(fpath)
                debug("Writing output to %r", fpath)
                with open(fpath, 'a') as fd:
                    if add2:
                        print("================", file=fd)  # TODO: insert result, time, etc
                    fd.write(testMethod.output)

        # If the test that just fininshed is the one (and only one)
        # selected on the tree, update the display.
        current_tree = self.current_test_tree
        if len(current_tree.selection()) == 1:
            # One test selected.
            if current_tree.selection()[0] == test_path:
                # If the test that just finished running is the selected
                # test, force reset the selection, which will generate a
                # selection event, forcing a refresh of the result page.
                debug("on_executorTestEnd: re-selecting to show output")  # DEBUG
                current_tree.selection_set(current_tree.selection())
        else:
            # No or Multiple tests selected
            self.name.set('')
            self.test_status.set('')

            self.duration.set('')
            self.description.delete('1.0', END)

            self._hide_test_output()
            self._hide_test_errors()

    def on_executorSuiteEnd(self, event, error=None):
        """The test suite finished running.  Handles suite_end"""
        # Display the final results
        self.run_status.set('Finished.')

        if error:
            TestErrorsDialog(self.root, error)

        if self.executor.any_failed:
            dialog = tkMessageBox.showerror
        else:
            dialog = tkMessageBox.showinfo

        message = ', '.join(
            '%d %s' % (count, TestMethod.STATUS_LABELS[state])
            for state, count in sorted(self.executor.result_count.items()))

        dialog(message=message or 'No tests were ran')

        self._set_run_summary()  # Reset the run summary

        if self._save_selection:
            self._save_selection[0].selection_set(self._save_selection[1])  # restore selected tests
            self._save_selection = None

        # Reset the buttons
        self.reset_button_states_on_end()

        # Drop the reference to the executor
        self.executor = None

    def on_executorSuiteError(self, event, error):
        """An error occurred running the test suite.  Handles suite_error"""
        # Display the error in a dialog
        self.run_status.set('Error running test suite.')
        FailedTestDialog(self.root, error)

        # Reset the buttons
        self.reset_button_states_on_end()

        # Drop the reference to the executor
        self.executor = None

    def reset_button_states_on_end(self):
        "A test run has ended and we should enable or disable buttons as appropriate."
        self.stop_button.configure(state=DISABLED)
        self.run_all_button.configure(state=NORMAL)
        self.set_selected_button_state()
        if self.executor and self.executor.any_failed:
            self.rerun_button.configure(state=NORMAL)
        else:
            self.rerun_button.configure(state=DISABLED)

    def set_selected_button_state(self):
        if self.executor and self.executor.is_running:
            self.run_selected_button.configure(state=DISABLED)
        elif self.current_test_tree.selection():
            self.run_selected_button.configure(state=NORMAL)
        else:
            self.run_selected_button.configure(state=DISABLED)

    ######################################################
    # GUI utility methods
    ######################################################

    def run(self, active=True, status=None, labels=None):
        """Run the test suite.

        If active=True, only active tests will be run.
        If status is provided, only tests whose most recent run
            status matches the set provided will be executed.
        If labels is provided, only tests with those labels will
            be executed
        """
        count, labels = self.test_suite.find_tests(active=active, status=status, labels=labels)
        #count, labels = self.test_suite.find_tests(active, status, labels)
        self.run_status.set('Running...')
        self.run_summary.set('T:%s P:0 F:0 E:0 X:0 U:0 S:0' % count)

        self.stop_button.configure(state=NORMAL)
        self.run_all_button.configure(state=DISABLED)
        self.run_selected_button.configure(state=DISABLED)
        self.rerun_button.configure(state=DISABLED)

        self.progress['maximum'] = count
        self.progress_value.set(0)

        # Create the runner
        self.executor = Executor(self.test_suite, count, labels)

        # Queue the first progress handling event
        self.root.after(50, self.on_testProgress)

    def stop(self):
        "Stop the test suite."
        if self.executor and self.executor.is_running:
            self.run_status.set('Stopping...')

            self.executor.terminate()
            self.executor = None

            self.run_status.set('Stopped.')

            self.reset_button_states_on_end()

    def _hide_test_output(self):
        "Hide the test output panel on the test results page"
        self.output_label.grid_remove()
        self.output.grid_remove()
        self.output_scrollbar.grid_remove()
        self.details_frame.rowconfigure(3, weight=0)

    def _show_test_output(self, content):
        "Show the test output panel on the test results page"
        self.output.delete('1.0', END)  # clear contents
        self.output.insert('1.0', content)  # insert new contents

        self.output_label.grid()  # enable in window?
        self.output.grid()
        self.output_scrollbar.grid()
        self.details_frame.rowconfigure(3, weight=5)

    def _hide_test_errors(self):
        "Hide the test error panel on the test results page"
        self.error_label.grid_remove()
        self.error.grid_remove()
        self.error_scrollbar.grid_remove()

    def _show_test_errors(self, content):
        "Show the test error panel on the test results page"
        self.error.delete('1.0', END)
        self.error.insert('1.0', content)

        self.error_label.grid()
        self.error.grid()
        self.error_scrollbar.grid()

    def _set_run_summary(self, remaining_time=None):
        """Update run summary with latest details."""
        format_string = \
            'T:%(total)s P:%(pass)s F:%(fail)s E:%(error)s X:%(expected)s U:%(unexpected)s S:%(skip)s'
        data = {
            'total': self.executor.total_count,
            'pass': self.executor.result_count.get(TestMethod.STATUS_PASS, 0),
            'fail': self.executor.result_count.get(TestMethod.STATUS_FAIL, 0),
            'error': self.executor.result_count.get(TestMethod.STATUS_ERROR, 0),
            'expected': self.executor.result_count.get(TestMethod.STATUS_EXPECTED_FAIL, 0),
            'unexpected': self.executor.result_count.get(TestMethod.STATUS_UNEXPECTED_SUCCESS, 0),
            'skip': self.executor.result_count.get(TestMethod.STATUS_SKIP, 0),
        }

        if remaining_time is not None:
            format_string += ', ~%(remaining)s remaining'
            data['remaining'] = remaining_time

        self.run_summary.set(format_string % data)


class StackTraceDialog(Toplevel):
    OK = 1
    CANCEL = 2

    def __init__(self, parent, title, label, trace, button_text='OK',
                 cancel_text='Cancel'):
        '''Show a dialog with a scrollable stack trace.

        Arguments:

            parent -- a parent window (the application window)
            title -- the title for the stack trace window
            label -- the label describing the stack trace
            trace -- the stack trace content to display.
            button_text -- the label for the button text ("OK" by default)
            cancel_text -- the label for the cancel button ("Cancel" by default)
        '''
        Toplevel.__init__(self, parent)

        self.withdraw()  # remain invisible for now

        # If the master is not viewable, don't
        # make the child transient, or else it
        # would be opened withdrawn
        if parent.winfo_viewable():
            self.transient(parent)

        self.title(title)

        self.parent = parent

        self.frame = Frame(self)
        self.frame.grid(column=0, row=0, sticky=(N, S, E, W))

        self.label = Label(self.frame, text=label)
        self.label.grid(column=0, row=0, padx=5, pady=5, sticky=(W, E))

        self.description = ReadOnlyText(self.frame, width=80, height=20)
        self.description.grid(column=0, columnspan=2, row=1, pady=5, sticky=(N, S, E, W,))

        self.description_scrollbar = Scrollbar(self.frame, orient=VERTICAL)
        self.description_scrollbar.grid(column=1, row=1, pady=5, sticky=(N, S, E))
        self.description.config(yscrollcommand=self.description_scrollbar.set)
        self.description_scrollbar.config(command=self.description.yview)

        self.description.insert('1.0', trace)

        if cancel_text is not None:
            self.cancel_button = Button(self.frame, text=cancel_text, command=self.cancel)
            self.cancel_button.grid(column=0, row=2, padx=5, pady=5, sticky=(E,))

        self.ok_button = Button(self.frame, text=button_text, command=self.ok, default=ACTIVE)
        self.ok_button.grid(column=1, row=2, padx=5, pady=5, sticky=(E,))

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=0)

        self.frame.rowconfigure(0, weight=0)
        self.frame.rowconfigure(1, weight=1)
        self.frame.rowconfigure(2, weight=0)

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind('<Return>', self.ok)

        if self.parent is not None:
            self.geometry("+%d+%d" % (parent.winfo_rootx()+50,
                                      parent.winfo_rooty()+50))

        self.deiconify()  # become visible now

        self.ok_button.focus_set()

        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def ok(self, event=None):
        self.withdraw()
        self.update_idletasks()

        if self.parent is not None:
            self.parent.focus_set()
        self.destroy()
        self.status = self.OK

    def cancel(self, event=None):
        self.withdraw()
        self.update_idletasks()

        if self.parent is not None:
            self.parent.focus_set()

        self.destroy()
        self.status = self.CANCEL


class FailedTestDialog(StackTraceDialog):
    def __init__(self, parent, trace):
        '''Report an error when running a test suite.

        Arguments:

            parent -- a parent window (the application window)
            trace -- the stack trace content to display.
        '''
        StackTraceDialog.__init__(
            self,
            parent,
            'Error running test suite',
            'The following stack trace was generated when attempting to run the test suite:',
            trace,
            button_text='OK',
            cancel_text='Quit',
        )

    def cancel(self, event=None):
        StackTraceDialog.cancel(self, event=event)
        self.parent.quit()


class TestErrorsDialog(StackTraceDialog):
    def __init__(self, parent, trace):
        '''Show a dialog with a scrollable list of errors.

        Arguments:

            parent -- a parent window (the application window)
            error -- the error content to display.
        '''
        StackTraceDialog.__init__(
            self,
            parent,
            'Errors during test suite',
            ('The following errors were generated while running the test suite:'),
            trace,
            button_text='OK',
            cancel_text=None,
        )

    def cancel(self, event=None):
        StackTraceDialog.cancel(self, event=event)
        self.parent.quit()


class TestLoadErrorDialog(StackTraceDialog):
    def __init__(self, parent, trace):
        '''Show a dialog with a scrollable stack trace.

        Arguments:

            parent -- a parent window (the application window)
            trace -- the stack trace content to display.
        '''
        StackTraceDialog.__init__(
            self,
            parent,
            'Error discovering test suite',
            ('The following stack trace was generated when attempting to '
             'discover the test suite:'),
            trace,
            button_text='Retry',
            cancel_text='Quit',
        )

    def cancel(self, event=None):
        StackTraceDialog.cancel(self, event=event)
        self.parent.quit()


class IgnorableTestLoadErrorDialog(StackTraceDialog):
    def __init__(self, parent, trace):
        '''Show a dialog with a scrollable stack trace when loading
           tests turned up errors in stderr but they can safely be ignored.

        Arguments:

            parent -- a parent window (the application window)
            trace -- the stack trace content to display.
        '''
        StackTraceDialog.__init__(
            self,
            parent,
            'Error discovering test suite',
            ('The following error where captured during test discovery '
             'but running the tests might still work:'),
            trace,
            button_text='Continue',
            cancel_text='Quit',
        )
