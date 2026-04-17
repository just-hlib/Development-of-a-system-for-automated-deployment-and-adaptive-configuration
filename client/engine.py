# client/engine.py — Двигун встановлення + PowerShell tweaks
import subprocess
import sys
from typing import List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

console = Console()

# ─── WINGET EXIT CODES ────────────────────────────────────────────────────────
WINGET_OK               = 0
WINGET_ALREADY_INSTALLED = 0x8A150011
WINGET_NO_INTERNET       = 0x8A150014
WINGET_NOT_FOUND         = 0x8A150015
WINGET_UPGRADE_AVAILABLE = 0x8A150040   # installed, update exists → treat as OK


# ─── UTILITY: ADMIN CHECK ─────────────────────────────────────────────────────

def is_admin() -> bool:
    """
    Returns True if the current process has Administrator privileges on Windows.
    Always returns False on non-Windows platforms (used for cross-platform safety).

    Required for:
      - powercfg -duplicatescheme  (Ultimate Performance)
      - HKLM registry writes       (Developer Mode, UAC)
      - Stopping system services   (DiagTrack telemetry)
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def check_winget_available() -> bool:
    """Returns True if winget is installed and reachable."""
    try:
        r = subprocess.run(
            ["winget", "--version"],
            capture_output=True, timeout=10, check=False
        )
        return r.returncode == 0
    except FileNotFoundError:
        console.print(
            "[red]❌ winget not found![/red] "
            "[dim]Install App Installer from the Microsoft Store.[/dim]"
        )
        return False
    except Exception:
        return False


# ─── EXECUTION ENGINE ─────────────────────────────────────────────────────────

class ExecutionEngine:
    """Запускає Winget та PowerShell команди з обробкою помилок."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._win = sys.platform == "win32"

        # Admin warning (once at init)
        if self._win and not dry_run and not is_admin():
            console.print(Panel(
                "[yellow]⚠️  Not running as Administrator![/yellow]\n\n"
                "PowerShell tweaks that require elevation may fail:\n"
                "  • [dim]powercfg[/dim] (Ultimate Performance scheme)\n"
                "  • [dim]HKLM[/dim] registry keys (Developer Mode, UAC)\n"
                "  • [dim]Stop-Service DiagTrack[/dim] (Telemetry)\n\n"
                "[dim]Right-click your terminal → [bold]Run as Administrator[/bold][/dim]",
                border_style="yellow",
                title="Admin Warning",
                expand=False,
            ))

    # ─── INTERNAL RUNNER ──────────────────────────────────────────────────

    def _run(self, cmd: List[str], timeout: int = 300) -> subprocess.CompletedProcess:
        if self.dry_run:
            console.print(f"[dim][DRY RUN] {' '.join(cmd)}[/dim]")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        try:
            return subprocess.run(
                cmd, capture_output=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired:
            console.print(f"[red]⏰ Timeout ({timeout}s): {' '.join(cmd)}[/red]")
            raise
        except FileNotFoundError:
            console.print(f"[red]❌ Command not found: {cmd[0]}[/red]")
            raise

    # ─── WINGET ───────────────────────────────────────────────────────────

    def install_via_winget(self, winget_id: str) -> bool:
        """
        Installs a package via Winget silently.
        Returns True on success or if already installed.
        """
        if not self._win and not self.dry_run:
            console.print(f"[yellow]⚠️  Winget only on Windows — skipping {winget_id}[/yellow]")
            return False

        cmd = [
            "winget", "install",
            "--id", winget_id,
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
        console.print(f"[cyan]⏳ Installing: [bold]{winget_id}[/bold]...[/cyan]")
        try:
            r = self._run(cmd)

            if r.returncode in (WINGET_OK, WINGET_UPGRADE_AVAILABLE):
                console.print(f"[green]✅ Installed: {winget_id}[/green]")
                return True

            if r.returncode == WINGET_ALREADY_INSTALLED:
                console.print(f"[yellow]ℹ️  Already installed: {winget_id}[/yellow]")
                return True

            if r.returncode == WINGET_NO_INTERNET:
                console.print(f"[red]🌐 No internet — skipping: {winget_id}[/red]")
                return False

            if r.returncode == WINGET_NOT_FOUND:
                console.print(
                    f"[red]🔍 Package not found in Winget: {winget_id}[/red]\n"
                    f"[dim]   Check: winget search {winget_id}[/dim]"
                )
                return False

            # Generic failure — print stderr for debugging
            err = (r.stderr or b"").decode("utf-8", errors="ignore")[:300]
            console.print(f"[red]❌ Winget error {hex(r.returncode)}: {winget_id}[/red]")
            if err.strip():
                console.print(f"[dim red]{err}[/dim red]")
            return False

        except FileNotFoundError:
            console.print(
                "[red]❌ winget not found![/red] "
                "[dim]Install App Installer from the Microsoft Store.[/dim]"
            )
            return False
        except subprocess.TimeoutExpired:
            return False
        except Exception as e:
            console.print(f"[red]❌ Unexpected error: {e}[/red]")
            return False

    def apply_profile_apps(self, apps: list) -> dict:
        """Встановлює список програм із прогрес-баром."""
        results = {"success": [], "failed": [], "skipped": []}
        if not apps:
            return results

        console.print(Panel(
            f"[bold]📦 Installing {len(apps)} apps[/bold]",
            border_style="blue", expand=False
        ))

        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"),
            BarColumn(), TaskProgressColumn(), console=console
        ) as progress:
            task = progress.add_task("[cyan]Progress...", total=len(apps))
            for app in apps:
                progress.update(task, description=f"[cyan]⏳ {app.get('id', '?')}")
                wid = app.get("winget_id", "")
                if not wid:
                    results["skipped"].append(app.get("id"))
                elif self.install_via_winget(wid):
                    results["success"].append(app.get("id"))
                else:
                    bucket = "failed" if app.get("required") else "skipped"
                    results[bucket].append(app.get("id"))
                progress.advance(task)

        console.print(
            f"\n✅ [green]{len(results['success'])}[/green]  "
            f"❌ [red]{len(results['failed'])}[/red]  "
            f"⏭  [yellow]{len(results['skipped'])}[/yellow]"
        )
        return results

    # ─── POWERSHELL ────────────────────────────────────────────────────────

    def run_powershell(self, script: str, label: str = "PowerShell") -> bool:
        """Executes a PowerShell script string. Warns if not on Windows."""
        if not self._win and not self.dry_run:
            console.print("[yellow]⚠️  PowerShell only on Windows[/yellow]")
            return False

        cmd = [
            "powershell.exe",
            "-NonInteractive", "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command", script,
        ]
        console.print(f"[magenta]⚡ {label}...[/magenta]")
        try:
            r = self._run(cmd, timeout=60)
            if r.returncode == 0:
                console.print(f"[green]✅ {label}[/green]")
                return True
            err = (r.stderr or b"").decode("utf-8", errors="ignore")[:300]
            console.print(f"[red]❌ {label} — exit code {r.returncode}[/red]")
            if err.strip():
                console.print(f"[dim red]{err}[/dim red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ {label}: {e}[/red]")
            return False

    # ─── SYSTEM TWEAKS ────────────────────────────────────────────────────

    def apply_dark_theme(self) -> bool:
        return self.run_powershell(
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\Themes\\Personalize' -Name 'AppsUseLightTheme' "
            "-Value 0 -Type DWord -Force; "
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\Themes\\Personalize' -Name 'SystemUsesLightTheme' "
            "-Value 0 -Type DWord -Force",
            "Dark Theme"
        )

    def apply_light_theme(self) -> bool:
        return self.run_powershell(
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\Themes\\Personalize' -Name 'AppsUseLightTheme' "
            "-Value 1 -Type DWord -Force; "
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\Themes\\Personalize' -Name 'SystemUsesLightTheme' "
            "-Value 1 -Type DWord -Force",
            "Light Theme"
        )

    def enable_developer_mode(self) -> bool:
        if not is_admin():
            console.print("[yellow]⚠️  enable_developer_mode requires Admin[/yellow]")
        return self.run_powershell(
            "reg add 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\"
            "AppModelUnlock' /t REG_DWORD /f /v 'AllowDevelopmentWithoutDevLicense' /d '1'",
            "Developer Mode"
        )

    def set_execution_policy(self) -> bool:
        return self.run_powershell(
            "Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force",
            "ExecutionPolicy RemoteSigned"
        )

    def disable_xbox_game_bar(self) -> bool:
        return self.run_powershell(
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\GameDVR' -Name 'AppCaptureEnabled' -Value 0 "
            "-Type DWord -Force",
            "Xbox Game Bar OFF"
        )

    def enable_ultimate_performance(self) -> bool:
        """Activates the hidden Ultimate Performance power scheme."""
        if not is_admin():
            console.print(
                "[yellow]⚠️  enable_ultimate_performance requires Admin "
                "(powercfg needs elevation)[/yellow]"
            )
        return self.run_powershell(
            "powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61",
            "Ultimate Performance Power Scheme"
        )

    def optimize_gaming_performance(self) -> bool:
        script = (
            "Set-ItemProperty -Path 'HKCU:\\System\\GameConfigStore' "
            "-Name 'GameDVR_Enabled' -Value 0 -Type DWord -Force; "
            "Set-ItemProperty -Path 'HKCU:\\System\\GameConfigStore' "
            "-Name 'GameDVR_FSEBehaviorMode' -Value 2 -Type DWord -Force"
        )
        return self.run_powershell(script, "Gaming Optimization")

    def disable_telemetry(self) -> bool:
        """Disables DiagTrack, dmwappushservice, and advertising ID."""
        if not is_admin():
            console.print(
                "[yellow]⚠️  disable_telemetry: stopping system services "
                "requires Admin[/yellow]"
            )
        script = (
            "Stop-Service -Name 'DiagTrack' -Force -ErrorAction SilentlyContinue; "
            "Set-Service  -Name 'DiagTrack' -StartupType Disabled "
            "-ErrorAction SilentlyContinue; "
            "Stop-Service -Name 'dmwappushservice' -Force "
            "-ErrorAction SilentlyContinue; "
            "Set-Service  -Name 'dmwappushservice' -StartupType Disabled "
            "-ErrorAction SilentlyContinue; "
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\AdvertisingInfo' -Name 'Enabled' "
            "-Value 0 -Type DWord -Force; "
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\Explorer\\Advanced' -Name 'Start_TrackProgs' "
            "-Value 0 -Type DWord -Force"
        )
        return self.run_powershell(script, "Telemetry OFF")

    def configure_uac_developer(self) -> bool:
        if not is_admin():
            console.print(
                "[yellow]⚠️  configure_uac_developer requires Admin "
                "(HKLM write)[/yellow]"
            )
        return self.run_powershell(
            "Set-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\"
            "CurrentVersion\\Policies\\System' "
            "-Name 'ConsentPromptBehaviorAdmin' -Value 2 -Type DWord -Force",
            "UAC Developer Mode"
        )

    def set_color_calibration(self) -> bool:
        return self.run_powershell(
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\"
            "CurrentVersion\\CloudStore\\Store\\Cache\\DefaultAccount\\"
            "*$*$windows.data.bluelightreduction.bluelightreductionstate\\"
            "Current' -Name 'Data' -Value 0 -Type Binary -Force "
            "-ErrorAction SilentlyContinue",
            "Color Calibration"
        )

    def enable_night_light(self) -> bool:
        return self.run_powershell(
            "Add-Type -AssemblyName System.Windows.Forms; "
            "[System.Windows.Forms.Application]::DoEvents()",
            "Night Light"
        )