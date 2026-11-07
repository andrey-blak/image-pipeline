import argparse
import random
import sys
from pathlib import Path

from imgpipe.config import load_steps
from imgpipe.errors import ConfigError
from imgpipe.pipeline import Pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="imgpipe", description="Batch image transformation pipeline.")
    parser.add_argument("--config", type=Path, help="TOML pipeline config; without it nothing is done")
    parser.add_argument("--input", type=Path, default=Path("input"), help="input folder (default: input)")
    parser.add_argument("--output", type=Path, default=Path("output"), help="output folder (default: output)")
    parser.add_argument("--seed", type=int, help="seed for repeatable random values")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.config is None:
        print("No config given; nothing to do.")
        return 0
    try:
        steps = load_steps(args.config)
        if not args.input.is_dir():
            raise ConfigError(f"input folder not found: {args.input}")
        result = Pipeline(steps).run(args.input, args.output, random.Random(args.seed))
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for path, reason in result.skipped:
        print(f"warning: skipped {path}: {reason}", file=sys.stderr)
    print(f"Processed {len(result.processed)} image(s), skipped {len(result.skipped)}.")
    return 0
