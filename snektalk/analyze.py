from itertools import count

import pkg_resources
from ptera import op

from .utils import findvar, pastecode


class Viz:
    def __init__(self, probe):
        self.probe = probe

    def __hrepr__(self, H, hrepr):
        from .lib import fill_at

        analyzers = {}

        for entry_point in pkg_resources.iter_entry_points("snektalk.analyzer"):
            analyzers[entry_point.name] = entry_point.load()

        divid = f"$analyze__{next(monitor_count)}"
        anal = Synthesizer(
            self.probe, [a(self.probe) for a in analyzers.values()]
        )

        def process(suggestions):
            contents = H.div["snek-suggestions"](
                [
                    H.div["snek-suggestion"](
                        sugg.description, onclick=sugg.output
                    )
                    for sugg in suggestions
                ]
            )
            fill_at(divid, contents)

        self.probe.pipe(op.map(anal.suggest), op.throttle(1)).subscribe(process)
        return H.div(id=divid)


def viz(probe):
    print(Viz(probe))


class Suggestion:
    def __init__(self, obs, description, output):
        self.obs = obs
        self.description = description
        self.output = output


class Analyzer:
    def __init__(self, obs):
        self.obs = obs

    def suggest(self, data):
        pass


class Synthesizer(Analyzer):
    def __init__(self, obs, analyzers):
        super().__init__(obs)
        self.analyzers = analyzers

    def suggest(self, data):
        suggestions = []
        for analyzer in list(self.analyzers):
            sugg = analyzer.suggest(data)
            if sugg is None:
                self.analyzers.remove(analyzer)
            else:
                suggestions.extend(sugg)
        return suggestions


###########
# Monitor #
###########

monitor_count = count()


class Monitor:
    def __init__(self):
        self.id = f"$monitor__{next(monitor_count)}"

    def update(self, x):
        from .lib import fill_at

        fill_at(self.id, x)

    def __hrepr__(self, H, hrepr):
        return H.div(id=self.id)


def monitor(obs):
    m = Monitor()
    obs.subscribe(m.update)
    return m


class MonitorAnalyzer(Analyzer):
    def __init__(self, obs):
        super().__init__(obs)
        self.suggestions = [
            Suggestion(self.obs, "Monitor", self.onclick),
        ]

    def suggest(self, data=None):
        return self.suggestions

    def onclick(self, _):
        # m = monitor(self.obs.pipe(op.throttle(0.1)))
        # print(m)
        prb = findvar(self.obs, "probe")
        pastecode(
            f"monitor({prb}.pipe(op.throttle(0.1)))",
            {
                "monitor": (monitor, "from snektalk.analyze import monitor"),
                "op": (monitor, "from ptera import op"),
            },
        )


##########
# Putvar #
##########


class PutvarSuggestion:
    def __init__(self, obs, key_name):
        self.obs = obs
        self.key_name = key_name
        self.value = None
        if key_name is None:
            self.description = "Put latest value in a variable"
        else:
            self.description = f"Put latest '{key_name}' in a variable"

    def output(self, _):
        from .utils import pastevar

        pastevar(self.value)


class PutvarAnalyzer(Analyzer):
    def __init__(self, obs):
        super().__init__(obs)
        self.suggestions = {}

    def suggest(self, data=None):
        if not isinstance(data, dict):
            data = {None: data}

        for key_name, value in data.items():
            if key_name not in self.suggestions:
                self.suggestions[key_name] = PutvarSuggestion(
                    self.obs, key_name
                )
            self.suggestions[key_name].value = value

        return list(self.suggestions.values())
