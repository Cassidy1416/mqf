from __future__ import annotations

import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))
import argparse
import hashlib
import math
import platform
import sys
import time
from pathlib import Path

import networkx as nx
import numpy as np
import plotly.graph_objects as go
import torch
from rich.console import Console
from rich.table import Table
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, average_precision_score, normalized_mutual_info_score, roc_auc_score

from common import (
    ROOT,
    directed_graph,
    edge_pairs,
    environment_metadata,
    load_edges,
    load_nodes,
    non_edges,
    region_labels,
    save_plot,
    set_seed,
    undirected_graph,
    validate_graph,
    validate_undirected_consistency,
    write_metrics,
    years_in,
)


def biased_walk(graph: nx.Graph, start: int, length: int, p: float, q: float, rng: np.random.Generator) -> list[int]:
    walk = [start]
    while len(walk) < length:
        current = walk[-1]
        neighbors = list(graph.neighbors(current))
        if not neighbors:
            break
        if len(walk) == 1:
            weights = np.array([graph[current][neighbor].get("weight", 1.0) for neighbor in neighbors], dtype=float)
        else:
            previous = walk[-2]
            weights = []
            for neighbor in neighbors:
                bias = 1.0 / p if neighbor == previous else (1.0 if graph.has_edge(neighbor, previous) else 1.0 / q)
                weights.append(graph[current][neighbor].get("weight", 1.0) * bias)
            weights = np.asarray(weights, dtype=float)
        weights = np.nan_to_num(weights, nan=0.0, posinf=0.0, neginf=0.0)
        if weights.sum() <= 0:
            weights = np.ones(len(neighbors), dtype=float)
        walk.append(int(rng.choice(neighbors, p=weights / weights.sum())))
    return walk


def walk_pairs(graph: nx.Graph, p: float, q: float, rng: np.random.Generator, walks_per_node: int, walk_length: int, window: int) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    nodes = list(graph.nodes)
    for _ in range(walks_per_node):
        rng.shuffle(nodes)
        for start in nodes:
            walk = biased_walk(graph, int(start), walk_length, p, q, rng)
            for center, node in enumerate(walk):
                for offset in range(1, window + 1):
                    for neighbor_index in (center - offset, center + offset):
                        if 0 <= neighbor_index < len(walk):
                            pairs.append((node, walk[neighbor_index]))
    return pairs


