"""Generate the synthetic demo dataset and seed it into the database.

Usage:
    python scripts/generate_demo_data.py [--n 150] [--seed 42]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from app.services.batch_service import create_demo_batch  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Seed FinRecon AI demo data")
    parser.add_argument("--n", type=int, default=150, help="Number of base transactions (>=50)")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    args = parser.parse_args()

    if args.n < 50:
        raise SystemExit("Hackathon requirement is a 50+ record batch; --n must be >= 50")

    init_db()
    db = SessionLocal()
    try:
        batch = create_demo_batch(db, n_base=args.n, seed=args.seed)
        print(f"Seeded demo batch: {batch.id}")
        print(f"Label: {batch.label}")
        print(f"Scenario distribution: {batch.notes}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
