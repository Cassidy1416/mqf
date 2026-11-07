from __future__ import annotations

import argparse
import math
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
    label_vector,
    load_edges,
    load_nodes,
    non_edges,
    region_labels,
    save_plot,
    set_seed,
    undirected_graph,
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
            loss = -torch.nn.functional.logsigmoid(positive_score).mean() - torch.nn.functional.logsigmoid(-negative_score).mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    return model.weight.detach().cpu().numpy()


def split_links(graph: nx.Graph, rng: np.random.Generator) -> dict[str, list[tuple[int, int]]]:
    positives = edge_pairs(graph)
    negatives = non_edges(graph)
    if len(negatives) < len(positives):
        raise ValueError("The selected graph has too few non-edges for equal negative sampling")
    negatives = list(rng.choice(len(negatives), size=len(positives), replace=False))
    negative_pairs = [non_edges(graph)[index] for index in negatives]
    rng.shuffle(positives)
    rng.shuffle(negative_pairs)
    def split(values: list[tuple[int, int]]) -> tuple[list[tuple[int, int]], list[tuple[int, int]], list[tuple[int, int]]]:
        first = max(1, int(len(values) * 0.8))
        second = max(first + 1, int(len(values) * 0.9))
        return values[:first], values[first:second], values[second:]
    positive_train, positive_validation, positive_test = split(positives)
    negative_train, negative_validation, negative_test = split(negative_pairs)
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


def embedding_sweep(graph: nx.Graph, links: dict[str, list[tuple[int, int]]], dimensions: list[int], p: float, q: float, args, seed: int) -> dict[str, dict]:
    rng = np.random.default_rng(seed)
    walk_data = walk_pairs(graph, p, q, rng, args.walks_per_node, args.walk_length, window=2)
    evaluation_pairs = links["test_positive"] + links["test_negative"]
    results: dict[str, dict] = {}
    for dimension in dimensions:
        embeddings = train_skipgram(walk_data, list(graph.nodes), dimension, seed + dimension, args.epochs, negative_count=5)
        matrix = fit_bilinear(embeddings, list(graph.nodes), links, seed + dimension)
        learned_scores = bilinear_scores(embeddings, list(graph.nodes), matrix, evaluation_pairs)
        metrics = evaluate_scores(links["test_positive"], links["test_negative"], learned_scores)
        baseline_metrics = {}
        for method in ("common_neighbors", "adamic_adar", "preferential_attachment"):
            baseline_scores = heuristic_scores(graph, evaluation_pairs, method)
            baseline_metrics[method] = evaluate_scores(links["test_positive"], links["test_negative"], baseline_scores)
        communities = nx.community.louvain_communities(graph, weight="weight", seed=seed)
        community_map = {node: index for index, group in enumerate(communities) for node in group}
        node_records = load_nodes(args.data / "node_metadata.csv")
        region_map = region_labels(node_records)
        region_ids = {name: index for index, name in enumerate(sorted(set(region_map.values())))}
        node_order = list(graph.nodes)
        cluster_count = max(2, min(len(node_order), len(communities)))
        clusters = KMeans(n_clusters=cluster_count, random_state=seed, n_init=10).fit_predict(embeddings)
        results[str(dimension)] = {
            "learned": metrics,
            "baselines": baseline_metrics,
            "cluster_ari_vs_louvain": float(adjusted_rand_score([community_map[node] for node in node_order], clusters)),
            "cluster_nmi_vs_louvain": float(normalized_mutual_info_score([community_map[node] for node in node_order], clusters)),
            "cluster_ari_vs_region_proxy": float(adjusted_rand_score([region_ids[region_map[node]] for node in node_order], clusters)),
            "cluster_nmi_vs_region_proxy": float(normalized_mutual_info_score([region_ids[region_map[node]] for node in node_order], clusters)),
        }
    return results


def main() -> None:
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
    rng = set_seed(args.seed)
    started = time.perf_counter()
    nodes = load_nodes(args.data / "node_metadata.csv")
    edges = load_edges(args.data / "trade_flows.csv")
    year = max(years_in(edges))
    graph = undirected_graph(directed_graph(edges, nodes, year, top_k=args.top_k))
    links = split_links(graph, rng)
    dimensions = [int(value) for value in args.dimensions.split(",")]
    p_values = [float(value) for value in args.p_values.split(",")]
    q_values = [float(value) for value in args.q_values.split(",")]
    sweep = {}
    for p_value in p_values:
        for q_value in q_values:
            key = f"p={p_value:g},q={q_value:g}"
            sweep[key] = embedding_sweep(graph, links, dimensions, p_value, q_value, args, args.seed + int(p_value * 100) + int(q_value * 1000))
    default_key = f"p={args.p:g},q={args.q:g}"
    results = sweep[default_key]
    best_sweep = max(
        ((item["learned"]["auc"], key, dimension) for key, values in sweep.items() for dimension, item in values.items()),
        key=lambda item: item[0],
    )
    metrics = {
        "year": year,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "split_sizes": {key: len(value) for key, value in links.items()},
        "dimensions": results,
        "sweep": sweep,
        "best_sweep": {"auc": best_sweep[0], "configuration": best_sweep[1], "dimension": int(best_sweep[2])},
        "task": "Held-out undirected trade-edge recovery on the latest annual induced network.",
    }
    dimensions_for_plot = sorted(int(value) for value in results)
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=dimensions_for_plot, y=[results[str(value)]["learned"]["auc"] for value in dimensions_for_plot], mode="lines+markers", name="node2vec + bilinear"))
    for method in ("common_neighbors", "adamic_adar", "preferential_attachment"):
        figure.add_trace(go.Scatter(x=dimensions_for_plot, y=[results[str(value)]["baselines"][method]["auc"] for value in dimensions_for_plot], mode="lines+markers", name=method))
    figure.update_layout(title="Held-out trade-link prediction AUC", xaxis_title="Embedding dimension", yaxis_title="AUC")
    save_plot(figure, args.out / "link_prediction.html")
    write_metrics(args.out / "metrics.json", {"seed": args.seed, "p": args.p, "q": args.q, "p_values": p_values, "q_values": q_values, "top_k": args.top_k, "epochs": args.epochs, "year": year}, metrics, time.perf_counter() - started, {"dimensions": dimensions_for_plot, "sweep_keys": sorted(sweep)})
    table = Table(title="Q4 Approach 2: node embeddings")
    table.add_column("Dimension")
    table.add_column("Learned AUC")
    table.add_column("CN AUC")
    table.add_column("AA AUC")
    table.add_column("PA AUC")
    for dimension in dimensions_for_plot:
        item = results[str(dimension)]
        table.add_row(str(dimension), f"{item['learned']['auc']:.3f}", f"{item['baselines']['common_neighbors']['auc']:.3f}", f"{item['baselines']['adamic_adar']['auc']:.3f}", f"{item['baselines']['preferential_attachment']['auc']:.3f}")
    Console().print(table)


if __name__ == "__main__":
    main()
