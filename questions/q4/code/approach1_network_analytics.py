from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys
from scipy.optimize import linear_sum_assignment

import networkx as nx
import numpy as np
import plotly.graph_objects as go
from rich.console import Console
from rich.table import Table
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from common import (
    ROOT,
    apply_trade_distance,
    validate_graph,
    validate_undirected_consistency,
    node_name_map,
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
        support = np.flatnonzero(counts)
        frequencies = counts[support]
        loglog_slope = float(np.polyfit(np.log(support), np.log(frequencies), 1)[0])
    assortativity = nx.degree_assortativity_coefficient(undirected) if undirected.number_of_edges() else float("nan")
    components = list(nx.connected_components(undirected))
    return {
        "nodes": graph.number_of_nodes(),
        "directed_edges": graph.number_of_edges(),
        "undirected_edges": undirected.number_of_edges(),
        "density": float(nx.density(graph)),
        "directed_density": float(nx.density(graph)),
        "undirected_density": float(nx.density(undirected)),
        "degree_distribution": {str(d): int(n) for d, n in enumerate(np.bincount([v for _, v in undirected.degree()])) if n},
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


def community_summary(undirected: nx.Graph, nodes: list[dict], resolution: float, seed: int = 42) -> dict:
    communities = nx.community.louvain_communities(undirected, weight="weight", resolution=resolution, seed=seed)
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
    old_ids, new_ids = sorted(set(previous.values())), sorted(set(current.values()))
    table = np.array([[sum(previous[n] == a and current[n] == b for n in nodes) for b in new_ids] for a in old_ids])
    row, col = linear_sum_assignment(-table)
    alignment = {new_ids[j]: old_ids[i] for i, j in zip(row, col)}
    next_id = max(old_ids, default=-1) + 1
    for label in new_ids:
        if label not in alignment:
            alignment[label] = next_id
            next_id += 1
    return {
        "previous_communities": len(old_ids), "current_communities": len(new_ids),
        "row_labels": old_ids, "column_labels": new_ids, "contingency": table.tolist(),
        "alignment": alignment,
        "changed_share": float(np.mean([previous[n] != alignment[current[n]] for n in nodes])),
        "ari": float(adjusted_rand_score([previous[n] for n in nodes], [current[n] for n in nodes])),
        "split_previous_labels": [old_ids[i] for i in range(len(old_ids)) if np.count_nonzero(table[i]) > 1],
        "merged_current_labels": [new_ids[j] for j in range(len(new_ids)) if np.count_nonzero(table[:, j]) > 1],
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
    sys.path.insert(0, str(ROOT))
    from data.fetch import verify_snapshots
    verify_snapshots(args.data)
    names = node_name_map(load_nodes(args.data / "node_metadata.csv"))
    nodes = load_nodes(args.data / "node_metadata.csv")
    edges = load_edges(args.data / "trade_flows.csv")
    years = years_in(edges)
    per_year: dict[str, dict] = {}
    community_by_year: dict[int, dict[int, int]] = {}
    for year in years:
        graph = directed_graph(edges, nodes, year, top_k=args.top_k)
        validate_graph(graph)
        apply_trade_distance(graph)
        undirected = undirected_graph(graph)
        validate_graph(undirected)
        validate_undirected_consistency(graph, undirected)
        summary = graph_statistics(graph, undirected)
        summary["mst"] = mst_summary(undirected)
        selected = community_summary(undirected, nodes, args.resolution, args.seed)
        summary["communities"] = {key: value for key, value in selected.items() if key != "labels"}
        summary["resolution_sweep"] = {str(resolution): {key: value for key, value in community_summary(undirected, nodes, resolution, args.seed).items() if key != "labels"} for resolution in resolution_values}
        community_by_year[year] = selected["labels"]
        summary["top_pagerank"] = sorted(nx.pagerank(graph, weight="weight").items(), key=lambda item: item[1], reverse=True)[:5]
        summary["top_betweenness"] = sorted(nx.betweenness_centrality(graph, weight="distance", normalized=True).items(), key=lambda item: item[1], reverse=True)[:5]
        summary["top_weighted_degree"] = sorted(undirected.degree(weight="weight"), key=lambda item: item[1], reverse=True)[:5]
        measures = {"pagerank": nx.pagerank(graph, alpha=.85, weight="weight"),
                    "betweenness": nx.betweenness_centrality(graph, weight="distance"),
                    "weighted_degree": dict(undirected.degree(weight="weight"))}
        summary["centrality_rankings"] = {key: [{"rank": i+1, "node": n, "name": names[n], "value": float(v)} for i, (n, v) in enumerate(sorted(values.items(), key=lambda item: (-item[1], item[0])))] for key, values in measures.items()}
        summary["community_labels"] = selected["labels"]
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
    write_metrics(args.out / "metrics.json", {"question": "q4", "approach": "approach1", "dataset": "trade", "seed": args.seed, "resolution": args.resolution, "resolutions": resolution_values, "top_k": args.top_k, "data": str(args.data)}, metrics, time.perf_counter() - started, {"years": ordered_years})
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
