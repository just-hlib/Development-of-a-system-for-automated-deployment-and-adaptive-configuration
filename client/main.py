# client/main.py — CLI точка входу (Typer)
# Commands: audit | deploy | install | list | tweak | apply | tui
import json
import typer
import httpx
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from auditor  import HardwareAuditor
from engine   import ExecutionEngine, save_build, load_build, is_app_installed
from injector import ConfigInjector

cli = typer.Typer(
    add_completion=False,
    help="AutoDeploy v2 — Windows 11 Auto-Deploy System",
)
console = Console()
DEFAULT_SERVER = "http://localhost:8000"


# ── Banner ─────────────────────────────────────────────────────────────────────

def banner():
    console.print(Panel(
        "[bold cyan]  ██████╗ ██╗   ██╗████████╗ ██████╗ \n"
        "  ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗\n"
        "  ███████║██║   ██║   ██║   ██║   ██║\n"
        "  ██╔══██║██║   ██║   ██║   ██║   ██║\n"
        "  ██║  ██║╚██████╔╝   ██║   ╚██████╔╝\n"
        "  ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ [/bold cyan]\n"
        "[dim]  Windows 11 Auto-Deploy System v2.0[/dim]",
        border_style="bright_blue", expand=False,
    ))


# ── Server helpers ─────────────────────────────────────────────────────────────

def _get_profile(persona: str, server: str) -> dict:
    try:
        r = httpx.get(f"{server}/profile/{persona}", timeout=10)
        if r.status_code == 404:
            console.print(f"[red]❌ Persona '{persona}' not found[/red]")
            raise typer.Exit(1)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        console.print(
            f"[red]❌ Server unreachable: {server}[/red]\n"
            "[yellow]💡 Start it: cd server && uvicorn main:app --reload[/yellow]"
        )
        raise typer.Exit(1)


def _get_manifests(server: str) -> dict:
    r = httpx.get(f"{server}/manifests", timeout=10)
    return {m["id"]: m for m in r.json()["manifests"]}


# ══════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

@cli.command("audit")
def cmd_audit():
    """🔍 Hardware audit — shows RAM/CPU/Disk and recommended profile."""
    banner()
    info = HardwareAuditor().run_audit()
    console.print(
        f"\n[bold]📋 Recommended profile: "
        f"[cyan]{info['recommended_profile']}[/cyan][/bold]"
    )


@cli.command("deploy")
def cmd_deploy(
    persona: Optional[str] = typer.Option(
        None, help="developer / gamer / designer / common"
    ),
    server:  Optional[str] = typer.Option(None, help="Server URL"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate without changes"),
    save:    Optional[Path] = typer.Option(
        None, "--save", help="Save the build to a .json file after deploy"
    ),
):
    """🚀 Full deploy: audit → profile → install → tweaks."""
    persona = persona or "developer"
    server  = server  or DEFAULT_SERVER
    banner()

    # Step 1: audit
    console.print("\n[bold blue]━━━ Step 1/4: Hardware Audit ━━━[/bold blue]")
    hw = HardwareAuditor().run_audit()

    # Step 2: profile
    console.print(f"\n[bold blue]━━━ Step 2/4: Profile '{persona}' ━━━[/bold blue]")
    profile = _get_profile(persona, server)
    console.print(f"[green]✅ {profile['display_name']} — {profile['description']}[/green]")

    # Step 3: install
    console.print(f"\n[bold blue]━━━ Step 3/4: Install Apps ━━━[/bold blue]")
    manifest_map = _get_manifests(server)
    apps = []
    for ref in profile["apps"]:
        aid = ref["id"]
        if aid in manifest_map:
            apps.append({
                "id":        aid,
                "winget_id": manifest_map[aid]["winget_id"],
                "required":  ref["required"],
            })

    engine  = ExecutionEngine(dry_run=dry_run)
    results = engine.apply_profile_apps(apps)

    # Step 4: tweaks
    console.print(f"\n[bold blue]━━━ Step 4/4: System Tweaks ━━━[/bold blue]")
    engine._run_scripts(profile.get("powershell_scripts", []))
    ConfigInjector().inject_all(profile.get("configs", {}))

    # Optional: save build file
    if save:
        save_build(
            selected_app_ids=apps,
            hw_profile=hw["recommended_profile"],
            persona=persona,
            output_path=save,
            powershell_scripts=profile.get("powershell_scripts", []),
        )

    console.print(Panel(
        f"[bold green]🎉 Deploy complete![/bold green]\n\n"
        f"Persona:         [cyan]{profile['display_name']}[/cyan]\n"
        f"HW Profile:      [cyan]{hw['recommended_profile']}[/cyan]\n"
        f"Installed:       [green]{len(results['success'])}[/green]\n"
        f"Failed:          [red]{len(results['failed'])}[/red]\n"
        f"Skipped:         [yellow]{len(results['skipped'])}[/yellow]",
        border_style="green", expand=False,
    ))


@cli.command("apply")
def cmd_apply(
    file:    Path = typer.Option(..., "--file", "-f",
                                 help="Path to .json build file"),
    dry_run: bool = typer.Option(False, "--dry-run",
                                 help="Simulate without real changes"),
):
    """
    📂 Apply a saved build file — no server needed.

    Example:
      python main.py apply --file my_build.json
      python main.py apply --file my_build.json --dry-run
    """
    banner()
    try:
        build = load_build(file)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1)

    engine = ExecutionEngine(dry_run=dry_run)
    results = engine.apply_build(build)

    console.print(Panel(
        f"[bold green]🎉 Build applied![/bold green]\n\n"
        f"File:      [cyan]{file}[/cyan]\n"
        f"Persona:   [cyan]{build.get('persona', '?')}[/cyan]\n"
        f"HW Profile:[cyan] {build.get('hw_profile', '?')}[/cyan]\n"
        f"Installed: [green]{len(results['success'])}[/green]\n"
        f"Failed:    [red]{len(results['failed'])}[/red]\n"
        f"Skipped:   [yellow]{len(results['skipped'])}[/yellow]",
        border_style="green", expand=False,
    ))


