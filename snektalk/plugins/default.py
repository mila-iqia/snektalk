def default_plugin():
    # Register analyzers
    from snektalk import analyze as an

    an.probe_analyzers["monitor"] = an.MonitorAnalyzer
    an.probe_analyzers["putvar"] = an.PutvarAnalyzer
