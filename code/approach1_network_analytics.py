from __future__ import annotations

import argparse
import time
from pathlib import Path

import networkx as nx
import numpy as np
import plotly.graph_objects as go
from rich.console import Console
from rich.table import Table
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from common import (
    ROOT,
    community_labels,
    directed_graph,
    label_vector,
    load_edges,
    load_nodes,
    region_labels,
    save_plot,
    set_seed,
    undirected_graph,
    write_metrics,
    years_in,
)


def graph_statistics(graph: nx.DiGraph, undirected: nx.Graph) -> dict:
    degree_values = [degree for _, degree in undirected.degree() if degree > 0]
    loglog_slope = None
    if len(degree_values) >= 2 and len(set(degree_values)) > 1:
        counts = np.bincount(degree_values)
        support = np.flatnonzero(counts)[1:]
        frequencies = counts[support]
        loglog_slope = float(np.polyfit(np.log(support), np.log(frequencies), 1)[0])
    assortativity = nx.degree_assortativity_coefficient(undirected) if undirected.number_of_edges() else float("nan")
    components = list(nx.connected_components(undirected))
    return {
        "nodes": graph.number_of_nodes(),
        "directed_edges": graph.number_of_edges(),
        "undirected_edges": undirected.number_of_edges(),
        "density": float(nx.density(graph)),
        "mean_degree": float(np.mean([degree for _, degree in undirected.degree()])),
        "degree_loglog_slope": loglog_slope,
        "assortativity": float(assortativity) if np.isfinite(assortativity) else None,
        "connected_components": len(components),
        "isolated_nodes": int(sum(1 for node in undirected if undirected.degree(node) == 0)),
        "self_loops": int(nx.number_of_selfloops(graph)),
    }


def mst_summary(undirected: nx.Graph) -> dict:
    metric_graph = nx.Graph()
    metric_graph.add_nodes_from(undirected.nodes)
    for left, right, attributes in undirected.edges(data=True):
        metric_graph.add_edge(left, right, distance=1.0 / np.log1p(max(attributes.get("weight", 0.0), 0.0)))
    tree = nx.minimum_spanning_tree(metric_graph, weight="distance")
    return {
        "nodes": tree.number_of_nodes(),
        "edges": tree.number_of_edges(),
        "components": nx.number_connected_components(tree),
        "diameter": int(nx.diameter(tree)) if nx.is_connected(tree) and tree.number_of_nodes() > 1 else None,
        "total_distance": float(sum(attributes["distance"] for _, _, attributes in tree.edges(data=True))),
    }


def community_summary(undirected: nx.Graph, nodes: list[dict], resolution: float) -> dict:
    communities = nx.community.louvain_communities(undirected, weight="weight", resolution=resolution, seed=42)
    labels = community_labels(communities, list(undirected.nodes))
    node_order = list(undirected.nodes)
    region_map = region_labels(nodes)
    regions = {name: index for index, name in enumerate(sorted(set(region_map.values())))}
    region_vector = [regions[region_map.get(node, "Other")] for node in node_order]
    community_vector = label_vector(labels, node_order)
    return {
        "resolution": resolution,
        "community_count": len(communities),
        "modularity": float(nx.community.modularity(undirected, communities, weight="weight")),
        "ari_vs_region_proxy": float(adjusted_rand_score(region_vector, community_vector)),
        "nmi_vs_region_proxy": float(normalized_mutual_info_score(region_vector, community_vector)),
        "labels": labels,
    }