@cli.command("install")
def cmd_install(
    app_name: str          = typer.Argument(..., help="App ID: vscode, chrome, steam..."),
    server:   Optional[str]= typer.Option(None),
    dry_run:  bool         = typer.Option(False, "--dry-run"),
):
    """📦 Install a single app by ID."""
    server = server or DEFAULT_SERVER
    banner()
    console.print(f"[cyan]🔍 Looking up: [bold]{app_name}[/bold]...[/cyan]")
    try:
        r = httpx.get(f"{server}/manifests/{app_name}", timeout=10)
        if r.status_code == 404:
            console.print(f"[red]❌ '{app_name}' not found. Check: python main.py list[/red]")
            raise typer.Exit(1)
        m = r.json()
        ExecutionEngine(dry_run=dry_run).install_via_winget(m["winget_id"])
    except httpx.ConnectError:
        console.print(f"[red]❌ Server unreachable: {server}[/red]")
        raise typer.Exit(1)


@cli.command("list")
def cmd_list(
    server:   Optional[str] = typer.Option(None),
    category: Optional[str] = typer.Option(None, help="Filter by category"),
):
    """📋 List all available apps."""
    server = server or DEFAULT_SERVER
    banner()
    try:
        url = f"{server}/manifests"
        if category:
            url += f"?category={category}"
        r    = httpx.get(url, timeout=10)
        data = r.json()

        t = Table(
            title=f"Available Apps ({data['total']})",
            box=box.ROUNDED, border_style="blue",
            header_style="bold magenta",
        )
        t.add_column("ID",       style="cyan",  min_width=14)
        t.add_column("Name",     style="white", min_width=22)
        t.add_column("Category", style="green", min_width=14)
        t.add_column("Winget ID",style="dim",   min_width=30)
        t.add_column("Size",     justify="right")

        for m in data["manifests"]:
            t.add_row(
                m["id"], m["name"], m["category"],
                m["winget_id"], f"{m.get('size_mb','?')} MB",
            )
        console.print(t)
    except httpx.ConnectError:
        console.print(f"[red]❌ Server unreachable: {server}[/red]")
        raise typer.Exit(1)


@cli.command("tweak")
def cmd_tweak(
    action:  str  = typer.Argument(
        ..., help="dark|light|telemetry|ultimate|devmode|uac|gamebar"
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """⚙️  Apply a single system tweak without full deploy."""
    banner()
    e = ExecutionEngine(dry_run=dry_run)
    actions = {
        "dark":      e.apply_dark_theme,
        "light":     e.apply_light_theme,
        "telemetry": e.disable_telemetry,
        "ultimate":  e.enable_ultimate_performance,
        "devmode":   e.enable_developer_mode,
        "uac":       e.configure_uac_developer,
        "gamebar":   e.disable_xbox_game_bar,
    }
    if action not in actions:
        console.print(
            f"[red]❌ Unknown action: {action}[/red]\n"
            f"[dim]Available: {', '.join(actions.keys())}[/dim]"
        )
        raise typer.Exit(1)
    actions[action]()


@cli.command("tui")
def cmd_tui():
    """🖥  Launch the interactive Textual TUI."""
    try:
        from tui import AutoDeployTUI
        AutoDeployTUI().run()
    except ImportError:
        console.print(
            "[red]❌ Textual not installed.[/red]\n"
            "[dim]Run: pip install textual>=0.61.0[/dim]"
        )
        raise typer.Exit(1)


if __name__ == "__main__":
    cli()