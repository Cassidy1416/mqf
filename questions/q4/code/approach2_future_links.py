"""Forecast formation of next-year major-trade links using past graphs only."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import networkx as nx
import numpy as np
import torch
import plotly.graph_objects as go
from scipy.linalg import orthogonal_procrustes
from rich.console import Console
from rich.table import Table

from common import ROOT, directed_graph, undirected_graph, load_nodes, load_edges, years_in, write_metrics, save_plot, validate_graph
from approach2_node_embeddings import walk_pairs, train_skipgram, evaluate_scores, heuristic_scores, select_learned_model, graph_fingerprint, bilinear_scores


def transition_sample(graph, following, feature_year, seed):
    """Conditional on no current major edge, label next-year edge appearance."""
    candidates = sorted((min(a, b), max(a, b)) for a, b in nx.non_edges(graph))
    positives = [p for p in candidates if following.has_edge(*p)]
    negatives = [p for p in candidates if not following.has_edge(*p)]
    if not positives or len(negatives) < len(positives):
        raise ValueError(f"Insufficient positive/negative formations for {feature_year}")
    rng = np.random.default_rng(seed + feature_year)
    rng.shuffle(positives)
    rng.shuffle(negatives)
    return {"feature_year": feature_year, "target_year": feature_year + 1,
            "positive": positives, "negative": negatives[:len(positives)],
            "population_positive": len(positives), "population_negative": len(negatives),
            "feature_graph": graph_fingerprint(graph)}


def embed(graph, args, p, q, dimension, reference=None):
    pairs = walk_pairs(graph, p, q, np.random.default_rng(args.seed), args.walks_per_node, args.walk_length, 2)
    vectors = train_skipgram(pairs, list(graph.nodes), dimension, args.seed + dimension, args.epochs, 5)
    # Rotation alignment uses only node correspondence and current/prior graph embeddings.
    if reference is not None:
        rotation, _ = orthogonal_procrustes(vectors, reference)
        vectors = np.einsum("ij,jk->ik", vectors.astype(np.float64), rotation.astype(np.float64), optimize=False).astype(vectors.dtype)
    if not np.isfinite(vectors).all():
        raise ValueError("Nonfinite aligned embeddings")
    return vectors


def fit_matrix(samples, embeddings, node_order):
    lookup = {n: i for i, n in enumerate(node_order)}
    left, right, labels = [], [], []
    for sample in samples:
        vectors = embeddings[sample["feature_year"]]
        for key, label in (("positive", 1.0), ("negative", 0.0)):
            for a, b in sample[key]:
                left.append(vectors[lookup[a]])
                right.append(vectors[lookup[b]])
                labels.append(label)
    x, y, target = torch.tensor(np.array(left)), torch.tensor(np.array(right)), torch.tensor(labels)
    matrix = torch.nn.Parameter(torch.eye(x.shape[1]))
    optimizer = torch.optim.Adam([matrix], lr=.05)
    for _ in range(100):
        logits = torch.einsum("bi,ij,bj->b", x, matrix, y)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, target)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    return matrix.detach().numpy()


def score(matrix, vectors, nodes, sample):
    pairs = sample["positive"] + sample["negative"]
    values = bilinear_scores(vectors, nodes, matrix, pairs)
    return evaluate_scores(sample["positive"], sample["negative"], values)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data", type=Path, default=ROOT / "data/clean")
    parser.add_argument("--out", type=Path, default=ROOT / "results/approach2/trade_future")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--walks-per-node", type=int, default=8)
    parser.add_argument("--walk-length", type=int, default=12)
    parser.add_argument("--dimensions", default="8,16,32,64")
    parser.add_argument("--p-values", default="0.5,1,2")
    parser.add_argument("--q-values", default="0.5,1,2")
    parser.add_argument("--top-k", type=int, default=6)
    args = parser.parse_args(argv)
    if args.seed < 0 or min(args.epochs, args.walks_per_node, args.walk_length) < 1:
        parser.error("Seed must be nonnegative and training settings positive")
    torch.set_num_threads(2)
    torch.manual_seed(args.seed)
    import sys
    sys.path.insert(0, str(ROOT))
    from data.fetch import verify_snapshots
    verify_snapshots(args.data)
    started = time.perf_counter()
    nodes, edges = load_nodes(args.data / "node_metadata.csv"), load_edges(args.data / "trade_flows.csv")
    years = years_in(edges)
    if len(years) < 4 or any(b != a + 1 for a, b in zip(years, years[1:])):
        raise ValueError("Temporal prediction requires consecutive annual snapshots")
    graphs = {y: undirected_graph(directed_graph(edges, nodes, y, args.top_k)) for y in years}
    for graph in graphs.values():
        validate_graph(graph)
    samples = [transition_sample(graphs[y], graphs[y+1], y, args.seed) for y in years[:-1]]
    train, validation, testing = samples[:-2], samples[-2], samples[-1]
    order = list(graphs[years[0]].nodes)
    candidates, models, sweep = [], {}, {}
    for p in map(float, args.p_values.split(",")):
        for q in map(float, args.q_values.split(",")):
            for dimension in map(int, args.dimensions.split(",")):
                reference = embed(graphs[years[0]], args, p, q, dimension)
                embeddings = {s["feature_year"]: embed(graphs[s["feature_year"]], args, p, q, dimension, reference) for s in train + [validation]}
                matrix = fit_matrix(train, embeddings, order)
                result = score(matrix, embeddings[validation["feature_year"]], order, validation)
                row = {"p": p, "q": q, "dimension": dimension, "validation_auc": result["auc"], "validation_average_precision": result["average_precision"]}
                candidates.append(row)
                key = f"p={p:g},q={q:g},d={dimension}"
                sweep[key] = result
                models[(p, q, dimension)] = (matrix, reference)
    selected = select_learned_model(candidates)
    matrix, reference = models[(selected["p"], selected["q"], selected["dimension"]) ]
    test_vectors = embed(graphs[testing["feature_year"]], args, selected["p"], selected["q"], selected["dimension"], reference)
    learned = score(matrix, test_vectors, order, testing)
    baselines = {method: evaluate_scores(testing["positive"], testing["negative"], heuristic_scores(graphs[testing["feature_year"]], testing["positive"] + testing["negative"], method))
                 for method in ("common_neighbors", "adamic_adar", "preferential_attachment")}
    fingerprint = hashlib.sha256(json.dumps(testing, sort_keys=True).encode()).hexdigest()
    metrics = {"task": "Next-year formation of a top-six major-trade relation, conditional on its absence in the forecast graph",
               "training_transitions": [{"feature_year": s["feature_year"], "target_year": s["target_year"], "positive_count": len(s["positive"]), "negative_count": len(s["negative"])} for s in train],
               "validation_sample": validation, "test_sample": testing, "evaluation_fingerprint": fingerprint,
               "selection": selected, "validation_sweep": sweep, "learned": learned, "baselines": baselines,
               "information_audit": {"training_target_cutoff": train[-1]["target_year"], "validation_target_year": validation["target_year"], "test_target_year": testing["target_year"],
                                     "test_feature_cutoff": testing["feature_year"], "test_labels_used_for_selection": False,
                                     "embeddings_use_only_forecast_graph": True},
               "limitations": ["The country universe is a fixed retrospective subset selected using 2023 trade, not a point-in-time global country selection.",
                               "The target is a major-edge appearance in the fixed top-six construction, not the first occurrence of any raw positive trade flow.",
                               "AUC/AP are evaluated on a balanced case-control sample; AP is not population-prevalence adjusted."]}
    write_metrics(args.out / "metrics.json", {"question": "q4", "approach": "approach2", "dataset": "trade_future", "seed": args.seed,
                  "epochs": args.epochs, "dimensions": args.dimensions, "p_values": args.p_values, "q_values": args.q_values,
                  "alignment": "Orthogonal Procrustes using current graph nodes and the first training-year reference; no future labels",
                  "residual_nondeterminism": "Seeded CPU computations; floating-point reductions may vary by platform."}, metrics, time.perf_counter()-started, {"validation_candidates": candidates})
    figure = go.Figure(go.Bar(x=["learned", *baselines], y=[learned["auc"], *[v["auc"] for v in baselines.values()]]))
    figure.update_layout(title=f"Next-year major-trade link formation: {testing['feature_year']} to {testing['target_year']}", yaxis_title="Final test AUC")
    save_plot(figure, args.out / "future_links.html")
    table = Table(title="Q4 future-link test (configuration selected on validation only)")
    for name in ("Method", "AUC", "AP"):
        table.add_column(name)
    for name, result in sorted({"learned": learned, **baselines}.items(), key=lambda kv: -kv[1]["auc"]):
        table.add_row(name, f"{result['auc']:.4f}", f"{result['average_precision']:.4f}")
    Console().print(table)


if __name__ == "__main__":
    main()
