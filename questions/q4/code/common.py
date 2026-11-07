from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Iterable

import networkx as nx
import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def trade_distance(weight: float) -> float:
    weight = float(weight)
    if not np.isfinite(weight) or weight <= 0:
        raise ValueError("Trade distance requires a finite positive weight")
    return 1.0 / np.log1p(weight)


def apply_trade_distance(graph: nx.Graph) -> nx.Graph:
    for _, _, attributes in graph.edges(data=True):
        attributes["distance"] = trade_distance(attributes.get("weight", 0.0))
    return graph


def validate_graph(graph: nx.Graph, *, label: str = "graph") -> dict:
    self_loops = list(nx.selfloop_edges(graph))
    if self_loops:
        raise ValueError(f"{label} contains {len(self_loops)} self-loops")
    invalid: list[str] = []
    for left, right, attributes in graph.edges(data=True):
        weight = attributes.get("weight")
        if weight is None:
            invalid.append(f"({left},{right}) missing weight")
        elif not np.isfinite(float(weight)):
            invalid.append(f"({left},{right}) non-finite weight {weight}")
        elif float(weight) <= 0.0:
            invalid.append(f"({left},{right}) non-positive weight {weight}")
    if invalid:
        preview = ", ".join(invalid[:10])
        raise ValueError(f"{label} has {len(invalid)} invalid edge weights; examples: {preview}")
    return {"nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(), "self_loops": 0, "invalid_weights": 0}


def validate_undirected_consistency(directed: nx.DiGraph, undirected: nx.Graph) -> None:
    expected = undirected_graph(directed)
    if set(expected.nodes) != set(undirected.nodes) or set(map(frozenset, expected.edges)) != set(map(frozenset, undirected.edges)):
        raise ValueError("Undirected projection does not preserve the directed graph nodes and edge union")
    for left, right, attributes in expected.edges(data=True):
        if not np.isclose(attributes["weight"], undirected[left][right].get("weight", np.nan), rtol=1e-12, atol=0):
            raise ValueError(f"Reciprocal trade weights were not summed for ({left},{right})")


def node_name_map(nodes: list[dict]) -> dict[int, str]:
    return {row["node_code"]: row["node_name"] for row in nodes}


def environment_metadata() -> dict:
    import platform
    import sys as _sys
    import os as _os
    info: dict = {
        "python": _sys.version.split()[0],
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "networkx_version": nx.__version__,
        "loky_max_cpu_count": _os.environ.get("LOKY_MAX_CPU_COUNT"),
        "cpu_count": _os.cpu_count(),
    }
    try:
        import torch
        info["torch_version"] = torch.__version__
        info["torch_threads"] = torch.get_num_threads()
    except ImportError:
        info["torch_version"] = None
    try:
        import sklearn
        info["sklearn_version"] = sklearn.__version__
    except ImportError:
        info["sklearn_version"] = None
    info["residual_nondeterminism"] = (
        "All randomness is seeded (seed recorded in params); CPU-only torch/scikit-learn operations are deterministic "
        "for these pinned versions, but BLAS reduction order or parallel scheduling can still produce last-bit float differences."
    )
    return info


def set_seed(seed: int) -> np.random.Generator:
    random.seed(seed)
    np.random.seed(seed)
    return np.random.default_rng(seed)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_nodes(path: Path | None = None) -> list[dict]:
    path = path or ROOT / "data" / "clean" / "node_metadata.csv"
    return [{**row, "node_code": int(row["node_code"]), "is_china": int(row["is_china"])} for row in read_csv(path)]


def load_edges(path: Path | None = None) -> list[dict]:
    path = path or ROOT / "data" / "clean" / "trade_flows.csv"
    return [{
        **row,
        "year": int(row["year"]),
        "reporter_code": int(row["reporter_code"]),
        "partner_code": int(row["partner_code"]),
        "trade_value_usd": float(row["trade_value_usd"]),
    } for row in read_csv(path)]


def years_in(edges: Iterable[dict]) -> list[int]:
    return sorted({row["year"] for row in edges})


def directed_graph(edges: list[dict], nodes: list[dict], year: int, top_k: int | None = None) -> nx.DiGraph:
    graph = nx.DiGraph(year=year)
    graph.add_nodes_from(row["node_code"] for row in nodes)
    year_edges = [row for row in edges if row["year"] == year and row["trade_value_usd"] > 0]
    if top_k is not None:
        selected: list[dict] = []
        reporters = sorted({row["reporter_code"] for row in year_edges})
        for reporter in reporters:
            reporter_edges = [row for row in year_edges if row["reporter_code"] == reporter]
            selected.extend(sorted(reporter_edges, key=lambda row: row["trade_value_usd"], reverse=True)[:top_k])
        year_edges = selected
    for row in year_edges:
        if row["trade_value_usd"] > 0:
            graph.add_edge(row["reporter_code"], row["partner_code"], weight=row["trade_value_usd"])
    return graph


def undirected_graph(graph: nx.DiGraph) -> nx.Graph:
    result = nx.Graph()
    result.add_nodes_from(graph.nodes)
    for left, right, attributes in graph.edges(data=True):
        weight = attributes.get("weight", 0.0)
        if result.has_edge(left, right):
            result[left][right]["weight"] += weight
        else:
            result.add_edge(left, right, weight=weight)
    return result


def community_labels(communities: list[set[int]], nodes: list[int]) -> dict[int, int]:
    labels: dict[int, int] = {}
    for index, community in enumerate(sorted(communities, key=lambda group: min(group) if group else -1)):
        for node in community:
            labels[node] = index
    return {node: labels.get(node, -1) for node in nodes}


def label_vector(labels: dict[int, int], nodes: list[int]) -> list[int]:
    return [labels.get(node, -1) for node in nodes]


def region_labels(nodes: list[dict]) -> dict[int, str]:
    return {row["node_code"]: row["region"] for row in nodes}


def jsonable(value):
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def write_metrics(path: Path, params: dict, metrics: dict, fit_seconds: float, history: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"params": jsonable(params), "metrics": jsonable(metrics), "fit_seconds": float(fit_seconds), "history": jsonable(history)}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def save_plot(figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(str(path), include_plotlyjs=True)


def edge_pairs(graph: nx.Graph) -> list[tuple[int, int]]:
    return [(min(int(left), int(right)), max(int(left), int(right))) for left, right in graph.edges]


def non_edges(graph: nx.Graph) -> list[tuple[int, int]]:
    return [(min(left, right), max(left, right)) for left, right in nx.non_edges(graph)]
