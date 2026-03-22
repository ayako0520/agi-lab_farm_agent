"""CLI entrypoint."""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

from farm_agent.agents.farm_agent import format_summary, run_autonomous
from farm_agent.output_rich import print_rich_summary
from farm_agent.report_html import render_dashboard


def _default_report_path(project_root: Path) -> Path:
    return project_root / "reports" / "latest.html"


def main(argv: list[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    load_dotenv(env_path)
    p = argparse.ArgumentParser(
        description="圃場向けデータ取得と HTML ダッシュボード（気象・NDVI・任意で JAXA・LLM 自律取得）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "マイナス付き座標（南緯・西経）の例:\n"
            "  オプション（--llm-agent 等）は必ず先に書き、そのあと -- で区切ってから座標と作物名を渡します。\n"
            '  python -m farm_agent.cli --llm-agent --pretty -- "-34.60,-58.38" soybean\n'
            "  （-- の後ろに --pretty を書くと、それらは位置引数扱いになりエラーになります）\n"
            "  別案: 先頭が - にならないよう = 形式で渡す（PowerShell でも可）:\n"
            '  python -m farm_agent.cli --llm-agent --pretty --location="-34.60,-58.38" --crop soybean'
        ),
    )
    p.add_argument(
        "location",
        nargs="?",
        default=None,
        help='住所・地名または "lat,lon"（--location と併用不可）',
    )
    p.add_argument(
        "crop",
        nargs="?",
        default=None,
        help="作物名（例: rice, tomato）（--crop と併用不可）",
    )
    p.add_argument(
        "--location",
        metavar="ADDR_OR_LAT_LON",
        dest="location_opt",
        default=None,
        help="場所（マイナス座標でも可）。位置引数の location の代わり。",
    )
    p.add_argument(
        "--crop",
        metavar="NAME",
        dest="crop_opt",
        default=None,
        help="作物名。位置引数の crop の代わり。",
    )
    p.add_argument(
        "-o",
        "--html",
        dest="html_out",
        type=Path,
        metavar="FILE",
        help="HTML レポートの保存先（省略時は farm_agent/reports/latest.html）",
    )
    p.add_argument(
        "--no-html",
        action="store_true",
        help="HTML レポートを書き出さない",
    )
    p.add_argument(
        "--no-browser",
        action="store_true",
        help="HTML は書くが既定ブラウザで開かない",
    )
    p.add_argument(
        "--pretty",
        action="store_true",
        help="ターミナル出力を Rich（表・パネル・バー）で表示",
    )
    p.add_argument(
        "--jaxa",
        action="store_true",
        help="JAXA Earth API（GSMaP 降水・AMSR2 SMC）を Sentinel の強弱に関係なく取得する",
    )
    p.add_argument(
        "--llm-agent",
        action="store_true",
        help="OpenAI ツール呼び出しで取得順を自律決定（要 OPENAI_API_KEY）。指定時は線形パイプラインと --jaxa は使わない",
    )
    args = p.parse_args(argv)

    loc = args.location_opt if args.location_opt is not None else args.location
    cr = args.crop_opt if args.crop_opt is not None else args.crop
    if loc is None or cr is None:
        p.error("location と crop を、位置引数2つで渡すか、--location と --crop の両方で指定してください。")
    if (args.location_opt is not None and args.location is not None) or (
        args.crop_opt is not None and args.crop is not None
    ):
        p.error("位置引数と --location / --crop の二重指定はできません。")

    result = run_autonomous(
        loc,
        cr,
        jaxa_always=args.jaxa and not args.llm_agent,
        llm_agent=args.llm_agent,
    )

    if not args.no_html:
        out = (
            args.html_out.expanduser().resolve()
            if args.html_out is not None
            else _default_report_path(project_root).resolve()
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_dashboard(result), encoding="utf-8")
        print(f"HTML dashboard: {out}", file=sys.stderr)
        if not args.no_browser and os.environ.get("FARM_AGENT_NO_BROWSER", "").strip() != "1":
            webbrowser.open(out.as_uri())

    if args.pretty:
        print_rich_summary(result)
    else:
        sys.stdout.write(format_summary(result) + "\n")

    return 0 if result.geocode and result.recommendation else 2


if __name__ == "__main__":
    raise SystemExit(main())
