from itertools import count

import pkg_resources
from ptera import op

from .utils import findvar, pastecode


def findprobe(probe):
    if lp := getattr(probe, "_local_probe", None):
        return True, findvar(lp, "lprobe")
    else:
        return False, findvar(probe, "probe")


class Explorer:
    def __init__(self, probe):
        self.probe = probe

    def __hrepr__(self, H, hrepr):
        from .lib import fill_at

        divid = f"$analyze__{next(monitor_count)}"
        anal = Synthesizer(
            self.probe, [a(self.probe) for a in probe_analyzers.values()]
        )

        def makediv(suggestions):
            return (
                H.div["snek-suggestions"](
                    [
                        H.div["snek-suggestion"](
                            sugg.description, onclick=sugg.output
                        )
                        for sugg in suggestions
                    ]
                )
                if suggestions
                else H.div["snek-suggestions"](
                    H.div["snek-nosuggestion"]("Not enough data to analyze")
                )
            )

        def process(suggestions):
            fill_at(divid, makediv(suggestions))

        self.probe.pipe(op.map(anal.suggest), op.throttle(1)).subscribe(process)
        return H.div(makediv([]), id=divid)


def explore(probe):
    print(Explorer(probe))


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
    print(m)


class MonitorAnalyzer(Analyzer):
    def __init__(self, obs):
        super().__init__(obs)
        self.suggestions = [
            Suggestion(self.obs, "Monitor", self.onclick),
        ]

    def suggest(self, data=None):
        return self.suggestions

    def onclick(self, _):
        lcl, prb = findprobe(self.obs)
        reqs = {
            "monitor": (monitor, "from snektalk.analyze import monitor"),
            "op": (monitor, "from ptera import op"),
        }
        if lcl:
            code = f"with {prb} as probe:\n    monitor(probe.pipe(op.throttle(0.1)))"
        else:
            code = f"monitor({prb}.pipe(op.throttle(0.1)))"
        pastecode(code, reqs)


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


probe_analyzers = {}

for entry_point in pkg_resources.iter_entry_points("snektalk.analyzer"):
    probe_analyzers[entry_point.name] = entry_point.load()
