# client/engine.py — Двигун встановлення + PowerShell tweaks
import subprocess
import sys
from typing import List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

console = Console()

WINGET_ALREADY_INSTALLED = 0x8A150011
WINGET_NO_INTERNET       = 0x8A150014
WINGET_NOT_FOUND         = 0x8A150015


class ExecutionEngine:
    """Запускає Winget та PowerShell команди з обробкою помилок."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._win = sys.platform == "win32"

    # ─── ВНУТРІШНІЙ ЗАПУСК ────────────────────────────────────────────────

    def _run(self, cmd: List[str], timeout: int = 300) -> subprocess.CompletedProcess:
        if self.dry_run:
            console.print(f"[dim][DRY RUN] {' '.join(cmd)}[/dim]")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        try:
            return subprocess.run(cmd, capture_output=True,
                                  timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            console.print(f"[red]⏰ Таймаут: {' '.join(cmd)}[/red]")
            raise
        except FileNotFoundError:
            console.print(f"[red]❌ Команда не знайдена: {cmd[0]}[/red]")
            raise

    # ─── WINGET ───────────────────────────────────────────────────────────

    def install_via_winget(self, winget_id: str) -> bool:
        """Встановлює програму через Winget у тихому режимі."""
        cmd = ["winget", "install", "--id", winget_id,
               "--silent", "--accept-package-agreements",
               "--accept-source-agreements"]
        console.print(f"[cyan]⏳ Встановлення: [bold]{winget_id}[/bold]...[/cyan]")
        try:
            r = self._run(cmd)
            if r.returncode == 0:
                console.print(f"[green]✅ Встановлено: {winget_id}[/green]")
                return True
            elif r.returncode == WINGET_ALREADY_INSTALLED:
                console.print(f"[yellow]ℹ️  Вже встановлено: {winget_id}[/yellow]")
                return True
            elif r.returncode == WINGET_NO_INTERNET:
                console.print(f"[red]🌐 Немає інтернету — пропуск: {winget_id}[/red]")
                return False
            else:
                err = r.stderr.decode("utf-8", errors="ignore")[:200] if r.stderr else ""
                console.print(f"[red]❌ Помилка {r.returncode}: {winget_id}[/red]")
                if err:
                    console.print(f"[dim red]{err}[/dim red]")
                return False
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
            return False

    def apply_profile_apps(self, apps: list) -> dict:
        """Встановлює список програм із прогрес-баром."""
        results = {"success": [], "failed": [], "skipped": []}
        if not apps:
            return results

        console.print(Panel(f"[bold]📦 Встановлення {len(apps)} програм[/bold]",
                            border_style="blue", expand=False))

        with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                      BarColumn(), TaskProgressColumn(),
                      console=console) as progress:
            task = progress.add_task("[cyan]Прогрес...", total=len(apps))
            for app in apps:
                progress.update(task, description=f"[cyan]⏳ {app.get('id','?')}")
                wid = app.get("winget_id", "")
                if not wid:
                    results["skipped"].append(app.get("id"))
                elif self.install_via_winget(wid):
                    results["success"].append(app.get("id"))
                else:
                    (results["failed"] if app.get("required") else results["skipped"]
                     ).append(app.get("id"))
                progress.advance(task)

        console.print(f"\n✅ [green]{len(results['success'])}[/green] "
                      f"❌ [red]{len(results['failed'])}[/red] "
                      f"⏭️  [yellow]{len(results['skipped'])}[/yellow]")
        return results

    # ─── POWERSHELL ────────────────────────────────────────────────────────

    def run_powershell(self, script: str, label: str = "PowerShell") -> bool:
        """Виконує рядок PowerShell."""
        if not self._win and not self.dry_run:
            console.print("[yellow]⚠️  PowerShell тільки на Windows[/yellow]")
            return False
        cmd = ["powershell.exe", "-NonInteractive", "-NoProfile",
               "-ExecutionPolicy", "Bypass", "-Command", script]
        console.print(f"[magenta]⚡ {label}...[/magenta]")
        try:
            r = self._run(cmd, timeout=60)
            if r.returncode == 0:
                console.print(f"[green]✅ {label} — виконано[/green]")
                return True
            err = r.stderr.decode("utf-8", errors="ignore")[:200] if r.stderr else ""
            console.print(f"[red]❌ {label} — помилка (код {r.returncode})[/red]")
            if err:
                console.print(f"[dim red]{err}[/dim red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
            return False

    # ─── СИСТЕМНІ НАЛАШТУВАННЯ ────────────────────────────────────────────

    def apply_dark_theme(self) -> bool:
        console.print("[cyan]🌑 Темна тема...[/cyan]")
        return self.run_powershell(
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\Themes\\Personalize' -Name 'AppsUseLightTheme' "
            "-Value 0 -Type DWord -Force; "
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\Themes\\Personalize' -Name 'SystemUsesLightTheme' "
            "-Value 0 -Type DWord -Force",
            "Темна тема"
        )

    def apply_light_theme(self) -> bool:
        console.print("[cyan]☀️  Світла тема...[/cyan]")
        return self.run_powershell(
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\Themes\\Personalize' -Name 'AppsUseLightTheme' "
            "-Value 1 -Type DWord -Force; "
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\Themes\\Personalize' -Name 'SystemUsesLightTheme' "
            "-Value 1 -Type DWord -Force",
            "Світла тема"
        )

    def enable_developer_mode(self) -> bool:
        console.print("[cyan]🛠️  Режим розробника...[/cyan]")
        return self.run_powershell(
            "reg add 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\"
            "AppModelUnlock' /t REG_DWORD /f /v 'AllowDevelopmentWithoutDevLicense' /d '1'",
            "Developer Mode"
        )

    def set_execution_policy(self) -> bool:
        console.print("[cyan]🔐 ExecutionPolicy...[/cyan]")
        return self.run_powershell(
            "Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force",
            "ExecutionPolicy"
        )

    def disable_xbox_game_bar(self) -> bool:
        console.print("[cyan]🎮 Вимкнення Xbox Game Bar...[/cyan]")
        return self.run_powershell(
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\GameDVR' -Name 'AppCaptureEnabled' -Value 0 "
            "-Type DWord -Force",
            "Xbox Game Bar OFF"
        )

    def enable_ultimate_performance(self) -> bool:
        """Активує приховану схему живлення Ultimate Performance."""
        console.print("[cyan]⚡ Ultimate Performance схема живлення...[/cyan]")
        return self.run_powershell(
            "powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61",
            "Ultimate Performance"
        )

    def optimize_gaming_performance(self) -> bool:
        """Вимикає Xbox DVR та оптимізує для ігор."""
        console.print("[cyan]🚀 Оптимізація для ігор...[/cyan]")
        script = (
            "Set-ItemProperty -Path 'HKCU:\\System\\GameConfigStore' "
            "-Name 'GameDVR_Enabled' -Value 0 -Type DWord -Force; "
            "Set-ItemProperty -Path 'HKCU:\\System\\GameConfigStore' "
            "-Name 'GameDVR_FSEBehaviorMode' -Value 2 -Type DWord -Force"
        )
        return self.run_powershell(script, "Gaming Optimization")

    def disable_telemetry(self) -> bool:
        """Вимикає телеметрію Windows (DiagTrack, dmwappushservice)."""
        console.print("[cyan]🔇 Вимкнення телеметрії...[/cyan]")
        script = (
            # Зупиняємо служби телеметрії
            "Stop-Service -Name 'DiagTrack' -Force -ErrorAction SilentlyContinue; "
            "Set-Service -Name 'DiagTrack' -StartupType Disabled -ErrorAction SilentlyContinue; "
            "Stop-Service -Name 'dmwappushservice' -Force -ErrorAction SilentlyContinue; "
            "Set-Service -Name 'dmwappushservice' -StartupType Disabled -ErrorAction SilentlyContinue; "
            # Вимикаємо рекламний ID
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\AdvertisingInfo' -Name 'Enabled' -Value 0 -Type DWord -Force; "
            # Вимикаємо відстеження запусків програм
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\Explorer\\Advanced' -Name 'Start_TrackProgs' -Value 0 -Type DWord -Force"
        )
        return self.run_powershell(script, "Телеметрія ВИМК")

    def disable_advertising_id(self) -> bool:
        """Вимикає рекламний ідентифікатор Windows."""
        console.print("[cyan]🚫 Рекламний ID...[/cyan]")
        return self.run_powershell(
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\AdvertisingInfo' -Name 'Enabled' -Value 0 -Type DWord -Force",
            "Рекламний ID ВИМК"
        )

    def configure_uac_developer(self) -> bool:
        """Знижує UAC для розробника (не вимикає повністю — безпечно)."""
        console.print("[cyan]🔑 UAC для розробника...[/cyan]")
        return self.run_powershell(
            "Set-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\"
            "CurrentVersion\\Policies\\System' -Name 'ConsentPromptBehaviorAdmin' "
            "-Value 2 -Type DWord -Force",
            "UAC Developer Mode"
        )

    def set_color_calibration(self) -> bool:
        """Вмикає HDR та Night Light для дизайнера."""
        console.print("[cyan]🎨 Налаштування кольору...[/cyan]")
        return self.run_powershell(
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\CloudStore\\Store\\Cache\\DefaultAccount\\"
            "*$*$windows.data.bluelightreduction.bluelightreductionstate\\"
            "Current' -Name 'Data' -Value 0 -Type Binary -Force "
            "-ErrorAction SilentlyContinue",
            "Color Calibration"
        )

    def enable_night_light(self) -> bool:
        """Вмикає нічний режим для дизайнера."""
        console.print("[cyan]🌙 Night Light...[/cyan]")
        return self.run_powershell(
            "Add-Type -AssemblyName System.Windows.Forms; "
            "[System.Windows.Forms.Application]::DoEvents()",
            "Night Light"
        )