def train_skipgram(pairs: list[tuple[int, int]], nodes: list[int], dimension: int, seed: int, epochs: int, negative_count: int) -> np.ndarray:
    torch.manual_seed(seed)
    index = {node: position for position, node in enumerate(nodes)}
    sources = torch.tensor([index[left] for left, _ in pairs], dtype=torch.long)
    targets = torch.tensor([index[right] for _, right in pairs], dtype=torch.long)
    model = torch.nn.Embedding(len(nodes), dimension)
    context = torch.nn.Embedding(len(nodes), dimension)
    torch.nn.init.xavier_uniform_(model.weight)
    torch.nn.init.zeros_(context.weight)
    optimizer = torch.optim.Adam([*model.parameters(), *context.parameters()], lr=0.03)
    generator = torch.Generator().manual_seed(seed + 17)
    for _ in range(epochs):
        order = torch.randperm(len(sources), generator=generator)
        for batch_start in range(0, len(order), 1024):
            batch = order[batch_start:batch_start + 1024]
            source_vector = model(sources[batch])
            target_vector = context(targets[batch])
            positive_score = (source_vector * target_vector).sum(dim=1)
            negative_targets = torch.randint(len(nodes), (len(batch), negative_count), generator=generator)
            negative_vector = context(negative_targets)
            negative_score = torch.einsum("bd,bnd->bn", source_vector, negative_vector)
            loss = (
                -torch.nn.functional.logsigmoid(positive_score).mean()
                - torch.nn.functional.logsigmoid(-negative_score).sum(dim=1).mean()
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    return model.weight.detach().cpu().numpy()


def build_training_graph(graph: nx.Graph, train_positives: list[tuple[int, int]]) -> nx.Graph:
    training = nx.Graph()
    training.add_nodes_from(graph.nodes)
    for left, right in train_positives:
        training.add_edge(left, right, weight=graph[left][right]["weight"])
    return training


def split_links(graph: nx.Graph, rng: np.random.Generator) -> dict[str, list[tuple[int, int]]]:
    positives = edge_pairs(graph)
    rng.shuffle(positives)
    def split(values: list[tuple[int, int]]) -> tuple[list[tuple[int, int]], list[tuple[int, int]], list[tuple[int, int]]]:
        first = max(1, int(len(values) * 0.8))
        second = max(first + 1, int(len(values) * 0.9))
        return values[:first], values[first:second], values[second:]
    positive_train, positive_validation, positive_test = split(positives)
    training_graph = build_training_graph(graph, positive_train)
    positive_set = set(positives)
    candidate_negatives = [pair for pair in non_edges(training_graph) if pair not in positive_set]
    if len(candidate_negatives) < len(positives):
        raise ValueError("The training graph has too few candidate non-edges for equal negative sampling")
    rng.shuffle(candidate_negatives)
    negative_train, negative_validation, negative_test = split(candidate_negatives[:len(positives)])
    return {
        "train_positive": positive_train,
        "validation_positive": positive_validation,
        "test_positive": positive_test,
        "train_negative": negative_train,
        "validation_negative": negative_validation,
        "test_negative": negative_test,
    }


def evaluate_scores(positive: list[tuple[int, int]], negative: list[tuple[int, int]], scores: list[float]) -> dict[str, float]:
    labels = [1] * len(positive) + [0] * len(negative)
    return {"auc": float(roc_auc_score(labels, scores)), "average_precision": float(average_precision_score(labels, scores))}


def heuristic_scores(graph: nx.Graph, pairs: list[tuple[int, int]], method: str) -> list[float]:
    if method == "common_neighbors":
        values = {(left, right): len(list(nx.common_neighbors(graph, left, right))) for left, right in pairs}
    elif method == "adamic_adar":
        values = {(left, right): score for left, right, score in nx.adamic_adar_index(graph, pairs)}
    else:
        values = {(left, right): score for left, right, score in nx.preferential_attachment(graph, pairs)}
    return [float(values.get(pair, 0.0)) for pair in pairs]


def fit_bilinear(embeddings: np.ndarray, node_order: list[int], links: dict[str, list[tuple[int, int]]], seed: int) -> np.ndarray:
    index = {node: position for position, node in enumerate(node_order)}
    positive = links["train_positive"]
    negative = links["train_negative"]
    pair_list = positive + negative
    labels = torch.tensor([1.0] * len(positive) + [0.0] * len(negative))
    left = torch.tensor([index[pair[0]] for pair in pair_list])
    right = torch.tensor([index[pair[1]] for pair in pair_list])
    torch.manual_seed(seed + 31)
    matrix = torch.nn.Parameter(torch.eye(embeddings.shape[1]))
    optimizer = torch.optim.Adam([matrix], lr=0.05)
    embedding_tensor = torch.tensor(embeddings, dtype=torch.float32)
    for _ in range(100):
        score = torch.einsum("bi,ij,bj->b", embedding_tensor[left], matrix, embedding_tensor[right])
        loss = torch.nn.functional.binary_cross_entropy_with_logits(score, labels)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    return matrix.detach().numpy()


def bilinear_scores(embeddings: np.ndarray, node_order: list[int], matrix: np.ndarray, pairs: list[tuple[int, int]]) -> list[float]:
    index = {node: position for position, node in enumerate(node_order)}
    return [float(1.0 / (1.0 + math.exp(-np.clip(embeddings[index[left]] @ matrix @ embeddings[index[right]], -50, 50)))) for left, right in pairs]


def select_learned_model(records: list[dict]) -> dict | None:
    ordered = sorted(
        records,
        key=lambda record: (
            -record["validation_auc"],
            -record["validation_average_precision"],
            record["dimension"],
            record["p"],
            record["q"],
        ),
    )
    return ordered[0] if ordered else None


def graph_fingerprint(graph: nx.Graph) -> dict:
    lines = sorted(
        f"{min(int(left), int(right))},{max(int(left), int(right))},{attributes.get('weight')!r}"
        for left, right, attributes in graph.edges(data=True)
    )
    encoded = "\n".join(lines).encode("utf-8")
    return {"nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(), "sha256": hashlib.sha256(encoded).hexdigest()}


def build_training_graph(graph: nx.Graph, train_positives: list[tuple[int, int]]) -> nx.Graph:
    training = nx.Graph()
    training.add_nodes_from(graph.nodes)
    for left, right in train_positives:
        training.add_edge(left, right, weight=graph[left][right]["weight"])
    return training


def validate_splits(links: dict[str, list[tuple[int, int]]], graph: nx.Graph, training_graph: nx.Graph) -> dict:
    problems: list[str] = []
    positive_splits = ("train_positive", "validation_positive", "test_positive")
    negative_splits = ("train_negative", "validation_negative", "test_negative")
    dataset = set(edge_pairs(graph))
    seen: set[tuple[int, int]] = set()
    for name in positive_splits:
        values = [tuple(pair) for pair in links[name]]
        if len(set(values)) != len(values):
            problems.append(f"{name} contains duplicate pairs")
        for pair in values:
            if pair not in dataset:
                problems.append(f"{name} pair {pair} is not a positive edge of the full graph")
            if pair in seen:
                problems.append(f"{name} pair {pair} overlaps another positive split")
        seen.update(values)
    if len(seen) != len(dataset):
        problems.append("positive splits do not cover all positive edges exactly once")
    positive_set = set(seen)
    negative_union: set[tuple[int, int]] = set()
    for name in negative_splits:
        values = [tuple(pair) for pair in links[name]]
        if len(set(values)) != len(values):
            problems.append(f"{name} contains duplicate pairs")
        for pair in values:
            if pair[0] == pair[1]:
                problems.append(f"{name} pair {pair} is a self-loop")
            if pair in positive_set:
                problems.append(f"{name} pair {pair} collides with a positive split")
            if pair in negative_union:
                problems.append(f"{name} pair {pair} overlaps another negative split")
            if training_graph.has_edge(*pair):
                problems.append(f"{name} pair {pair} is a training-graph edge")
        negative_union.update(values)
    for name in positive_splits:
        if len(links[name]) != len(links[name.replace("positive", "negative")]):
            problems.append(f"{name} is not balanced with its negative counterpart")
    hidden = [pair for pair in links["validation_positive"] + links["test_positive"] if training_graph.has_edge(*pair)]
    if hidden:
        problems.append(f"validation/test positives present in the training graph: {hidden}")
    if problems:
        detail = "; ".join(problems[:10])
        raise ValueError(f"split invariant violations: {detail}")
    return {
        "validated": True,
        "balanced_by_split": True,
        "disjoint_positive_splits": True,
        "disjoint_positive_negative": True,
        "no_self_loops": True,
        "validation_test_positive_absent_from_training_graph": True,
        "training_graph_edges": training_graph.number_of_edges(),
        "training_graph_fingerprint": graph_fingerprint(training_graph),
        "full_graph_fingerprint": graph_fingerprint(graph),
        "evaluation_fingerprint": hashlib.sha256(repr((links["test_positive"], links["test_negative"])).encode()).hexdigest(),
        "counts": {name: len(values) for name, values in links.items()},
    }


def agreement_metrics(labels_a: dict[int, int], labels_b: dict[int, int], nodes: list[int]) -> dict[str, float]:
    vector_a = [labels_a[node] for node in nodes]
    vector_b = [labels_b[node] for node in nodes]
    return {
        "ari": float(adjusted_rand_score(vector_a, vector_b)),
        "nmi": float(normalized_mutual_info_score(vector_a, vector_b)),
    }


def label_map(communities: list[set[int]], nodes: list[int]) -> dict[int, int]:
    labels: dict[int, int] = {}
    for index, group in enumerate(communities):
        for node in group:
            labels[node] = index
    return {node: labels.get(node, -1) for node in nodes}


def main() -> None:
    torch.set_num_threads(2)
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "clean")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "approach2" / "trade")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--p", type=float, default=1.0)
    parser.add_argument("--q", type=float, default=1.0)
    parser.add_argument("--p-values", default="0.5,1.0,2.0")
    parser.add_argument("--q-values", default="0.5,1.0,2.0")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--walks-per-node", type=int, default=8)
    parser.add_argument("--walk-length", type=int, default=12)
    parser.add_argument("--dimensions", default="8,16,32,64")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from data.fetch import verify_snapshots

    verify_snapshots(clean_dir=args.data)

    rng = set_seed(args.seed)
    started = time.perf_counter()
    nodes = load_nodes(args.data / "node_metadata.csv")
    edges = load_edges(args.data / "trade_flows.csv")
    year = max(years_in(edges))
    directed = directed_graph(edges, nodes, year, top_k=args.top_k)
    validate_graph(directed, label="directed trade graph")
    graph = undirected_graph(directed)
    validate_graph(graph, label="undirected trade graph")
    validate_undirected_consistency(directed, graph)

    links = split_links(graph, rng)
    training_graph = build_training_graph(graph, [tuple(pair) for pair in links["train_positive"]])
    validate_graph(training_graph, label="training graph")
    split_audit = validate_splits(links, graph, training_graph)

    dimensions = [int(value) for value in args.dimensions.split(",")]
    p_values = [float(value) for value in args.p_values.split(",")]
    q_values = [float(value) for value in args.q_values.split(",")]
    node_order = list(training_graph.nodes)
    validation_pairs = [tuple(pair) for pair in links["validation_positive"]] + [tuple(pair) for pair in links["validation_negative"]]
    validation_positive = [tuple(pair) for pair in links["validation_positive"]]
    validation_negative = [tuple(pair) for pair in links["validation_negative"]]
    test_pairs = [tuple(pair) for pair in links["test_positive"]] + [tuple(pair) for pair in links["test_negative"]]
    test_positive = [tuple(pair) for pair in links["test_positive"]]
    test_negative = [tuple(pair) for pair in links["test_negative"]]

    records: list[dict] = []
    models: dict[tuple[float, float, int], tuple[np.ndarray, np.ndarray]] = {}
    validation_sweep: dict[str, dict[str, dict]] = {}
    for p_value in p_values:
        for q_value in q_values:
            key = f"p={p_value:g},q={q_value:g}"
            sweep_seed = args.seed + int(p_value * 100) + int(q_value * 1000)
            walk_rng = np.random.default_rng(sweep_seed)
            walk_data = walk_pairs(training_graph, p_value, q_value, walk_rng, args.walks_per_node, args.walk_length, window=2)
            config_results: dict[str, dict] = {}
            for dimension in dimensions:
                embeddings = train_skipgram(walk_data, node_order, dimension, sweep_seed + dimension, args.epochs, negative_count=5)
                matrix = fit_bilinear(embeddings, node_order, links, sweep_seed + dimension)
                scores = bilinear_scores(embeddings, node_order, matrix, validation_pairs)
                metrics = evaluate_scores(validation_positive, validation_negative, scores)
                config_results[str(dimension)] = {"validation": metrics}
                records.append({
                    "p": p_value,
                    "q": q_value,
                    "dimension": dimension,
                    "validation_auc": metrics["auc"],
                    "validation_average_precision": metrics["average_precision"],
                    "walk_pair_count": len(walk_data),
                })
                models[(p_value, q_value, dimension)] = (embeddings, matrix)
            validation_sweep[key] = config_results

    selected = select_learned_model(records)
    if selected is None:
        raise ValueError("no learned model configurations were produced")
    selected_embeddings, selected_matrix = models[(selected["p"], selected["q"], selected["dimension"])]
    test_scores = bilinear_scores(selected_embeddings, node_order, selected_matrix, test_pairs)
    learned_test = evaluate_scores(test_positive, test_negative, test_scores)

    baseline_test = {}
    for method in ("common_neighbors", "adamic_adar", "preferential_attachment"):
        baseline_scores = heuristic_scores(training_graph, test_pairs, method)
        baseline_test[method] = evaluate_scores(test_positive, test_negative, baseline_scores)

    communities = nx.community.louvain_communities(training_graph, weight="weight", seed=args.seed)
    louvain_labels = label_map(communities, node_order)
    region_map = region_labels(nodes)
    region_names = sorted(set(region_map.values()))
    region_ids = {name: index for index, name in enumerate(region_names)}
    region_labels_vector = {node: region_ids[region_map.get(node, "Other")] for node in node_order}
    cluster_count = max(2, min(len(node_order), len(communities)))
    clusters_array = KMeans(n_clusters=cluster_count, random_state=args.seed, n_init=10).fit_predict(selected_embeddings)
    embedding_labels = {node: int(clusters_array[position]) for position, node in enumerate(node_order)}

    label_sets = {
        "embedding_kmeans": embedding_labels,
        "training_graph_louvain": louvain_labels,
        "region_geographical_proxy": region_labels_vector,
    }
    agreement_matrix: dict[str, dict[str, dict]] = {}
    names = sorted(label_sets)
    for left_index, left in enumerate(names):
        for right in names[left_index + 1:]:
            agreement_matrix[f"{left}|{right}"] = agreement_metrics(label_sets[left], label_sets[right], node_order)

    metrics = {
        "year": year,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "split_sizes": {key: len(value) for key, value in links.items()},
        "split_audit": split_audit,
        "split_pairs": links,
        "validation_sweep": validation_sweep,
        "selection": {
            "criterion": "highest validation AUC, then validation AP, then smaller dimension, then smaller p, then smaller q",
            "validation_only": True,
            "selected_p": selected["p"],
            "selected_q": selected["q"],
            "selected_dimension": selected["dimension"],
            "selected_validation": validation_sweep[f"p={selected['p']:g},q={selected['q']:g}"][str(selected["dimension"])]["validation"],
            "candidate_count": len(records),
        },
        "learned": learned_test,
        "baselines": baseline_test,
        "model_agreement": {
            "label_sets": {name: {"description": description} for name, description in (
                ("embedding_kmeans", "KMeans clusters of the validation-selected learned embeddings"),
                ("training_graph_louvain", "Louvain communities of the training graph"),
                ("region_geographical_proxy", "geographical region of the country; NOT an industry ground truth"),
            )},
            "pairs": agreement_matrix,
        },
        "training_graph_louvain": {
            "community_count": len(communities),
            "modularity": float(nx.community.modularity(training_graph, communities, weight="weight")),
        },
        "environment": environment_metadata(),
        "task": "Held-out trade-edge recovery on edges excluded from the training graph; walks, embeddings, heuristics, and bilinear fitting use the training graph only.",
    }

    dimensions_for_plot = sorted({record["dimension"] for record in records})
    figure = go.Figure()
    for key, config in validation_sweep.items():
        figure.add_trace(go.Scatter(
            x=dimensions_for_plot,
            y=[config[str(dimension)]["validation"]["auc"] for dimension in dimensions_for_plot],
            mode="lines+markers",
            name=f"validation AUC ({key})",
        ))
    figure.add_trace(go.Scatter(
        x=[selected["dimension"]],
        y=[learned_test["auc"]],
        mode="markers",
        marker={"symbol": "star", "size": 14},
        name=f"selected model TEST AUC (p={selected['p']:g}, q={selected['q']:g}, d={selected['dimension']})",
    ))
    figure.update_layout(title="Trade-link prediction: validation sweep vs final test (heuristic-free plot)", xaxis_title="Embedding dimension", yaxis_title="AUC")
    save_plot(figure, args.out / "link_prediction.html")

    ranking = [("learned (selected model)", learned_test, selected)] + [
        (method, baseline_metrics, {}) for method, baseline_metrics in baseline_test.items()
    ]
    ranking.sort(key=lambda item: (-item[1]["auc"], -item[1]["average_precision"]))
    write_metrics(
        args.out / "metrics.json",
        {
            "seed": args.seed,
            "p": args.p,
            "q": args.q,
            "p_values": p_values,
            "q_values": q_values,
            "top_k": args.top_k,
            "epochs": args.epochs,
            "walks_per_node": args.walks_per_node,
            "walk_length": args.walk_length,
            "dimensions": dimensions,
            "year": year,
        },
        metrics,
        time.perf_counter() - started,
        {"dimensions": dimensions_for_plot, "sweep_keys": sorted(validation_sweep), "final_test_ranking": [name for name, _, _ in ranking]},
    )

    table = Table(title="Q4 Approach 2: validation-selected learned model vs heuristic baselines (final test set)")
    table.add_column("Rank")
    table.add_column("Model")
    table.add_column("Test AUC")
    table.add_column("Test AP")
    for rank, (name, test_metrics, _) in enumerate(ranking, start=1):
        table.add_row(str(rank), name, f"{test_metrics['auc']:.3f}", f"{test_metrics['average_precision']:.3f}")
    console = Console()
    console.print(table)
    summary = Table(title="Selected configuration (validation only)")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("p", f"{selected['p']:g}")
    summary.add_row("q", f"{selected['q']:g}")
    summary.add_row("dimension", str(selected["dimension"]))
    summary.add_row("validation AUC", f"{selected['validation_auc']:.3f}")
    summary.add_row("validation AP", f"{selected['validation_average_precision']:.3f}")
    console.print(summary)


if __name__ == "__main__":
    main()
