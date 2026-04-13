import typer
import httpx
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from auditor import HardwareAuditor
from engine import ExecutionEngine
from injector import ConfigInjector

cli = typer.Typer(add_completion=False)
console = Console()
DEFAULT_SERVER = "http://localhost:8000"

def print_banner():
    console.print("[bold cyan]  AutoDeploy v1.0.0 — Windows 11[/bold cyan]")

@cli.command("audit")
def audit_command():
    """Аудит апаратного забезпечення."""
    print_banner()
    auditor = HardwareAuditor()
    result = auditor.run_audit()
    console.print(f"Профіль: [cyan]{result['recommended_profile']}[/cyan]")

@cli.command("deploy")
def deploy_command(
    persona: Optional[str] = typer.Option(None, help="developer / gamer / designer"),
    server: Optional[str] = typer.Option(None, help="URL сервера"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """Повний цикл розгортання."""
    if persona is None:
        persona = "developer"
    if server is None:
        server = DEFAULT_SERVER

    print_banner()
    console.print(f"[cyan]Персона: {persona}[/cyan]")

    auditor = HardwareAuditor()
    hw_info = auditor.run_audit()

    try:
        response = httpx.get(f"{server}/profile/{persona}", timeout=10)
        if response.status_code != 200:
            console.print(f"[red]Помилка сервера: {response.status_code}[/red]")
            raise typer.Exit(1)
        profile = response.json()
        console.print(f"[green]Профіль: {profile['display_name']}[/green]")
    except httpx.ConnectError:
        console.print(f"[red]Сервер недоступний: {server}[/red]")
        raise typer.Exit(1)

    manifests_resp = httpx.get(f"{server}/manifests", timeout=10)
    manifest_map = {m["id"]: m for m in manifests_resp.json()["manifests"]}

    apps_to_install = []
    for app_ref in profile["apps"]:
        aid = app_ref["id"]
        if aid in manifest_map:
            apps_to_install.append({
                "id": aid,
                "winget_id": manifest_map[aid]["winget_id"],
                "required": app_ref["required"]
            })

    engine = ExecutionEngine(dry_run=dry_run)
    install_results = engine.apply_profile_apps(apps_to_install)

    ps_methods = {
        "apply_dark_theme": engine.apply_dark_theme,
        "apply_light_theme": engine.apply_light_theme,
        "enable_developer_mode": engine.enable_developer_mode,
        "disable_xbox_game_bar": engine.disable_xbox_game_bar,
        "set_execution_policy": engine.set_execution_policy,
    }
    for script_name in profile.get("powershell_scripts", []):
        if script_name in ps_methods:
            ps_methods[script_name]()

    injector = ConfigInjector()
    injector.inject_all(profile.get("configs", {}))

    console.print(f"[green]Готово! Встановлено: {len(install_results['success'])}[/green]")

@cli.command("install")
def install_command(
    app_name: str = typer.Argument(..., help="ID програми: vscode, chrome..."),
    server: Optional[str] = typer.Option(None),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """Встановити одну програму."""
    if server is None:
        server = DEFAULT_SERVER
    print_banner()
    try:
        response = httpx.get(f"{server}/manifests/{app_name}", timeout=10)
        if response.status_code == 404:
            console.print(f"[red]Не знайдено: {app_name}[/red]")
            raise typer.Exit(1)
        manifest = response.json()
        engine = ExecutionEngine(dry_run=dry_run)
        engine.install_via_winget(manifest["winget_id"])
    except httpx.ConnectError:
        console.print(f"[red]Сервер недоступний[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    cli()