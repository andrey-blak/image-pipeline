import argparse
import random
import sys
from pathlib import Path

from imgpipe.config import load_config
from imgpipe.errors import ConfigError
from imgpipe.pipeline import FileReport, Pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="imgpipe", description="Batch image transformation pipeline.")
    parser.add_argument("--config", type=Path, help="TOML pipeline config; without it nothing is done")
    parser.add_argument("--input", type=Path, default=Path("input"), help="input folder (default: input)")
    parser.add_argument("--output", type=Path, default=Path("output"), help="output folder (default: output)")
    parser.add_argument("--seed", type=int, help="seed for repeatable random values")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="list each file's original name, new name and applied changes"
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true",
        help="show what would be done (like --verbose) without writing any files",
    )
    return parser


def format_report(report: FileReport, input_dir: Path, output_dir: Path) -> str:
    changes = " | ".join(f"{key} {text}" for key, text in report.changes.items())
    return f"{input_dir / report.source} -> {output_dir / report.target} | {changes}"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.config is None:
        print("No config given; nothing to do.")
        return 0
    try:
        config = load_config(args.config)
        if not args.input.is_dir():
            raise ConfigError(f"input folder not found: {args.input}")
        on_file = None
        if args.verbose or args.dry_run:
            def on_file(report: FileReport) -> None:
                print(format_report(report, args.input, args.output), flush=True)

        if args.dry_run:
            print("Dry run (no changes will be made):", flush=True)
        pipeline = Pipeline(config.steps, config.fix_orientation, config.output, config.rename)
        result = pipeline.run(
            args.input, args.output, random.Random(args.seed), on_file, dry_run=args.dry_run
        )
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for path, reason in result.skipped:
        print(f"warning: skipped {path}: {reason}", file=sys.stderr)
    count = len(result.processed)
    images = f"{count} image" if count == 1 else f"{count} images"
    verb = "would be processed" if args.dry_run else "processed"
    print(f"{images} {verb}, {len(result.skipped)} skipped.")
    if result.renamed:
        # Always shown, not only with --verbose: the user did not choose these names.
        many = len(result.renamed) > 1
        print(
            f"{len(result.renamed)} {'files' if many else 'file'} "
            f"{'would get' if args.dry_run else 'got'} "
            f"a number added to {'their names' if many else 'its name'} "
            "because the name was already taken:"
        )
        for source, target in result.renamed:
            print(f"  {args.input / source} -> {args.output / target}")
    if args.dry_run:
        print("Nothing was written.")
    return 0
