"""
Train all XGBoost models used by the ML service (after datasets exist).

From the ml-service directory:

  python datasets/generate_dataset.py
  python datasets/generate_behavior_dataset.py
  python training/train_all.py

This script builds ``datasets/borrower_training.csv`` from ``invoices.csv`` before
training the borrower model. Or run it alone if invoices, behavior CSV, and
(up to date) borrower CSV workflow are already satisfied.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPTS = [
    "training/train_payment.py",
    "training/train_risk.py",
    "training/train_delay.py",
    "training/train_behavior.py",
    "training/train_borrower.py",
]


def main() -> None:
    inv = ROOT / "datasets" / "invoices.csv"
    beh = ROOT / "datasets" / "behavior_training.csv"
    if not inv.exists():
        print(f"Missing {inv} — run: python datasets/generate_dataset.py", file=sys.stderr)
        sys.exit(1)
    if not beh.exists():
        print(f"Missing {beh} — run: python datasets/generate_behavior_dataset.py", file=sys.stderr)
        sys.exit(1)

    gen_borrower = ROOT / "datasets" / "generate_borrower_training.py"
    print("\n" + "=" * 60)
    print("datasets/generate_borrower_training.py")
    print("=" * 60)
    rc = subprocess.call([sys.executable, str(gen_borrower)], cwd=str(ROOT))
    if rc != 0:
        sys.exit(rc)

    for rel in SCRIPTS:
        path = ROOT / rel
        print("\n" + "=" * 60)
        print(path.name)
        print("=" * 60)
        cmd = [sys.executable, str(path)]
        rc = subprocess.call(cmd, cwd=str(ROOT))
        if rc != 0:
            sys.exit(rc)

    print("\nAll training jobs finished.")


if __name__ == "__main__":
    main()
