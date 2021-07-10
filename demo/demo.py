import random
from dataclasses import dataclass

import demo_analyzers

from graph import Graph
from snektalk import pastevar

random.seed(1234)


def foo(x):
    return x * x


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


@dataclass
class Point:
    x: int
    y: int


if __name__ == "__main__":
    print("Hello there!")
    print(random_colors())
