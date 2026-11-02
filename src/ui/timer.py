import objc
from Foundation import NSObject


class _TimerProxy(NSObject):
    """Bridges NSTimer selector-based callback into a plain Python callable."""

    def initWithCallback_(self, callback):
        self = objc.super(_TimerProxy, self).init()
        if self is None:
            return None
        self._callback = callback
        return self

    def fire_(self, timer):
        self._callback()
