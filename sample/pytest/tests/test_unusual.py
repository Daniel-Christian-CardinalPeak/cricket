import sys
import time


def test_item_output():
    print("Hello?")
    print("More output?")
    print("But this is stderr", file=sys.stderr)
    print("Did you see the stderr thing?")


def test_logging():
    import logging
    print("Did you hear...")
    logging.warning("The sky is falling!")
    print("About that sky thing?")


def test_mixed_stdout_stderr():
    print("Twinkle, twinkle")
    print("Little star", file=sys.stderr)
    print("How I wonder")
    print("What you are", file=sys.stderr)

def slow():
    time.sleep(0.2)

# Create slow tests
for i in range(0, 10):
    locals()['test_slow_{}'.format(i)] = slow
