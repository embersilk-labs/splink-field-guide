"""Behavior checks against the fixture's independently stated person identities."""

import tempfile
import unittest
from pathlib import Path

from match_people import load_people, run_demo, truth_pairs, write_csv


class SplinkDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blocked = run_demo()
        cls.all_pairs = run_demo(compare_all=True)

    def test_default_finds_typos_but_reports_both_deliberate_errors(self):
        _, _, summary = self.blocked
        self.assertEqual(summary["candidate_pairs"], 5)
        self.assertEqual(summary["true_matches"], [("1", "2"), ("3", "4"), ("5", "6")])
        self.assertEqual(summary["false_positives"], [("9", "10")])
        self.assertEqual(summary["false_negatives"], [("11", "12")])
        self.assertEqual(summary["missed_by_blocking"], [("11", "12")])
        self.assertEqual(summary["missed_by_score"], [])

    def test_all_pairs_recovers_missed_duplicate_but_cannot_separate_identical_people(self):
        _, _, summary = self.all_pairs
        self.assertEqual(summary["candidate_pairs"], 91)
        self.assertEqual(set(summary["true_matches"]), truth_pairs())
        self.assertEqual(summary["false_positives"], [("9", "10")])
        self.assertEqual(summary["false_negatives"], [])

    def test_conflicting_birth_dates_keep_sams_separate(self):
        pairs, clusters, _ = self.blocked
        sam = next(row for row in pairs if (row["left_id"], row["right_id"]) == ("7", "8"))
        self.assertFalse(sam["accepted"])
        membership = {row["unique_id"]: row["cluster_id"] for row in clusters}
        self.assertNotEqual(membership["7"], membership["8"])

    def test_clustering_keeps_singletons_and_exposes_the_false_merge(self):
        _, clusters, _ = self.blocked
        membership = {row["unique_id"]: row["cluster_id"] for row in clusters}
        self.assertEqual(len(membership), 14)
        self.assertEqual(membership["1"], membership["2"])
        self.assertEqual(membership["9"], membership["10"])
        self.assertNotEqual(membership["11"], membership["12"])
        self.assertEqual(membership["14"], "14")

    def test_postcode_keeps_leading_zero_and_truth_is_not_a_model_feature(self):
        people = load_people()
        self.assertEqual(people.loc[0, "postcode"], "02139")
        self.assertNotIn("person_id", people.columns)
        self.assertTrue(people.loc[13, "postcode"] != people.loc[13, "postcode"])

    def test_higher_threshold_exposes_score_misses_separately_from_blocking(self):
        _, _, summary = run_demo(threshold=0.99)
        self.assertEqual(summary["missed_by_score"], [("5", "6")])
        self.assertEqual(summary["missed_by_blocking"], [("11", "12")])
        self.assertEqual(summary["false_positives"], [("9", "10")])

    def test_invalid_threshold_is_rejected(self):
        for value in (0, 1, -0.5, float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                run_demo(threshold=value)

    def test_csv_writer_emits_header_when_no_pairs_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.csv"
            write_csv(path, [], ["left_id", "right_id"])
            self.assertEqual(path.read_text(), "left_id,right_id\n")


if __name__ == "__main__":
    unittest.main()
