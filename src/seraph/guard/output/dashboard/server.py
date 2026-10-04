"""Seraph Guard Web Dashboard — D3.js Causal Graph Visualization.

Launches a local, zero-dependency web server to render the blast radius
as a navigable, Palantir-style force-directed graph.
"""

import http.server
import json
import socketserver
import threading
import webbrowser

from typing import Any, override


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Seraph Guard - Causal Blast Radius Dashboard</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0d1117; color: #c9d1d9; overflow: hidden; }
        #graph { width: 100vw; height: 100vh; }
        .node { cursor: pointer; }
        .link { stroke: #8b949e; stroke-opacity: 0.6; stroke-width: 1.5px; }
        .node text { font-size: 12px; fill: #c9d1d9; pointer-events: none; text-shadow: 0 1px 3px #000; }
        .tooltip { position: absolute; background: #161b22; border: 1px solid #30363d; padding: 10px; border-radius: 6px; font-size: 13px; pointer-events: none; opacity: 0; transition: opacity 0.2s; max-width: 350px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
        .legend { position: absolute; top: 20px; left: 20px; background: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .legend-item { display: flex; align-items: center; margin-bottom: 8px; font-size: 13px; }
        .legend-color { width: 14px; height: 14px; border-radius: 50%; margin-right: 10px; border: 1px solid #fff2; }
        .header { position: absolute; top: 20px; right: 20px; text-align: right; }
        .header h1 { margin: 0; font-size: 24px; color: #58a6ff; }
        .header p { margin: 5px 0 0; font-size: 14px; color: #8b949e; }
        .instructions { position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); background: #161b22cc; padding: 8px 16px; border-radius: 20px; font-size: 12px; color: #8b949e; border: 1px solid #30363d; }
    </style>
</head>
<body>
    <div id="graph"></div>
    <div class="tooltip" id="tooltip"></div>
    <div class="legend">
        <h3 style="margin-top:0; font-size: 14px; color: #58a6ff;">Node Types</h3>
        <div class="legend-item"><div class="legend-color" style="background:#f85149"></div> Critical/High Finding</div>
        <div class="legend-item"><div class="legend-color" style="background:#d29922"></div> Medium/Low Finding</div>
        <div class="legend-item"><div class="legend-color" style="background:#58a6ff"></div> Source File</div>
        <div class="legend-item"><div class="legend-color" style="background:#3fb950"></div> Affected Resource</div>
    </div>
    <div class="header">
        <h1>Seraph Guard</h1>
        <p>Causal Blast Radius Graph</p>
    </div>
    <div class="instructions">Click a node to visualize blast radius ripple • Drag to rearrange • Click background to reset</div>

    <script>
        const width = window.innerWidth;
        const height = window.innerHeight;

        const svg = d3.select("#graph")
            .append("svg")
            .attr("width", width)
            .attr("height", height);

        const tooltip = d3.select("#tooltip");

        const simulation = d3.forceSimulation()
            .force("link", d3.forceLink().id(d => d.id).distance(120))
            .force("charge", d3.forceManyBody().strength(-400))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(35));

        d3.json("/api/graph").then(function(graph) {
            if (!graph.nodes || graph.nodes.length === 0) {
                svg.append("text").attr("x", width/2).attr("y", height/2).attr("text-anchor", "middle").attr("fill", "#8b949e").text("No causal graph data available.");
                return;
            }

            const link = svg.append("g")
                .selectAll("line")
                .data(graph.edges)
                .enter().append("line")
                .attr("class", "link")
                .attr("stroke-width", d => d.relation === 'compromises' || d.relation === 'authenticates' ? 3 : 1.5)
                .attr("stroke-dasharray", d => d.relation === 'found_in' ? '4' : 'none');

            const node = svg.append("g")
                .selectAll("g")
                .data(graph.nodes)
                .enter().append("g")
                .attr("class", "node")
                .call(d3.drag()
                    .on("start", dragstarted)
                    .on("drag", dragged)
                    .on("end", dragended));

            node.append("circle")
                .attr("r", d => {
                    if (d.type === 'finding') return (d.severity === 'critical' || d.severity === 'high') ? 14 : 9;
                    if (d.type === 'resource') return 11;
                    return 7;
                })
                .attr("fill", d => {
                    if (d.type === 'finding') return (d.severity === 'critical' || d.severity === 'high') ? '#f85149' : '#d29922';
                    if (d.type === 'resource') return '#3fb950';
                    return '#58a6ff';
                })
                .attr("stroke", "#0d1117")
                .attr("stroke-width", 2)
                .on("mouseover", function(event, d) {
                    tooltip.style("opacity", 1)
                        .html(`<strong style="color:#58a6ff">${d.type.toUpperCase()}</strong><br><strong>${d.id}</strong><br>${d.title || ''}`)
                        .style("left", (event.pageX + 15) + "px")
                        .style("top", (event.pageY - 15) + "px");
                })
                .on("mouseout", function() { tooltip.style("opacity", 0); })
                .on("click", function(event, d) {
                    event.stopPropagation();
                    const connectedIds = new Set();
                    connectedIds.add(d.id);
                    graph.edges.forEach(e => {
                        const sId = typeof e.source === 'object' ? e.source.id : e.source;
                        const tId = typeof e.target === 'object' ? e.target.id : e.target;
                        if (sId === d.id) connectedIds.add(tId);
                        if (tId === d.id) connectedIds.add(sId);
                    });

                    node.select("circle").transition().duration(300)
                        .attr("opacity", n => connectedIds.has(n.id) ? 1 : 0.15)
                        .attr("stroke", n => n.id === d.id ? "#fff" : "#0d1117")
                        .attr("stroke-width", n => n.id === d.id ? 4 : 2);

                    node.select("text").transition().duration(300)
                        .attr("opacity", n => connectedIds.has(n.id) ? 1 : 0.15);

                    link.transition().duration(300)
                        .attr("stroke-opacity", e => {
                            const sId = typeof e.source === 'object' ? e.source.id : e.source;
                            const tId = typeof e.target === 'object' ? e.target.id : e.target;
                            return (connectedIds.has(sId) && connectedIds.has(tId)) ? 1 : 0.05;
                        })
                        .attr("stroke", e => {
                            const sId = typeof e.source === 'object' ? e.source.id : e.source;
                            const tId = typeof e.target === 'object' ? e.target.id : e.target;
                            return (connectedIds.has(sId) && connectedIds.has(tId)) ? "#f0f6fc" : "#8b949e";
                        });
                });

            node.append("text")
                .attr("dx", 14)
                .attr("dy", ".35em")
                .text(d => d.id.length > 25 ? d.id.substring(0, 22) + '...' : d.id);

            simulation.nodes(graph.nodes).on("tick", ticked);
            simulation.force("link").links(graph.edges);

            function ticked() {
                link
                    .attr("x1", d => d.source.x)
                    .attr("y1", d => d.source.y)
                    .attr("x2", d => d.target.x)
                    .attr("y2", d => d.target.y);

                node
                    .attr("transform", d => `translate(${d.x},${d.y})`);
            }
        }).catch(err => {
            console.error("Failed to load graph data", err);
        });

        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x; d.fy = d.y;
        }
        function dragged(event, d) {
            d.fx = event.x; d.fy = event.y;
        }
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null; d.fy = null;
        }

        svg.on("click", function(event) {
            if (event.target.tagName === "svg") {
                node.select("circle").transition().duration(300)
                    .attr("opacity", 1).attr("stroke", "#0d1117").attr("stroke-width", 2);
                node.select("text").transition().duration(300).attr("opacity", 1);
                link.transition().duration(300).attr("stroke-opacity", 0.6).attr("stroke", "#8b949e");
            }
        });
    </script>
</body>
</html>"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    graph_data: dict[str, Any] = {}

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        elif self.path == "/api/graph":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            # Explicitly omit Access-Control-Allow-Origin to prevent unauthenticated cross-origin access
            self.end_headers()
            self.wfile.write(json.dumps(self.graph_data).encode("utf-8"))
        else:
            self.send_error(404)

    @override
    def log_message(self, format: str, *args: Any) -> None:
        pass  # Suppress standard HTTP logs to keep CLI clean


def launch_web_dashboard(graph_data: dict[str, Any], port: int = 8080) -> None:
    """Starts a local web server and opens the D3.js dashboard in the browser."""
    DashboardHandler.graph_data = graph_data

    # Find an available port
    for p in range(port, port + 100):
        try:
            # Bind strictly to localhost (127.0.0.1) to prevent LAN/internet exposure
            with socketserver.TCPServer(("127.0.0.1", p), DashboardHandler) as httpd:
                url = f"http://127.0.0.1:{p}"

                print(f"\nSeraph Dashboard running at {url}")
                print("Press Ctrl+C to stop the server and return to the CLI.\n")

                # Open browser after a short delay
                threading.Timer(1.0, lambda u=url: webbrowser.open(u)).start()

                try:
                    httpd.serve_forever()
                except KeyboardInterrupt:
                    print("\nDashboard server stopped.")
                break
        except OSError:
            continue
