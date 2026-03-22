"""CLI entrypoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from farm_agent.agents.farm_agent import format_summary, run_autonomous
from farm_agent.output_rich import print_rich_summary
from farm_agent.report_html import render_dashboard


def main(argv: list[str] | None = None) -> int:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)
    p = argparse.ArgumentParser(description="Autonomous farm decision agent (hackathon MVP)")
    p.add_argument("location", help='Address or "lat,lon"')
    p.add_argument("crop", help="Crop name (e.g. rice, tomato)")
    p.add_argument(
        "-o",
        "--html",
        dest="html_out",
        type=Path,
        metavar="FILE",
        help="グラフィカルな HTML レポートをこのパスに保存（ブラウザで開く）",
    )
    p.add_argument(
        "--pretty",
        action="store_true",
        help="ターミナル出力を Rich（表・パネル・バー）で表示",
    )
    args = p.parse_args(argv)

    result = run_autonomous(args.location, args.crop)

    if args.html_out is not None:
        out = args.html_out.expanduser().resolve()
        out.write_text(render_dashboard(result), encoding="utf-8")
        print(f"HTML dashboard written: {out}", file=sys.stderr)

    if args.pretty:
        print_rich_summary(result)
    else:
        sys.stdout.write(format_summary(result) + "\n")

    return 0 if result.geocode and result.recommendation else 2


if __name__ == "__main__":
    raise SystemExit(main())
