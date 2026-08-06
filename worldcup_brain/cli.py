from __future__ import annotations

import argparse
import json

from .config import load_config
from .collectors import collect_missing
from .audit import run as run_audit
from .status import build as build_status
from .pipeline import prepare, replay
from .validation import validate


def main() -> None:
    parser = argparse.ArgumentParser(description="Leakage-safe temporal learning engine for the 2026 World Cup")
    parser.add_argument("command", choices=["audit", "prepare", "collect", "replay", "daily", "post-match", "validate", "status", "run-all"])
    parser.add_argument("--as-of", default=None, help="UTC or timezone-aware historical cutoff")
    parser.add_argument("--no-clean", action="store_true", help="Do not clear generated temporal artifacts before replay")
    parser.add_argument("--allow-network", action="store_true", help="Allow configured public-source enrichment; historical timestamps remain mandatory")
    args = parser.parse_args()
    config = load_config()
    if args.command == "audit":
        result = run_audit(config)
    elif args.command == "prepare":
        result = prepare(config)
    elif args.command == "collect":
        result = collect_missing(config, as_of=args.as_of, allow_network=args.allow_network)
    elif args.command in {"replay", "daily", "post-match"}:
        result = replay(config, as_of=args.as_of, clean=not args.no_clean)
    elif args.command == "validate":
        result = validate(config, expect_complete=args.as_of is None)
    elif args.command == "status":
        result = build_status(config)
    else:
        replay_result = replay(config, as_of=args.as_of, clean=not args.no_clean)
        validation_result = validate(config, expect_complete=args.as_of is None)
        result = {"replay": replay_result, "validation": validation_result}
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
