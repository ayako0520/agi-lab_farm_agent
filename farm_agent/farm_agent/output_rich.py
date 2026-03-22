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
    console.print(Panel.fit(title, border_style="bright_magenta"))

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
        console.print(
            Panel(
                f"[{style}]{bar}[/]\n[bold]{n:.3f}[/]  [dim](scenes={result.ndvi.image_count}, {result.ndvi.source})[/]",
                title="NDVI",
                border_style=style,
            )
        )
    elif result.ndvi:
        console.print(f"[yellow]NDVI 不安定 / 欠測[/]  [dim](scenes={result.ndvi.image_count})[/]")
    else:
        console.print("[yellow]NDVI: GEE 未取得[/]")

    if result.errors:
        for e in result.errors:
            console.print(f"[red]•[/] {e}")

    if result.recommendation:
        console.print(Panel(Markdown(result.recommendation.text), title="提案", border_style="cyan"))
