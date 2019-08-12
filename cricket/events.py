from __future__ import print_function

class EventSource(object):
    """A source of GUI events.

    An event source can receive handlers for events, and
    can emit events.
    """
    _events = {}                # { class : { event : handler } }

    @classmethod
    def bind(cls, event, handler):
        cls._events.setdefault(cls, {}).setdefault(event, []).append(handler)
        debug("bind %r:%r to %r", cls, event, handler)

    def emit(self, event, **data):
        try:
            debug("emit %r:%r to %d", 
                  self.__class__, event, len(self._events[self.__class__][event]))
            for handler in self._events[self.__class__][event]:
                debug("emit %r(%r, **%r)", handler, self, data)
                handler(self, **data)
        except KeyError:
            # No handler registered for event.
            debug("emit %r:%r no receivers", self.__class__, event)
            pass


# TODO: debug support should be in it's own file
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
    print(msg, end=end, flush=True)


def set_debug(enable):
    """Set debug enable and return old value."""
    global _debug_on

    old = _debug_on
    _debug_on = enable

    return old


def is_debug():
    """Return debug enable status."""
    return _debug_on
