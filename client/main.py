# client/main.py — CLI точка входу
import typer
import httpx
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box
from auditor import HardwareAuditor
from engine import ExecutionEngine
from injector import ConfigInjector

cli = typer.Typer(add_completion=False,
                  help="AutoDeploy v2 — Windows 11 Auto-Deploy System")
console = Console()
DEFAULT_SERVER = "http://localhost:8000"


def banner():
    console.print(Panel(
        "[bold cyan]  ██████╗ ██╗   ██╗████████╗ ██████╗ \n"
        "  ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗\n"
        "  ███████║██║   ██║   ██║   ██║   ██║\n"
        "  ██╔══██║██║   ██║   ██║   ██║   ██║\n"
        "  ██║  ██║╚██████╔╝   ██║   ╚██████╔╝\n"
        "  ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ [/bold cyan]\n"
        "[dim]  Windows 11 Auto-Deploy System v2.0[/dim]",
        border_style="bright_blue", expand=False
    ))


def get_profile_from_server(persona: str, server: str) -> dict:
    """Запитує профіль з FastAPI сервера."""
    try:
        r = httpx.get(f"{server}/profile/{persona}", timeout=10)
        if r.status_code == 404:
            console.print(f"[red]❌ Персона '{persona}' не знайдена[/red]")
            raise typer.Exit(1)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        console.print(f"[red]❌ Сервер недоступний: {server}[/red]")
        console.print("[yellow]💡 Запустіть: cd server && uvicorn main:app --reload[/yellow]")
        raise typer.Exit(1)
    except httpx.TimeoutException:
        console.print("[red]❌ Таймаут підключення[/red]")
        raise typer.Exit(1)


def get_manifests_from_server(server: str) -> dict:
    """Отримує всі маніфести з сервера."""
    r = httpx.get(f"{server}/manifests", timeout=10)
    return {m["id"]: m for m in r.json()["manifests"]}


# ─── КОМАНДИ ──────────────────────────────────────────────────────────────────

@cli.command("audit")
def cmd_audit():
    """🔍 Аудит апаратного забезпечення системи."""
    banner()
    info = HardwareAuditor().run_audit()
    console.print(f"\n[bold]📋 Профіль: [cyan]{info['recommended_profile']}[/cyan][/bold]")


@cli.command("deploy")
def cmd_deploy(
    persona: Optional[str] = typer.Option(None, help="developer / gamer / designer / common"),
    server:  Optional[str] = typer.Option(None, help="URL сервера (за замовч. localhost:8000)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Симуляція без реальних змін"),
):
    """🚀 Повне розгортання: аудит → профіль → встановлення → tweaks."""
    persona = persona or "developer"
    server  = server  or DEFAULT_SERVER
    banner()

    # ── Крок 1: Аудит ────────────────────────────────────────────────────
    console.print("\n[bold blue]━━━ Крок 1/4: Аудит системи ━━━[/bold blue]")
    hw = HardwareAuditor().run_audit()

    # ── Крок 2: Профіль із сервера ───────────────────────────────────────
    console.print(f"\n[bold blue]━━━ Крок 2/4: Профіль '{persona}' ━━━[/bold blue]")
    profile = get_profile_from_server(persona, server)
    console.print(f"[green]✅ {profile['display_name']} — {profile['description']}[/green]")

    # ── Крок 3: Встановлення ─────────────────────────────────────────────
    console.print(f"\n[bold blue]━━━ Крок 3/4: Встановлення програм ━━━[/bold blue]")
    manifest_map = get_manifests_from_server(server)
    apps = []
    for ref in profile["apps"]:
        aid = ref["id"]
        if aid in manifest_map:
            apps.append({"id": aid,
                         "winget_id": manifest_map[aid]["winget_id"],
                         "required": ref["required"]})

    engine = ExecutionEngine(dry_run=dry_run)
    results = engine.apply_profile_apps(apps)

    # ── Крок 4: PowerShell tweaks ─────────────────────────────────────────
    console.print(f"\n[bold blue]━━━ Крок 4/4: Системні налаштування ━━━[/bold blue]")
    ps = {
        "apply_dark_theme":          engine.apply_dark_theme,
        "apply_light_theme":         engine.apply_light_theme,
        "enable_developer_mode":     engine.enable_developer_mode,
        "set_execution_policy":      engine.set_execution_policy,
        "disable_xbox_game_bar":     engine.disable_xbox_game_bar,
        "enable_ultimate_performance": engine.enable_ultimate_performance,
        "optimize_gaming_performance": engine.optimize_gaming_performance,
        "disable_telemetry":         engine.disable_telemetry,
        "configure_uac_developer":   engine.configure_uac_developer,
        "set_color_calibration":     engine.set_color_calibration,
        "enable_night_light":        engine.enable_night_light,
    }
    for name in profile.get("powershell_scripts", []):
        if name in ps:
            ps[name]()
        else:
            console.print(f"[yellow]⚠️  Невідомий скрипт: {name}[/yellow]")

    # Конфіги
    ConfigInjector().inject_all(profile.get("configs", {}))

    # ── Підсумок ──────────────────────────────────────────────────────────
    console.print(Panel(
        f"[bold green]🎉 Розгортання завершено![/bold green]\n\n"
        f"Персона:        [cyan]{profile['display_name']}[/cyan]\n"
        f"Профіль системи:[cyan] {hw['recommended_profile']}[/cyan]\n"
        f"Встановлено:    [green]{len(results['success'])}[/green]\n"
        f"Помилок:        [red]{len(results['failed'])}[/red]\n"
        f"Пропущено:      [yellow]{len(results['skipped'])}[/yellow]",
        border_style="green", expand=False
    ))


