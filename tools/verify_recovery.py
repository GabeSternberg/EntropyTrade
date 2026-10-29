"""Offline recovery proof on an existing quiescent workspace; no network or new receipts."""

import argparse
from pathlib import Path

from entropytrade.api.recovery_proof import verify_recovery


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--restored", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify_recovery(Path(__file__).resolve().parents[1], args.workspace, args.restored, args.output)


if __name__ == "__main__":
    main()