def migration(previous: dict[int, int], current: dict[int, int], nodes: list[int]) -> dict:
    previous_values = [previous[node] for node in nodes]
    current_values = [current[node] for node in nodes]
    mapping = {}
    for current_id in sorted(set(current_values)):
        overlaps = {previous_id: sum(1 for old, new in zip(previous_values, current_values) if new == current_id and old == previous_id) for previous_id in sorted(set(previous_values))}
        mapping[current_id] = max(overlaps, key=overlaps.get)
    aligned_current = [mapping[value] for value in current_values]
    previous_ids = sorted(set(previous_values))
    current_ids = sorted(set(aligned_current))
    matrix = [[sum(1 for old, new in zip(previous_values, aligned_current) if old == old_id and new == new_id) for new_id in current_ids] for old_id in previous_ids]
    return {
        "previous_communities": len(previous_ids),
        "current_communities": len(set(current_values)),
        "changed_share": float(np.mean(np.array(previous_values) != np.array(aligned_current))),
        "ari": float(adjusted_rand_score(previous_values, current_values)),
        "contingency": matrix,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "clean")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "approach1" / "trade")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resolution", type=float, default=1.0)
    parser.add_argument("--resolutions", default="0.5,1.0,1.5")
    parser.add_argument("--top-k", type=int, default=6)
    args = parser.parse_args()
    resolution_values = [float(value) for value in args.resolutions.split(",")]
    set_seed(args.seed)
    started = time.perf_counter()
    nodes = load_nodes(args.data / "node_metadata.csv")
    edges = load_edges(args.data / "trade_flows.csv")
    years = years_in(edges)
    per_year: dict[str, dict] = {}
    community_by_year: dict[int, dict[int, int]] = {}
    for year in years:
        graph = directed_graph(edges, nodes, year, top_k=args.top_k)
        undirected = undirected_graph(graph)
        summary = graph_statistics(graph, undirected)
        summary["mst"] = mst_summary(undirected)
        selected = community_summary(undirected, nodes, args.resolution)
        summary["communities"] = {key: value for key, value in selected.items() if key != "labels"}
        summary["resolution_sweep"] = {str(resolution): {key: value for key, value in community_summary(undirected, nodes, resolution).items() if key != "labels"} for resolution in resolution_values}
        community_by_year[year] = selected["labels"]
        summary["top_pagerank"] = sorted(nx.pagerank(graph, weight="weight").items(), key=lambda item: item[1], reverse=True)[:5]
        summary["top_betweenness"] = sorted(nx.betweenness_centrality(graph, weight="distance", normalized=True).items(), key=lambda item: item[1], reverse=True)[:5]
        summary["top_weighted_degree"] = sorted(undirected.degree(weight="weight"), key=lambda item: item[1], reverse=True)[:5]
        per_year[str(year)] = summary
    migrations = {}
    ordered_years = sorted(community_by_year)
    node_codes = [row["node_code"] for row in nodes]
    for previous_year, current_year in zip(ordered_years, ordered_years[1:]):
        migrations[f"{previous_year}->{current_year}"] = migration(community_by_year[previous_year], community_by_year[current_year], node_codes)
    metrics = {
        "years": ordered_years,
        "construction": {"top_k_exports_per_reporter": args.top_k},
        "per_year": per_year,
        "community_migration": migrations,
        "verification": {
            "self_loops_total": sum(item["self_loops"] for item in per_year.values()),
            "isolated_nodes_reported": True,
            "region_proxy_note": "Trade-network nodes are countries; region is used as a transparent proxy because stock industry labels are not defined for countries.",
        },
    }
    years_for_plot = ordered_years
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=years_for_plot, y=[per_year[str(year)]["communities"]["modularity"] for year in years_for_plot], mode="lines+markers", name="Modularity"))
    figure.add_trace(go.Scatter(x=years_for_plot, y=[per_year[str(year)]["mst"]["diameter"] for year in years_for_plot], mode="lines+markers", name="MST diameter", yaxis="y2"))
    figure.update_layout(title="Trade-network modularity and MST diameter", xaxis_title="Year", yaxis_title="Modularity", yaxis2={"title": "MST diameter", "overlaying": "y", "side": "right"})
    save_plot(figure, args.out / "network_evolution.html")
    write_metrics(args.out / "metrics.json", {"seed": args.seed, "resolution": args.resolution, "resolutions": resolution_values, "top_k": args.top_k, "data": str(args.data)}, metrics, time.perf_counter() - started, {"years": ordered_years})
    table = Table(title="Q4 Approach 1: network analytics")
    table.add_column("Year")
    table.add_column("Nodes")
    table.add_column("Edges")
    table.add_column("Communities")
    table.add_column("Modularity")
    for year in ordered_years:
        item = per_year[str(year)]
        table.add_row(str(year), str(item["nodes"]), str(item["undirected_edges"]), str(item["communities"]["community_count"]), f"{item['communities']['modularity']:.3f}")
    Console().print(table)


if __name__ == "__main__":
    main()
