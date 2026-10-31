"""Controlled one-date browser rollover fixture; clock acceleration is software evidence only."""

import argparse
from pathlib import Path

from tests.integration.forward_validation_fixture import seed_dates, serve

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--phase", type=Path)
    parser.add_argument("--port", type=int, default=43153)
    args = parser.parse_args()
    if args.phase:
        serve(args.workspace, args.phase, args.port)
    else:
        seed_dates(args.workspace, count=1)
