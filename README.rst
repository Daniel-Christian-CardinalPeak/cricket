Cricket-pt
==========

Cricket-pt is a graphical tool that helps you run your test suites.

Cricket-pt is derived from the Cricket in the `BeeWare suite`_. The
project website is `http://pybee.org/cricket`_.

New versions (not yet released 0.3+) of Cricket use the Toga widget
toolkit and support pytest.  Toga isn't currently working on Windows
and Linux.  This version is a backport of pytest to the tkinter based
Cricket.  Getting everything working and some additional features
makes it hard to contribute change upstream.  See Changelog.txt for
details.  The focus is on pytest, so unittest and django may have
experienced some bit rot.  This project can die when Toga and Cricket
are stable on all platforms.


Quickstart
----------

At present, Cricket has support for:

* pytest test suites
* unittest test suites
* Django 1.6+ test suites using unittest2-style discovery (untested)
* Pre-Django 1.6 test suites (untested)

Running pytest::

    $ pip3 install -r requirements.txt
    $ python cricket/pytest/__main__.py

This will pop up a GUI window. Hit "Run all", and watch your test suite
execute. A progress bar is displayed in the bottom right hand corner of
the window, along with an estimate of time remaining.

While the suite is running, you can click on test names to see the output
of that test. If the test passed, it will be displayed in green; other test
results will be shown in other colors.

Cricket-pt should run on Linux, Windows, and MacOS (untested).


Problems under Ubuntu
~~~~~~~~~~~~~~~~~~~~~

Ubuntu's packaging of Python omits the ``idlelib`` library from it's base
package. If you're using Python 3.6 on Ubuntu 18.04, you can install
``idlelib`` by running::

    $ sudo apt-get install python3-tk idle-python3.6

For other versions of Python and Ubuntu, you'll need to adjust this as
appropriate.


Problems under Windows
~~~~~~~~~~~~~~~~~~~~~~

If you're running Cricket in a virtualenv under Windows, you'll need to set an
environment variable so that Cricket can find the TCL graphics library::

    $ set TCL_LIBRARY=c:\Python27\tcl\tcl8.5

You'll need to adjust the exact path to reflect your local Python install.
You may find it helpful to put this line in the ``activate.bat`` script
for your virtual environment so that it is automatically set whenever the
virtualenv is activated.

