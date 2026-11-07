import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import unittest
import networkx as nx
import numpy as np
from common import validate_graph, apply_trade_distance, undirected_graph, validate_undirected_consistency
from approach1_network_analytics import migration, graph_statistics
from approach2_node_embeddings import split_links, build_training_graph, validate_splits, select_learned_model
from approach2_future_links import transition_sample


class GraphContracts(unittest.TestCase):
    def test_projection_preserves_union_and_sums_reciprocal_weights(self):
        graph = nx.DiGraph()
        graph.add_weighted_edges_from([(0, 1, 10), (1, 0, 20), (1, 2, 5)])
        projection = undirected_graph(graph)
        validate_undirected_consistency(graph, projection)
        projection[0][1]["weight"] = 20
        with self.assertRaisesRegex(ValueError, "summed"):
            validate_undirected_consistency(graph, projection)

    def graph(self):
        graph = nx.cycle_graph(10)
        nx.set_edge_attributes(graph, 100.0, "weight")
        return graph

    def test_split_excludes_every_holdout_edge_from_training(self):
        graph = self.graph()
        links = split_links(graph, np.random.default_rng(42))
        training = build_training_graph(graph, links["train_positive"])
        audit = validate_splits(links, graph, training)
        self.assertTrue(audit["validation_test_positive_absent_from_training_graph"])
        for pair in links["validation_positive"] + links["test_positive"]:
            self.assertFalse(training.has_edge(*pair))
        self.assertEqual(len(links["test_positive"]), len(links["test_negative"]))

    def test_selection_never_uses_test_auc(self):
        records = [{"p": 1, "q": 1, "dimension": 8, "validation_auc": .8, "validation_average_precision": .7, "test_auc": 0},
                   {"p": 1, "q": 1, "dimension": 16, "validation_auc": .6, "validation_average_precision": .8, "test_auc": 1}]
        self.assertEqual(select_learned_model(records)["dimension"], 8)
        records[0]["test_auc"], records[1]["test_auc"] = 1, 0
        self.assertEqual(select_learned_model(records)["dimension"], 8)

    def test_migration_preserves_a_split_and_label_permutation(self):
        result = migration({0: 0, 1: 0, 2: 0, 3: 0}, {0: 7, 1: 7, 2: 9, 3: 9}, list(range(4)))
        self.assertEqual(result["contingency"], [[2, 2]])
        self.assertEqual(result["changed_share"], .5)
        same = migration({0: 0, 1: 1}, {0: 9, 1: 8}, [0, 1])
        self.assertEqual(same["changed_share"], 0)

    def test_density_and_distance_definitions(self):
        graph = nx.DiGraph()
        graph.add_weighted_edges_from([(0, 1, 10), (1, 2, 100)])
        apply_trade_distance(graph)
        self.assertGreater(graph[0][1]["distance"], graph[1][2]["distance"])
        stats = graph_statistics(graph, graph.to_undirected())
        self.assertAlmostEqual(stats["directed_density"], 1/3)
        self.assertAlmostEqual(stats["undirected_density"], 2/3)
        graph.add_edge(0, 0, weight=1)
        with self.assertRaises(ValueError):
            validate_graph(graph)

    def test_future_labels_refer_only_to_absent_current_edges(self):
        current = self.graph()
        following = current.copy()
        following.add_edge(0, 4, weight=100)
        sample = transition_sample(current, following, 2020, 42)
        self.assertEqual(sample["target_year"], 2021)
        self.assertEqual(sample["positive"], [(0, 4)])
        self.assertFalse(current.has_edge(*sample["positive"][0]))
        self.assertTrue(all(not following.has_edge(*p) for p in sample["negative"]))


if __name__ == "__main__":
    unittest.main()
