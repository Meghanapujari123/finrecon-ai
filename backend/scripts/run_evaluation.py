"""Run reconciliation + evaluation for a batch and write a JSON artifact.

Usage:
    python scripts/run_evaluation.py --batch-id <id>
    python scripts/run_evaluation.py --create-demo --n 150 --seed 42
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from app.evaluation.evaluator import run_evaluation  # noqa: E402
from app.services.batch_service import create_demo_batch  # noqa: E402
from app.services.reconciliation_service import run_reconciliation  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Run FinRecon AI evaluation")
    parser.add_argument("--batch-id", type=str, default=None)
    parser.add_argument("--create-demo", action="store_true")
    parser.add_argument("--n", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="evaluation_report.json")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        batch_id = args.batch_id
        if args.create_demo or not batch_id:
            batch = create_demo_batch(db, n_base=args.n, seed=args.seed)
            batch_id = batch.id
            print(f"Created demo batch {batch_id}")

        recon_result = run_reconciliation(db, batch_id)
        print("Reconciliation:", json.dumps(recon_result, indent=2))

        eval_result = run_evaluation(db, batch_id)
        print("Evaluation:", json.dumps(eval_result, indent=2))

        with open(args.out, "w") as f:
            json.dump({"reconciliation": recon_result, "evaluation": eval_result}, f, indent=2)
        print(f"Wrote {args.out}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
