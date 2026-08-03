from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analysis import render_markdown
from .protocol import ProtocolConfig
from .provider import AnthropicProvider
from .runner import BenchmarkRunner

CONFIRMATION = "RUN_10X10_CLAUDE_VALIDATION"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="SWARM_OS final 10-vs-10 validation")
    sub = root.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="Validate config and show maximum calls")
    run = sub.add_parser("run", help="Execute the live Claude API benchmark")
    for item in (plan, run):
        item.add_argument("--config", required=True)
        item.add_argument("--tasks", required=True)
        item.add_argument("--output-dir", required=True)
    run.add_argument("--confirm-live-run", required=True)
    run.add_argument("--resume", action="store_true")
    return root


def main() -> None:
    args = parser().parse_args()
    config = ProtocolConfig.load(args.config)
    config.validate()
    max_calls = config.agents_per_condition * config.tasks_per_agent * config.max_attempts * 2
    if args.command == "plan":
        print(json.dumps({
            "agents_per_condition": config.agents_per_condition,
            "tasks_per_agent": config.tasks_per_agent,
            "paired_observations": config.agents_per_condition * config.tasks_per_agent,
            "maximum_api_calls": max_calls,
            "model": config.model,
            "output_dir": str(Path(args.output_dir)),
        }, indent=2))
        return
    if args.confirm_live_run != CONFIRMATION:
        raise SystemExit(f"Refusing live API calls. Pass --confirm-live-run {CONFIRMATION}")
    provider = AnthropicProvider()
    runner = BenchmarkRunner(config=config, provider=provider, tasks_path=args.tasks, output_dir=args.output_dir, resume=args.resume)
    report = runner.run()
    print(render_markdown(report))


if __name__ == "__main__":
    main()
