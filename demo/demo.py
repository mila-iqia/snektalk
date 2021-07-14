import random
from dataclasses import dataclass

import demo_analyzers

from graph import Graph
from snektalk import pastevar


def bisect(arr, key):
    lo = -1
    hi = len(arr)
    while lo < hi - 1:
        mid = lo + (hi - lo) // 2
        if (elem := arr[mid]) > key:
            hi = mid
        else:
            lo = mid
    return lo + 1


def bisect_test(key=1234):
    arr = [random.randint(0, 10000) for i in range(100)]
    arr.sort()
    split = bisect(arr, key)
    return {"less": arr[:split], "more": arr[split:]}


def foo(x):
    return x * x


@dataclass
class Point:
    x: int
    y: int


class Color:
    def __init__(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b

    def __hrepr__(self, H, hrepr):
        size = hrepr.config.swatch_size or 25
        style = f"""
        background: rgb({self.r}, {self.g}, {self.b});
        width: {size}px;
        height: {size}px;
        margin: 3px;
        """
        return H.div(style=style)


def random_colors(n=10):
    results = []
    for i in range(n):
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        color = Color(r, g, b)
        results.append(color)
    return results


if __name__ == "__main__":
    random.seed(1234)
    print("Hello there!")
    print(random_colors(), swatch_size=50)
