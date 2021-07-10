#############
# Line plot #
#############

import base64
import time
from io import BytesIO

import numpy
from hrepr import H
from PIL import Image
from ptera import op

from snektalk import Interactor, pastecode
from snektalk.analyze import Analyzer, monitor_count, probe_analyzers
from snektalk.lib import fill_at


class Plot(Interactor):
    js_constructor = "Plot"
    js_requires = {"plotly": "https://cdn.plot.ly/plotly-latest.min.js"}
    js_code = """
    class Plot {
        constructor(element, options) {
            this.element = element;
            plotly.newPlot(element, options.data, options.layout);
        }

        react(data, layout) {
            plotly.react(this.element, data, layout);
        }

        extendTraces(new_traces, which) {
            plotly.extendTraces(this.element, new_traces, which);
        }

        addPoint(x, y) {
            this.extendTraces({x: [[x]], y: [[y]]}, [0]);
        }
    }
    """

    def __init__(self, *data, layout=None):
        super().__init__({"data": list(data), "layout": layout or {}})


def plot(probe):
    t0 = time.time()

    def add_point(thing):
        if isinstance(thing, tuple):
            plt.js.addPoint(*thing)
        elif isinstance(thing, dict):
            if len(thing) > 1:
                x = thing.pop("x")
            else:
                x = time.time() - t0
            (y,) = thing.values()
            plt.js.addPoint(float(x), float(y))
        else:
            plt.js.addPoint(time.time() - t0, float(thing))

    probe.subscribe(add_point)
    plt = Plot({"x": [], "y": []})
    print(plt)


class LinePlotSuggestion:
    def __init__(self, obs, key_name):
        self.obs = obs
        self.key_name = key_name
        if key_name is None:
            self.description = "Line plot over time"
        else:
            self.description = f"Line plot '{key_name}' over time"

    def output(self, _):
        pastecode(
            "plot(probe.pipe(op.throttle(0.1)))",
            {
                "plot": (plot, "from demo_analyzers import plot"),
                "op": (op, "from ptera import op"),
            },
        )


class LinePlotAnalyzer(Analyzer):
    def __init__(self, obs):
        super().__init__(obs)
        self.suggestions = {}

    def suggest(self, data):
        key_name = None
        if isinstance(data, dict) and len(data) == 1:
            ((key_name, data),) = data.items()

        try:
            data = float(data)
        except:
            return None

        if key_name not in self.suggestions:
            self.suggestions[key_name] = LinePlotSuggestion(self.obs, key_name)

        return [self.suggestions[key_name]]


#############
# Histogram #
#############


def histo(probe):
    def redraw(thing):
        data = [x.item() for x in thing.flatten() if x]
        plot.js.react([{"x": data, "type": "histogram"}], {})

    probe.subscribe(redraw)
    plot = Plot({"x": [], "type": "histogram"})
    print(plot)


class HistogramSuggestion:
    def __init__(self, obs, key_name):
        self.obs = obs
        self.key_name = key_name
        if key_name is None:
            self.description = "Distribution of values"
        else:
            self.description = f"Distribution of values for '{key_name}'"

    def output(self, _):
        pastecode(
            f'histo(probe.pipe(op.throttle(0.1), op.getitem("{self.key_name}")))',
            {
                "histo": (histo, "from demo_analyzers import histo"),
                "op": (op, "from ptera import op"),
            },
        )


class HistogramAnalyzer(Analyzer):
    def __init__(self, obs):
        super().__init__(obs)
        self.suggestions = {}

    def suggest(self, data):
        key_name = None
        if isinstance(data, dict) and len(data) == 1:
            ((key_name, data),) = data.items()

        if not hasattr(data, "shape") or not data.shape:
            return None

        if key_name not in self.suggestions:
            self.suggestions[key_name] = HistogramSuggestion(self.obs, key_name)

        return [self.suggestions[key_name]]


#########
# Image #
#########


def image(probe, key_name=None):
    if key_name:
        probe = probe.pipe(op.getitem(key_name))

    divid = f"$analyze__{next(monitor_count)}"

    def redraw(arr):
        while len(arr.shape) > 2:
            arr = arr[0]
        arr = arr.detach().numpy()
        arr = (arr - arr.min()) / (arr.max() - arr.min()) * 255
        arr = arr.astype(numpy.uint8)
        img = Image.fromarray(arr, "L")

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        b = base64.b64encode(buffered.getvalue())
        s = b.decode("utf8")
        fill_at(divid, H.img(src=f"data:image/png;base64,{s}"))

    probe.subscribe(redraw)
    print(H.div(id=divid))


class ImageSuggestion:
    def __init__(self, obs, key_name):
        self.obs = obs
        self.key_name = key_name
        if key_name is None:
            self.description = "Image"
        else:
            self.description = f"Image of '{key_name}'"

    def output(self, _):
        pastecode(
            f'image(probe.pipe(op.throttle(0.1)), key_name="{self.key_name}")',
            {
                "image": (image, "from demo_analyzers import image"),
                "op": (op, "from ptera import op"),
            },
        )


class ImageAnalyzer(Analyzer):
    def __init__(self, obs):
        super().__init__(obs)
        self.suggestions = {}

    def suggest(self, data):
        key_name = None
        if isinstance(data, dict) and len(data) == 1:
            ((key_name, data),) = data.items()

        if not hasattr(data, "shape") or len(data.shape) < 2:
            return None

        if key_name not in self.suggestions:
            self.suggestions[key_name] = ImageSuggestion(self.obs, key_name)

        return [self.suggestions[key_name]]


probe_analyzers.update(
    {
        "line": LinePlotAnalyzer,
        "histo": HistogramAnalyzer,
        "image": ImageAnalyzer,
    }
)
