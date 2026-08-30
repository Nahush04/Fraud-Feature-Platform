"""Sanity-check the IEEE-CIS raw CSVs after a manual Kaggle download.

Does not fetch the data itself (requires a Kaggle account/token) -- see
README.md for the download command. This just validates what landed in
data/raw/ before ingestion runs against it.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REQUIRED_FILES = ("train_transaction.csv", "train_identity.csv")


def check_file(path: Path) -> int:
    if not path.exists():
        raise FileNotFoundError(f"missing {path} -- see data/README.md")
    with path.open(newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.reader(f)) - 1  # exclude header


def fraud_rate(transaction_path: Path) -> float:
    total = 0
    fraud = 0
    with transaction_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fraud_idx = reader.fieldnames.index("isFraud")
        for row in reader:
            total += 1
            if row["isFraud"] == "1":
                fraud += 1
    return fraud / total if total else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data/raw", type=Path)
    args = parser.parse_args()

    for name in REQUIRED_FILES:
        rows = check_file(args.data_dir / name)
        print(f"{name}: {rows:,} rows")

    rate = fraud_rate(args.data_dir / "train_transaction.csv")
    print(f"fraud rate: {rate:.3%}")


if __name__ == "__main__":
    sys.exit(main())
