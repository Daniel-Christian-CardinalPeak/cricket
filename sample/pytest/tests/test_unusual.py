from __future__ import print_function

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

def test_lots_o_output():
    # http://99-bottles-of-beer.net/language-python-808.html
    for quant in range(99, 0, -1):
       if quant > 1:
          print(quant, "bottles of beer on the wall,", quant, "bottles of beer.")
          if quant > 2:
             suffix = str(quant - 1) + " bottles of beer on the wall."
          else:
             suffix = "1 bottle of beer on the wall."
       elif quant == 1:
          print("1 bottle of beer on the wall, 1 bottle of beer.")
          suffix = "no more beer on the wall!"
       print("Take one down, pass it around,", suffix)
       print("")

    print("Remember kids -- always drink responsibly")

def test_mixed_stdout_stderr():
    delay = 0.05
    print("Twinkle, twinkle")
    time.sleep(delay)
    print("Little star", file=sys.stderr)
    time.sleep(delay)
    print("How I wonder")
    time.sleep(delay)
    print("What you are", file=sys.stderr)
    time.sleep(delay)

# TODO: large amount of output
# TODO: stack trace

def slow():
    time.sleep(0.2)

# Create slow tests
for i in range(0, 5):
    locals()['test_slow_{}'.format(i)] = slow
