from __future__ import annotations

import argparse
import json
from typing import Callable

from . import audit
from .config import load_competition, load_registry
from .loops import completeness, enrichment, feedback, features, patterns, recalibration, simulation, validation
from .pipeline import run_all


def main() -> None:
    parser=argparse.ArgumentParser(description="Replicable sports analytics engine")
    parser.add_argument(
        "command",
        choices=[
            "audit", "completeness", "enrich", "validate", "patterns",
            "feedback", "features", "simulate", "recalibrate", "run-all",
            "run-registry",
        ],
    )
    parser.add_argument("--competition",default=None,help="Competition ID from config/competitions.yaml")
    args=parser.parse_args()
    if args.command=="audit":
        result=audit.run()
    elif args.command == "run-registry":
        registry = load_registry()
        selected = [
            competition_id
            for competition_id, payload in registry.get("competitions", {}).items()
            if not payload.get("template", False)
            and (args.competition is None or args.competition == "all" or competition_id == args.competition)
        ]
        if not selected:
            raise ValueError("No executable competition matched the selection")
        result = {
            "summary": {
                "competitions_processed": len(selected),
                "competition_ids": selected,
            },
            "competitions": {competition_id: run_all(load_competition(competition_id)) for competition_id in selected},
        }
    else:
        config=load_competition(args.competition)
        commands:dict[str,Callable]={
            "completeness":completeness.run,"enrich":enrichment.run,"validate":validation.run,"patterns":patterns.run,
            "feedback":feedback.run,"features":features.run,"simulate":simulation.run,"recalibrate":recalibration.run,"run-all":run_all,
        }
        result=commands[args.command](config)
    print(json.dumps(result.get("summary",result),ensure_ascii=False,indent=2,default=str))


if __name__=="__main__": main()
