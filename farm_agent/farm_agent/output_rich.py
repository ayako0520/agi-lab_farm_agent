"""Optional Rich terminal layout."""

from __future__ import annotations

from typing import Any


def print_rich_summary(result: Any) -> None:
    from rich import box
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    title = f"[bold]{result.crop}[/] · [cyan]farm agent[/]"
    if getattr(result, "llm_agent_mode", False):
        title += " [magenta]· LLMツール自律[/]"
    console.print(Panel.fit(title, border_style="bright_magenta"))

    if getattr(result, "llm_agent_mode", False):
        tr = getattr(result, "llm_agent_trace", None) or []
        demo_tags = getattr(result, "llm_agent_demo_tags", None) or []
        if "force_ndvi_fail_sim" in demo_tags:
            console.print(
                "[yellow]【オプション】FARM_AGENT_LLM_DEMO_FORCE_NDVI_FAIL=1 — 最初の fetch_ndvi はシミュレーション失敗です[/]"
            )
        intro = (
            "[dim]OpenAI の function calling でデータ取得順を自律選択。"
            "要 OPENAI_API_KEY。一覧は呼び出し順（順序ミスによる一発失敗が含まれることがあります）。[/]\n"
        )
        if tr:
            rows: list[str] = []
            for ev in tr:
                step = ev.get("step", len(rows) + 1)
                name = ev.get("tool", "")
                summ = str(ev.get("summary", ""))
                ok = ev.get("ok", False)
                st = "[green]OK[/]" if ok else "[yellow]失敗[/]"
                rows.append(f"{step}. [cyan]{name}[/] — {st} {summ}")
            body = intro + "\n".join(rows)
        else:
            body = intro + "[yellow]ツール実行ログなし（API キーや通信で中断した可能性）[/]"
        console.print(
            Panel(
                body,
                title="自律 LLM エージェント（OpenAI ツール）",
                border_style="magenta",
            )
        )

    if result.geocode:
        g = result.geocode
        console.print(
            f"[dim]位置[/] {g.display_name}\n"
            f"[dim]座標[/] {g.lat:.5f}, {g.lon:.5f}  [dim]({g.source})[/]"
        )
    else:
        console.print("[red]位置: ジオコード失敗[/]")

    if result.weather:
        w = result.weather
        t = Table(title="気象（過去日数）", box=box.ROUNDED, show_lines=False)
        t.add_column("指標", style="cyan")
        t.add_column("値", justify="right")
        t.add_row("期間", f"{w.days_past} 日")
        t.add_row("降水合計", f"{w.precip_sum_mm} mm" if w.precip_sum_mm is not None else "—")
        t.add_row("最高温（平均）", f"{w.tmax_c_mean:.1f} °C" if w.tmax_c_mean is not None else "—")
        t.add_row("最低温（平均）", f"{w.tmin_c_mean:.1f} °C" if w.tmin_c_mean is not None else "—")
        t.add_row("ソース", w.source)
        console.print(t)
    else:
        console.print("[yellow]気象: 未取得[/]")

    if result.ndvi and result.ndvi.mean_ndvi is not None:
        n = result.ndvi.mean_ndvi
        bar_w = max(1, min(40, int(n * 40)))
        bar = "█" * bar_w + "░" * (40 - bar_w)
        style = "green" if n >= 0.35 else "yellow" if n >= 0.2 else "red"
        latest = getattr(result.ndvi, "latest_scene_date", None)
        latest_line = f"\n[dim]直近シーン日[/] {latest}" if latest else ""
        console.print(
            Panel(
                f"[{style}]{bar}[/]\n[bold]{n:.3f}[/]  [dim](scenes={result.ndvi.image_count}, {result.ndvi.source})[/]"
                f"{latest_line}",
                title="NDVI",
                border_style=style,
            )
        )
    elif result.ndvi:
        console.print(f"[yellow]NDVI 不安定 / 欠測[/]  [dim](scenes={result.ndvi.image_count})[/]")
    else:
        console.print("[yellow]NDVI: GEE 未取得[/]")

    jx = getattr(result, "jaxa_supplement", None)
    if jx is not None:
        bits = []
        if jx.precip_sum_mm is not None:
            bits.append(f"GSMaP 期間合計 ≈ {jx.precip_sum_mm:.1f} mm")
        if jx.precip_mean_daily_mm is not None:
            bits.append(f"GSMaP 日平均 ≈ {jx.precip_mean_daily_mm:.3f} mm/日")
        if jx.smc_mean is not None:
            bits.append(f"AMSR2 SMC 平均 ≈ {jx.smc_mean:.3f}")
        body = "\n".join(bits) if bits else "（主要指標なし）"
        if jx.notes:
            body += "\n\n" + "\n".join(f"• {n}" for n in jx.notes)
        if getattr(jx, "precip_thumb_data_uri", None) or getattr(jx, "smc_thumb_data_uri", None):
            body += (
                "\n\n[dim]※ 降水·土壌水分の地図サムネは HTML レポートの JAXA セクションに表示されます。[/]"
            )
        console.print(
            Panel(
                body,
                title="JAXA 補完（GSMaP / SMC）",
                border_style="blue",
            )
        )
    elif getattr(result, "supplement_reason", None) == "sentinel_weak_jaxa_unavailable":
        console.print("[yellow]JAXA 補完: jaxa-earth 未インストール（.env で FARM_AGENT_USE_JAXA=1）[/]")
    elif getattr(result, "supplement_reason", None) == "cli_jaxa_unavailable":
        console.print("[yellow]JAXA (--jaxa): jaxa-earth 未インストール[/]")

    if result.errors:
        for e in result.errors:
            console.print(f"[red]•[/] {e}")

    if result.recommendation:
        console.print(Panel(Markdown(result.recommendation.text), title="提案", border_style="cyan"))
