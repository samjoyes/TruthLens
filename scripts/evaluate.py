"""Evaluation script benchmarking TruthLens against labelled dataset."""

import argparse
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from core.pipeline import run_analysis


def evaluate(csv_path: str, output_csv: str, limit: int | None = None) -> None:
    """Run pipeline across evaluation dataset and compute performance metrics."""
    df = pd.read_csv(csv_path)
    if limit:
        df = df.head(limit)

    print(f"Starting evaluation on {len(df)} samples from '{csv_path}'...")
    predictions = []
    latencies = []
    credibility_scores = []
    confidences = []

    for idx, row in df.iterrows():
        headline = str(row["headline"])
        body = str(row.get("body", ""))
        true_label = str(row["label"])

        print(f"\n[{idx + 1}/{len(df)}] Evaluating: {headline[:60]}...")
        start_t = time.time()
        try:
            res = run_analysis(headline=headline, body=body)
            elapsed = time.time() - start_t
            pred_verdict = res.verdict
            credibility = res.credibility_score
            confidence = res.confidence
            print(f"   -> Ground Truth: {true_label} | Predicted: {pred_verdict} ({elapsed:.2f}s)")
        except Exception as e:
            elapsed = time.time() - start_t
            pred_verdict = "Misleading"  # Neutral default on failure
            credibility = 50
            confidence = 20
            print(f"   -> ERROR ({e}); falling back to default verdict {pred_verdict}")

        predictions.append(pred_verdict)
        latencies.append(elapsed)
        credibility_scores.append(credibility)
        confidences.append(confidence)

    df["predicted_label"] = predictions
    df["credibility_score"] = credibility_scores
    df["confidence"] = confidences
    df["latency_sec"] = latencies

    # Compute metrics
    labels = ["Real", "Misleading", "Fake"]
    acc = accuracy_score(df["label"], df["predicted_label"])
    avg_latency = float(np.mean(latencies))

    print("\n" + "=" * 60)
    print("                 TRUTHLENS EVALUATION RESULTS")
    print("=" * 60)
    print(f"Total Evaluated Samples : {len(df)}")
    print(f"Overall Accuracy        : {acc * 100:.2f}%")
    print(f"Average Latency/Sample  : {avg_latency:.2f} seconds")
    print("-" * 60)
    print("\nClassification Report:\n")
    print(classification_report(df["label"], df["predicted_label"], labels=labels, zero_division=0))

    cm = confusion_matrix(df["label"], df["predicted_label"], labels=labels)
    cm_df = pd.DataFrame(cm, index=[f"Actual {l}" for l in labels], columns=[f"Pred {l}" for l in labels])
    print("Confusion Matrix:\n")
    print(cm_df)
    print("=" * 60)

    # Save detailed per-sample outcomes
    df.to_csv(output_csv, index=False)
    print(f"\nDetailed evaluation results saved to: {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate TruthLens performance")
    parser.add_argument("--csv", default="data/eval_set.csv", help="Path to labelled evaluation CSV")
    parser.add_argument("--out", default="data/eval_results.csv", help="Path to save evaluation output")
    parser.add_argument("--limit", type=int, default=None, help="Optional max rows to evaluate")
    args = parser.parse_args()

    evaluate(args.csv, args.out, limit=args.limit)
