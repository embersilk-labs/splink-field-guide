"""A small, local Splink example with deliberately visible linkage errors."""

import argparse
import csv
import itertools
import json
from pathlib import Path

import pandas as pd
import splink.comparison_library as cl
from splink import DuckDBAPI, Linker, SettingsCreator, block_on

HERE = Path(__file__).resolve().parent
DEFAULT_THRESHOLD = 0.95


def load_people():
    """Keep IDs and postcodes as strings, normalize text, preserve missing values."""
    frame = pd.read_csv(HERE / "data/people.csv", dtype=str)
    for column in ("first_name", "surname", "postcode"):
        frame[column] = frame[column].str.strip().str.lower().replace("", None)
    return frame


def model_settings(compare_all=False):
    # Explicit teaching parameters, NOT estimates learned from these 14 records.
    # Each list follows the non-null levels: exact, one edit (names), other.
    return SettingsCreator(
        link_type="dedupe_only",
        probability_two_random_records_match=0.01,
        comparisons=[
            cl.LevenshteinAtThresholds("first_name", [1]).configure(
                m_probabilities=[0.85, 0.10, 0.05],
                u_probabilities=[0.02, 0.03, 0.95],
            ),
            cl.LevenshteinAtThresholds("surname", [1]).configure(
                m_probabilities=[0.90, 0.08, 0.02],
                u_probabilities=[0.01, 0.02, 0.97],
            ),
            cl.ExactMatch("dob").configure(
                m_probabilities=[0.999, 0.001],
                u_probabilities=[0.005, 0.995],
            ),
            cl.ExactMatch("postcode").configure(
                m_probabilities=[0.80, 0.20],
                u_probabilities=[0.02, 0.98],
            ),
        ],
        blocking_rules_to_generate_predictions=(
            ["1=1"] if compare_all else [block_on("surname"), block_on("postcode")]
        ),
        retain_matching_columns=True,
    )


def pair_key(left, right):
    return tuple(sorted((str(left), str(right)), key=int))


def truth_pairs():
    """Labels are used only AFTER prediction, never as model features."""
    with (HERE / "data/truth.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    return {
        pair_key(left["unique_id"], right["unique_id"])
        for left, right in itertools.combinations(rows, 2)
        if left["person_id"] == right["person_id"]
    }


def ordered_pairs(pairs):
    return sorted(pairs, key=lambda pair: tuple(map(int, pair)))


def run_demo(compare_all=False, threshold=DEFAULT_THRESHOLD):
    if not 0 < threshold < 1:
        raise ValueError("threshold must be greater than 0 and less than 1")
    people = load_people()
    db_api = DuckDBAPI()
    linker = Linker(
        people, model_settings(compare_all), db_api=db_api,
        set_up_basic_logging=False,
    )
    # Keep ALL candidate scores so rejected candidates can also be inspected.
    predictions = linker.inference.predict()
    scored = predictions.as_record_dict()
    pairs = []
    for record in scored:
        left, right = pair_key(record["unique_id_l"], record["unique_id_r"])
        probability = float(record["match_probability"])
        pairs.append({
            "left_id": left,
            "right_id": right,
            "match_probability": round(probability, 6),
            "accepted": probability >= threshold,
        })
    pairs.sort(key=lambda row: (int(row["left_id"]), int(row["right_id"])))

    predicted = {
        (row["left_id"], row["right_id"]) for row in pairs if row["accepted"]
    }
    considered = {(row["left_id"], row["right_id"]) for row in pairs}
    truth = truth_pairs()
    missed = truth - predicted
    summary = {
        "records": len(people),
        "possible_pairs": len(people) * (len(people) - 1) // 2,
        "candidate_pairs": len(pairs),
        "mode": "all pairs" if compare_all else "surname OR postcode blocking",
        "threshold": threshold,
        "true_matches": ordered_pairs(predicted & truth),
        "false_positives": ordered_pairs(predicted - truth),
        "false_negatives": ordered_pairs(missed),
        "missed_by_blocking": ordered_pairs(truth - considered),
        "missed_by_score": ordered_pairs(missed & considered),
        "model_note": "Hand-set teaching parameters; no training or calibrated accuracy claim.",
    }

    clustered = linker.clustering.cluster_pairwise_predictions_at_threshold(
        predictions, threshold_match_probability=threshold,
    ).as_record_dict()
    # Stable, readable cluster labels: smallest numeric record ID in the component.
    groups = {}
    for record in clustered:
        groups.setdefault(str(record["cluster_id"]), []).append(str(record["unique_id"]))
    clusters = []
    for members in groups.values():
        cluster_id = min(members, key=int)
        clusters.extend({"unique_id": member, "cluster_id": cluster_id} for member in members)
    clusters.sort(key=lambda row: int(row["unique_id"]))
    return pairs, clusters, summary


def write_csv(path, rows, columns):
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def show_pairs(pairs):
    return ", ".join(f"{left}-{right}" for left, right in pairs) or "none"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare-all", action="store_true", help="score all 91 pairs in this tiny fixture")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    if not 0 < args.threshold < 1:
        parser.error("--threshold must be greater than 0 and less than 1")
    pairs, clusters, summary = run_demo(args.compare_all, args.threshold)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "pairs.csv", pairs, ["left_id", "right_id", "match_probability", "accepted"])
    write_csv(args.output_dir / "clusters.csv", clusters, ["unique_id", "cluster_id"])
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(f"Records: {summary['records']}")
    print(f"Candidate pairs: {summary['candidate_pairs']} / {summary['possible_pairs']} ({summary['mode']})")
    print(f"Threshold: {args.threshold:.2f}")
    print("Accepted pairs:")
    for row in pairs:
        if row["accepted"]:
            print(f"  {row['left_id']}-{row['right_id']}: {row['match_probability']:.6f}")
    for field, title in [
        ("true_matches", "True matches"), ("false_positives", "False positives"),
        ("false_negatives", "False negatives"), ("missed_by_blocking", "Missed by blocking"),
        ("missed_by_score", "Missed by score"),
    ]:
        print(f"{title}: {show_pairs(summary[field])}")
    print(f"Wrote {args.output_dir}/pairs.csv, clusters.csv, summary.json")


if __name__ == "__main__":
    main()
