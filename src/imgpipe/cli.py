import argparse
import random
import sys
from pathlib import Path

from imgpipe.preset import load_preset
from imgpipe.errors import PresetError
from imgpipe.pipeline import FileReport, Pipeline


DEFAULT_PRESET = Path("preset.toml")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="imgpipe", description="Batch image transformation pipeline.")
    parser.add_argument(
        "--preset", type=Path, help=f"TOML pipeline preset (default: {DEFAULT_PRESET})"
    )
    parser.add_argument(
        "-i", "--input", type=Path, help="input folder (default: the preset's input, else input)"
    )
    parser.add_argument(
        "-o", "--output", type=Path, help="output folder (default: the preset's output, else output)"
    )
    parser.add_argument(
        "--seed", type=int, help="seed for repeatable random values (default: the preset's seed, else random)"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "-v", "--verbose", action="store_true", help="also list the changes applied to each file"
    )
    mode.add_argument(
        "-q", "--quiet", action="store_true",
        help="do not print the progress line for each file or the summary (problems are still shown)",
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true",
        help="show what would be done (like --verbose) without writing any files",
    )
    return parser


def format_report(report: FileReport, input_dir: Path, output_dir: Path, details: bool = True) -> str:
    line = f"{input_dir / report.source} -> {output_dir / report.target}"
    if not details:
        return line
    changes = " | ".join(f"{key} {text}" for key, text in report.changes.items())
    return f"{line} | {changes}"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.quiet and args.dry_run:
        parser.error("argument -q/--quiet: not allowed with argument -n/--dry-run")
    try:
        if args.preset is None and not DEFAULT_PRESET.is_file():
            raise PresetError(
                f"preset file not found: {DEFAULT_PRESET} "
                "(put it in the current folder or use --preset FILE)"
            )
        preset = load_preset(args.preset or DEFAULT_PRESET)
        # Command line first, then the preset, then the built-in default.
        input_dir = args.input or Path(preset.input_folder or "input")
        output_dir = args.output or Path(preset.output_folder or "output")
        seed = args.seed if args.seed is not None else preset.seed
        if not input_dir.is_dir():
            raise PresetError(f"input folder not found: {input_dir}")
        on_file = None
        if not args.quiet:
            # One line per file as progress; the changes of each step only with -v or -n.
            details = args.verbose or args.dry_run

            def on_file(report: FileReport) -> None:
                print(format_report(report, input_dir, output_dir, details), flush=True)

        if args.dry_run:
            print("Dry run (no changes will be made):", flush=True)
        pipeline = Pipeline(preset.steps, preset.exif_orientation, preset.output, preset.rename)
        result = pipeline.run(
            input_dir, output_dir, random.Random(seed), on_file, dry_run=args.dry_run
        )
    except PresetError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for path, reason in result.skipped:
        print(f"warning: skipped {path}: {reason}", file=sys.stderr)
    count = len(result.processed)
    images = f"{count} image" if count == 1 else f"{count} images"
    verb = "would be processed" if args.dry_run else "processed"
    if not args.quiet:
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
            print(f"  {input_dir / source} -> {output_dir / target}")
    if args.dry_run:
        print("Nothing was written.")
    return 0
