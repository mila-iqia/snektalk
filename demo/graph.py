from collections import defaultdict


cystyle = [
    {
        "selector": "node",
        "style": {"background-color": "#800", "label": "data(id)"},
    },
    {
        "selector": "edge",
        "style": {
            "width": 3,
            "line-color": "#ccc",
            "target-arrow-color": "#ccc",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
        },
    },
]


cystyle = """
node {
    background-color: #080;
    label: data(id);
}
edge {
    width: 5;
    line-color: #ccc;
    target-arrow-color: #ccc;
    target-arrow-shape: triangle;
    curve-style: bezier;
}
"""


class Graph:
    def __init__(self, edges, on_node=None):
        edges = list(edges)
        self.edges = edges
        self.nodes = {src for src, _ in edges} | {tgt for _, tgt in edges}
        self.pred = defaultdict(set)
        self.succ = defaultdict(set)
        for a, b in edges:
            self.pred[str(b)].add(a)
            self.succ[str(a)].add(b)
        self._on_node = on_node

    def on_node(self, data):
        if not self._on_node:
            return
        x = data["id"]
        data["pred"] = self.pred[x]
        data["succ"] = self.succ[x]
        return self._on_node(data["pred"])

    @classmethod
    def __hrepr_resources__(cls, H):
        return [
            H.javascript(
                src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.17.0/cytoscape.min.js",
                export="cytoscape",
            ),
            H.javascript(
                """
                function make_graph(element, options) {
                    this.cy = cytoscape({
                        container: element,
                        elements: options.data,
                        style: options.style,
                        layout: {name: options.layout}
                    });
                    if (options.on_node) {
                        this.cy.on('click', 'node', function(evt){
                            options.on_node(evt.target.data());
                        });
                    }
                }
                """,
                require="cytoscape",
                export="make_graph",
            ),
        ]

    def __hrepr__(self, H, hrepr):
        width = hrepr.config.graph_width or 500
        height = hrepr.config.graph_height or 500
        style = hrepr.config.graph_style or cystyle
        data = [{"data": {"id": node}} for node in self.nodes]
        data += [
            {"data": {"source": src, "target": tgt}} for src, tgt in self.edges
        ]
        return H.div(
            style=f"width:{width}px;height:{height}px;",
            constructor="make_graph",
            options={"data": data, "style": style, "layout": "cose", "on_node": self.on_node},
        )
