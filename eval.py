import csv
import time
from pipeline.verdict import get_verdict


def run_eval(csv_path="data/eval_set.csv"):
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))

    results = []
    for row in rows:
        verdict = get_verdict(row["vendor_name"], row["detail"])
        predicted_risky = verdict["risk"] != "Low"
        actual_risky = row["ground_truth"] != "Low"
        results.append(
            {
                "name": row["vendor_name"],
                "predicted": verdict["risk"],
                "actual": row["ground_truth"],
                "predicted_risky": predicted_risky,
                "actual_risky": actual_risky,
            }
        )
        time.sleep(2)

    tp = sum(1 for r in results if r["predicted_risky"] and r["actual_risky"])
    fp = sum(1 for r in results if r["predicted_risky"] and not r["actual_risky"])
    fn = sum(1 for r in results if not r["predicted_risky"] and r["actual_risky"])

    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

    print(f"\nPrecision: {precision:.0%}  Recall: {recall:.0%}  F1: {f1:.0%}\n")
    for r in results:
        mark = "correct" if r["predicted_risky"] == r["actual_risky"] else "WRONG"
        print(f"[{mark}] {r['name']}: predicted={r['predicted']}, actual={r['actual']}")


if __name__ == "__main__":
    run_eval()
