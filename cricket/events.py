from __future__ import print_function

class EventSource(object):
    """A source of GUI events.

    An event source can receive handlers for events, and
    can emit events.
    """
    _events = {}

    @classmethod
    def bind(cls, event, handler):
        cls._events.setdefault(cls, {}).setdefault(event, []).append(handler)

    def emit(self, event, **data):
        try:
            for handler in self._events[self.__class__][event]:
                handler(self, **data)
        except KeyError:
            # No handler registered for event.
            pass


_debug_on = False

def debug(msg, *args, end='\n'):
    """Our simple debug printer.  Styled after log.debug()
    Print msg if debugging is on

    If there are additional arguments, pass those to classic style format first,
    If debugging is off, don't calculate formatted string.

    Arguments:
      msg    String to print.  May contain class style formatting
      *args  Any arguments to string format
      end    Line ending string.  Default is '\n'

    e.g. debug("Read %d", 512)
    """
    if not _debug_on:
        return
    if args:
        msg = msg % args
    print(msg, end=end)


def set_debug(enable):
    """Set debug enable and return old value."""
    global _debug_on

    old = _debug_on
    _debug_on = enable

    return old