@cli.command("install")
def cmd_install(
    app_name: str = typer.Argument(..., help="ID програми: vscode, chrome, steam..."),
    server:  Optional[str] = typer.Option(None),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """📦 Встановити одну програму за ID."""
    server = server or DEFAULT_SERVER
    banner()
    console.print(f"[cyan]🔍 Пошук: [bold]{app_name}[/bold]...[/cyan]")
    try:
        r = httpx.get(f"{server}/manifests/{app_name}", timeout=10)
        if r.status_code == 404:
            console.print(f"[red]❌ '{app_name}' не знайдено[/red]")
            console.print("[dim]Перевір список: python main.py list[/dim]")
            raise typer.Exit(1)
        m = r.json()
        ExecutionEngine(dry_run=dry_run).install_via_winget(m["winget_id"])
    except httpx.ConnectError:
        console.print(f"[red]❌ Сервер недоступний: {server}[/red]")
        raise typer.Exit(1)


@cli.command("list")
def cmd_list(
    server:   Optional[str] = typer.Option(None),
    category: Optional[str] = typer.Option(None, help="Фільтр за категорією"),
):
    """📋 Список усіх доступних програм."""
    server = server or DEFAULT_SERVER
    banner()
    try:
        url = f"{server}/manifests"
        if category:
            url += f"?category={category}"
        r = httpx.get(url, timeout=10)
        data = r.json()

        t = Table(title=f"Доступні програми ({data['total']})",
                  box=box.ROUNDED, border_style="blue",
                  header_style="bold magenta")
        t.add_column("ID",          style="cyan",  min_width=14)
        t.add_column("Назва",       style="white", min_width=22)
        t.add_column("Категорія",   style="green", min_width=14)
        t.add_column("Winget ID",   style="dim",   min_width=30)
        t.add_column("Розмір",      justify="right")

        for m in data["manifests"]:
            size = f"{m.get('size_mb','?')} MB"
            t.add_row(m["id"], m["name"], m["category"], m["winget_id"], size)

        console.print(t)
    except httpx.ConnectError:
        console.print(f"[red]❌ Сервер недоступний: {server}[/red]")
        raise typer.Exit(1)


@cli.command("tweak")
def cmd_tweak(
    action: str = typer.Argument(...,
        help="dark | light | telemetry | ultimate | devmode | uac | gamebar"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """⚙️  Окремий системний твік без повного розгортання."""
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
        console.print(f"[red]❌ Невідома дія: {action}[/red]")
        console.print(f"[dim]Доступні: {', '.join(actions.keys())}[/dim]")
        raise typer.Exit(1)
    actions[action]()


if __name__ == "__main__":
    cli()