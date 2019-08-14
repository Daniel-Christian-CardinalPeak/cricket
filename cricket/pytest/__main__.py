'''
This is the main entry point for running pytest test suites.
'''
from __future__ import absolute_import
from __future__ import print_function

from cricket.main import main as cricket_main
from cricket.pytest.model import PyTestTestSuite
from cricket.events import debug
import os, sys

# If pytest_cricket isn't on path, thing will fail later
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
os.environ['PYTHONPATH'] = os.pathsep.join(sys.path)  # export
#print("PYTHONPATH=%r" % os.environ['PYTHONPATH'])

def main():
    return cricket_main(PyTestTestSuite)


def run():
    main()


if __name__ == "__main__":
    run()
