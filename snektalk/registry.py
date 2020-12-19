import weakref
from collections import deque
from itertools import count

_c = count()


class UNAVAILABLE:
    def __init__(self):
        pass

    def __hrepr__(self, H, hrepr):
        return H.span("<UNAVAILABLE>", style="color:#bbb")


UNAVAILABLE = UNAVAILABLE()


class CallbackRegistry:
    def __init__(self, keep=10000):
        self.keep = keep
        self.id = 0
        self.weak_map = {}
        self.strong_map = {}
        self.strong_ids = deque()

    def cleanup(self, id):
        del self.weak_map[id]
        del self.callbacks[id]

    def register(self, method):
        self.id += 1
        currid = self.id
        try:
            self.weak_map[currid] = weakref.WeakMethod(method)
        except TypeError:
            self.strong_map[currid] = method
            self.strong_ids.append(currid)
            if len(self.strong_ids) > self.keep >= 0:
                rm = self.strong_ids.popleft()
                del self.strong_map[rm]
        return currid

    def resolve(self, id):
        try:
            m = self.weak_map[id]()
        except KeyError:
            m = self.strong_map.get(id, None)

        if m is None:
            raise KeyError(id)

        return m


callback_registry = CallbackRegistry()
