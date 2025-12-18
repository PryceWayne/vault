"""Vault CLI - Pokemon TCG collection value tracker."""

import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from . import database, importer, api

console = Console()


def format_currency(value: float | None) -> str:
    """Format a value as currency."""
    if value is None:
        return "-"
    return f"${value:,.2f}"


def format_change(value: float | None, include_pct: bool = False, pct: float | None = None) -> Text:
    """Format a price change with color."""
    if value is None or value == 0:
        return Text("-", style="dim")

    if value > 0:
        text = f"+{format_currency(value)}"
        if include_pct and pct is not None:
            text += f" ({pct:+.1f}%)"
        return Text(text, style="green")
    else:
        text = format_currency(value)
        if include_pct and pct is not None:
            text += f" ({pct:+.1f}%)"
        return Text(text, style="red")


@click.group()
@click.version_option()
def main():
    """Vault - Pokemon TCG collection value tracker."""
    pass


@main.command(name="import")
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
def import_cmd(csv_file: Path):
    """Import items from a Collectr CSV export."""
    console.print(f"\n[bold]Importing from:[/bold] {csv_file}\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Importing...", total=None)

        def update_progress(current, total, name):
            progress.update(task, completed=current, total=total, description=f"Importing: {name[:40]}")

        stats = importer.import_csv(csv_file, progress_callback=update_progress)

    # Show results
    console.print()
    table = Table(title="Import Results", show_header=False, box=None)
    table.add_column("Stat", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total rows", str(stats["total"]))
    table.add_row("Imported", str(stats["imported"]))
    table.add_row("Cards", str(stats["cards"]))
    table.add_row("Sealed products", str(stats["sealed"]))

    console.print(table)

    if stats["errors"]:
        console.print(f"\n[yellow]Warnings ({len(stats['errors'])}):[/yellow]")
        for error in stats["errors"][:5]:
            console.print(f"  {error}")
        if len(stats["errors"]) > 5:
            console.print(f"  ... and {len(stats['errors']) - 5} more")

    console.print("\n[green]Import complete![/green]")
    console.print("[dim]Run 'vault update' to fetch current prices from the API.[/dim]\n")


@main.command()
def update():
    """Refresh prices from the Pokemon TCG API (cards only)."""
    database.init_db()
    items = database.get_items_needing_update()

    if not items:
        console.print("[yellow]No cards found to update.[/yellow]")
        return

    cards = [i for i in items if not i["is_sealed"]]
    console.print(f"\n[bold]Updating prices for {len(cards)} cards...[/bold]\n")

    updated = 0
    failed = 0
    failed_items = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Updating...", total=len(cards))

        for item in cards:
            progress.update(task, advance=1, description=f"Updating: {item['name'][:40]}")

            api_id, price = api.lookup_and_price_card(
                name=item["name"],
                set_name=item["set_name"],
                number=item["card_number"],
                existing_api_id=item["api_id"],
            )

            if price is not None:
                if api_id and not item["api_id"]:
                    database.update_item_api_id(item["id"], api_id)
                database.record_price(item["id"], price)
                updated += 1
            else:
                failed += 1
                failed_items.append(item)

    console.print()
    console.print(f"[green]Updated:[/green] {updated} cards")
    console.print(f"[yellow]Failed:[/yellow] {failed} cards")
    console.print(f"[dim]API calls this session: {api.get_call_count()}[/dim]")

    if failed_items:
        console.print("\n[yellow]Could not find prices for:[/yellow]")
        for item in failed_items[:10]:
            console.print(f"  - {item['name']} ({item['set_name'] or 'no set'})")
        if len(failed_items) > 10:
            console.print(f"  ... and {len(failed_items) - 10} more")

    console.print()


@main.command()
def summary():
    """Show portfolio summary with total value and daily change."""
    database.init_db()
    stats = database.get_summary_stats()

    if stats["item_count"] == 0:
        console.print("[yellow]No items in vault. Run 'vault import <csv>' first.[/yellow]")
        return

    # Build summary panel
    lines = []
    lines.append(f"[bold]Total Value:[/bold]  {format_currency(stats['total_value'])}")

    if stats["daily_change"] != 0:
        change_color = "green" if stats["daily_change"] > 0 else "red"
        sign = "+" if stats["daily_change"] > 0 else ""
        lines.append(
            f"[bold]Daily Change:[/bold] [{change_color}]{sign}{format_currency(stats['daily_change'])} "
            f"({sign}{stats['daily_change_pct']:.1f}%)[/{change_color}]"
        )

    if stats["total_cost"] and stats["total_profit"] is not None:
        profit_color = "green" if stats["total_profit"] >= 0 else "red"
        sign = "+" if stats["total_profit"] >= 0 else ""
        lines.append(f"[bold]Cost Basis:[/bold]  {format_currency(stats['total_cost'])}")
        lines.append(f"[bold]Total P&L:[/bold]    [{profit_color}]{sign}{format_currency(stats['total_profit'])}[/{profit_color}]")

    lines.append("")
    lines.append(f"[dim]Items: {stats['item_count']} ({stats['card_count']} cards, {stats['sealed_count']} sealed)[/dim]")
    lines.append(f"[dim]Total quantity: {stats['total_quantity']}[/dim]")

    panel = Panel(
        "\n".join(lines),
        title="[bold blue]Vault Summary[/bold blue]",
        border_style="blue",
    )
    console.print()
    console.print(panel)
    console.print()


@main.command(name="list")
@click.option("--sort", type=click.Choice(["value", "change", "name"]), default="value", help="Sort order")
def list_cmd(sort: str):
    """List all items with current values."""
    database.init_db()
    items = database.get_all_items()

    if not items:
        console.print("[yellow]No items in vault.[/yellow]")
        return

    # Calculate values and changes
    for item in items:
        item["total_value"] = (item["current_price"] or 0) * item["quantity"]
        if item["previous_price"] and item["current_price"]:
            item["change"] = item["current_price"] - item["previous_price"]
            item["change_pct"] = (item["change"] / item["previous_price"]) * 100
        else:
            item["change"] = 0
            item["change_pct"] = 0

    # Sort
    if sort == "value":
        items.sort(key=lambda x: x["total_value"], reverse=True)
    elif sort == "change":
        items.sort(key=lambda x: x["change_pct"], reverse=True)
    else:
        items.sort(key=lambda x: x["name"].lower())

    # Build table
    table = Table(title="Collection", show_lines=False)
    table.add_column("ID", style="dim", width=4)
    table.add_column("Name", max_width=35)
    table.add_column("Set", max_width=20)
    table.add_column("Qty", justify="right", width=4)
    table.add_column("Price", justify="right")
    table.add_column("Value", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("Type", width=6)

    for item in items:
        change_text = format_change(item["change"], include_pct=True, pct=item["change_pct"])
        type_badge = "[cyan]sealed[/cyan]" if item["is_sealed"] else "[green]card[/green]"

        table.add_row(
            str(item["id"]),
            item["name"][:35],
            (item["set_name"] or "-")[:20],
            str(item["quantity"]),
            format_currency(item["current_price"]),
            format_currency(item["total_value"]),
            change_text,
            type_badge,
        )

    console.print()
    console.print(table)
    console.print()


@main.command()
@click.option("--days", default=7, help="Number of days to look back")
def movers(days: int):
    """Show biggest gainers and losers by percentage change."""
    database.init_db()
    items = database.get_all_items()

    if not items:
        console.print("[yellow]No items in vault.[/yellow]")
        return

    # Calculate changes
    movers_list = []
    for item in items:
        if item["current_price"] and item["previous_price"]:
            change = item["current_price"] - item["previous_price"]
            change_pct = (change / item["previous_price"]) * 100
            movers_list.append({
                **item,
                "change": change,
                "change_pct": change_pct,
            })

    if not movers_list:
        console.print("[yellow]No price history available. Run 'vault update' to fetch prices.[/yellow]")
        return

    # Sort by absolute change percentage
    movers_list.sort(key=lambda x: abs(x["change_pct"]), reverse=True)

    # Split into gainers and losers
    gainers = [m for m in movers_list if m["change_pct"] > 0][:5]
    losers = [m for m in movers_list if m["change_pct"] < 0][:5]

    if gainers:
        console.print("\n[bold green]Top Gainers[/bold green]")
        table = Table(show_header=True, box=None)
        table.add_column("Name", max_width=30)
        table.add_column("Change", justify="right")
        table.add_column("Price", justify="right")

        for item in gainers:
            table.add_row(
                item["name"][:30],
                f"[green]+{item['change_pct']:.1f}%[/green]",
                format_currency(item["current_price"]),
            )
        console.print(table)

    if losers:
        console.print("\n[bold red]Top Losers[/bold red]")
        table = Table(show_header=True, box=None)
        table.add_column("Name", max_width=30)
        table.add_column("Change", justify="right")
        table.add_column("Price", justify="right")

        for item in losers:
            table.add_row(
                item["name"][:30],
                f"[red]{item['change_pct']:.1f}%[/red]",
                format_currency(item["current_price"]),
            )
        console.print(table)

    console.print()


@main.command()
@click.option("--threshold", default=10, help="Percentage threshold for alerts")
def alerts(threshold: int):
    """Show items that moved more than X% since last check."""
    database.init_db()
    items = database.get_all_items()

    alerts_list = []
    for item in items:
        if item["current_price"] and item["previous_price"]:
            change_pct = ((item["current_price"] - item["previous_price"]) / item["previous_price"]) * 100
            if abs(change_pct) >= threshold:
                alerts_list.append({
                    **item,
                    "change_pct": change_pct,
                })

    if not alerts_list:
        console.print(f"[green]No items moved more than {threshold}%[/green]")
        return

    console.print(f"\n[bold]Items that moved >{threshold}%[/bold]\n")

    table = Table(show_header=True)
    table.add_column("Name", max_width=30)
    table.add_column("Set", max_width=15)
    table.add_column("Change", justify="right")
    table.add_column("Old Price", justify="right")
    table.add_column("New Price", justify="right")

    for item in sorted(alerts_list, key=lambda x: abs(x["change_pct"]), reverse=True):
        color = "green" if item["change_pct"] > 0 else "red"
        table.add_row(
            item["name"][:30],
            (item["set_name"] or "-")[:15],
            f"[{color}]{item['change_pct']:+.1f}%[/{color}]",
            format_currency(item["previous_price"]),
            format_currency(item["current_price"]),
        )

    console.print(table)
    console.print()


@main.command()
@click.argument("item_id", type=int)
def history(item_id: int):
    """Show price history for a specific item."""
    database.init_db()
    item = database.get_item_by_id(item_id)

    if not item:
        console.print(f"[red]Item {item_id} not found.[/red]")
        return

    prices = database.get_price_history(item_id, limit=30)

    if not prices:
        console.print(f"[yellow]No price history for '{item['name']}'[/yellow]")
        return

    console.print(f"\n[bold]Price History: {item['name']}[/bold]")
    if item["set_name"]:
        console.print(f"[dim]Set: {item['set_name']}[/dim]")
    console.print()

    table = Table(show_header=True)
    table.add_column("Date", width=20)
    table.add_column("Price", justify="right")
    table.add_column("Change", justify="right")

    prev_price = None
    for i, record in enumerate(reversed(prices)):
        change_text = Text("-", style="dim")
        if prev_price is not None:
            change = record["price"] - prev_price
            if change != 0:
                change_text = format_change(change)

        table.add_row(
            record["timestamp"][:19],
            format_currency(record["price"]),
            change_text,
        )
        prev_price = record["price"]

    console.print(table)
    console.print()


@main.command()
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path")
def export(output: Path | None):
    """Export current data to CSV."""
    database.init_db()
    items = database.get_all_items()

    if not items:
        console.print("[yellow]No items to export.[/yellow]")
        return

    if output is None:
        output = Path(f"vault_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

    fieldnames = [
        "id", "name", "set_name", "card_number", "rarity", "variance",
        "quantity", "cost_basis", "current_price", "total_value",
        "is_sealed", "portfolio_name", "grade", "condition", "notes"
    ]

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for item in items:
            total_value = (item["current_price"] or 0) * item["quantity"]
            writer.writerow({
                "id": item["id"],
                "name": item["name"],
                "set_name": item["set_name"],
                "card_number": item["card_number"],
                "rarity": item["rarity"],
                "variance": item["variance"],
                "quantity": item["quantity"],
                "cost_basis": item["cost_basis"],
                "current_price": item["current_price"],
                "total_value": total_value,
                "is_sealed": "yes" if item["is_sealed"] else "no",
                "portfolio_name": item["portfolio_name"],
                "grade": item["grade"],
                "condition": item["condition"],
                "notes": item["notes"],
            })

    console.print(f"[green]Exported {len(items)} items to {output}[/green]")


@main.command()
@click.option("--port", "-p", default=5000, help="Port to run on")
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
def web(port: int, host: str):
    """Launch the web dashboard."""
    from . import web as web_module
    import webbrowser

    database.init_db()
    url = f"http://{host}:{port}"

    console.print(f"\n[bold blue]Starting Vault Web Dashboard[/bold blue]")
    console.print(f"[green]Open your browser to:[/green] {url}")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    # Open browser automatically
    webbrowser.open(url)

    # Run the server
    web_module.run_server(host=host, port=port)


if __name__ == "__main__":
    main()
