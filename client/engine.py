# client/engine.py — ExecutionEngine v2.1
# Winget install, PowerShell tweaks, registry-based install check
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

console = Console()

# ── Winget exit codes ──────────────────────────────────────────────────────────
WINGET_OK                = 0
WINGET_ALREADY_INSTALLED = 0x8A150011
WINGET_NO_INTERNET       = 0x8A150014
WINGET_NOT_FOUND         = 0x8A150015
WINGET_UPGRADE_AVAILABLE = 0x8A150040


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def is_admin() -> bool:
    """True if process has Windows Administrator privileges."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def is_app_installed(winget_id: str) -> bool:
    """
    Check Windows Registry before calling Winget — saves time on already-installed apps.

    Searches two registry hives:
      HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall
      HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall
      HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall

    Matches on DisplayName or the key name containing the app's short name
    derived from the winget_id (part after the last dot).
    """
    if sys.platform != "win32":
        return False  # can't check on non-Windows

    try:
        import winreg  # built into Python on Windows
    except ImportError:
        return False

    # Derive a short name to search for: "Notepad++.Notepad++" → "Notepad++"
    short_name = winget_id.split(".")[-1].lower().replace("+", "").replace("-", "")

    hives = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for hive, base_key in hives:
        try:
            with winreg.OpenKey(hive, base_key) as reg_key:
                count = winreg.QueryInfoKey(reg_key)[0]
                for i in range(count):
                    try:
                        sub_name = winreg.EnumKey(reg_key, i)
                        with winreg.OpenKey(reg_key, sub_name) as sub_key:
                            try:
                                display_name, _ = winreg.QueryValueEx(
                                    sub_key, "DisplayName"
                                )
                                dn_clean = str(display_name).lower().replace(
                                    "+", ""
                                ).replace("-", "").replace(" ", "")
                                if short_name in dn_clean:
                                    return True
                            except FileNotFoundError:
                                pass
                    except OSError:
                        continue
        except OSError:
            continue

    return False


# ══════════════════════════════════════════════════════════════════════════════
# BUILD FILE  (Save / Load personal builds)
# ══════════════════════════════════════════════════════════════════════════════

def save_build(
    selected_app_ids: List[str],
    hw_profile: str,
    persona: str,
    output_path: Path,
    powershell_scripts: Optional[List[str]] = None,
) -> Path:
    """
    Export the current selection to a standalone .json build file.
    The file is self-contained — no server needed to apply it.

    Schema:
    {
      "autodeploy_version": "2.0",
      "created_at": "<ISO timestamp>",
      "persona": "developer",
      "hw_profile": "Ultimate",
      "apps": [{"id": "vscode", "winget_id": "Microsoft.VisualStudioCode"}, ...],
      "powershell_scripts": ["apply_dark_theme", ...]
    }
    """
    build = {
        "autodeploy_version": "2.0",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "persona": persona,
        "hw_profile": hw_profile,
        "apps": selected_app_ids,          # list of {"id", "winget_id"} dicts
        "powershell_scripts": powershell_scripts or [],
    }
    output_path = Path(output_path)
    output_path.write_text(
        json.dumps(build, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    console.print(f"[green]💾 Build saved → [bold]{output_path}[/bold][/green]")
    return output_path


def load_build(path: Path) -> dict:
    """
    Load a .json build file.
    Returns the parsed dict or raises ValueError with a clear message.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Build file not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))

    # Minimal schema validation
    required_keys = {"autodeploy_version", "apps"}
    missing = required_keys - set(raw.keys())
    if missing:
        raise ValueError(
            f"Invalid build file — missing keys: {missing}\n"
            f"File: {path}"
        )
    if not isinstance(raw["apps"], list):
        raise ValueError("'apps' must be a list.")

    return raw


# ══════════════════════════════════════════════════════════════════════════════
# EXECUTION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class ExecutionEngine:
    """Runs Winget installs and PowerShell tweaks with robust error handling."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._win    = sys.platform == "win32"

        if self._win and not dry_run and not is_admin():
            console.print(Panel(
                "[yellow]⚠️  Not running as Administrator![/yellow]\n\n"
                "Tweaks that need elevation will fail:\n"
                "  • [dim]powercfg[/dim]  (Ultimate Performance)\n"
                "  • [dim]HKLM[/dim] registry  (Developer Mode, UAC)\n"
                "  • [dim]Stop-Service[/dim]  (Telemetry)\n\n"
                "[dim]Right-click terminal → [bold]Run as Administrator[/bold][/dim]",
                border_style="yellow", title="Admin Warning", expand=False,
            ))

    # ── Internal runner ────────────────────────────────────────────────────

    def _run(self, cmd: List[str], timeout: int = 300) -> subprocess.CompletedProcess:
        if self.dry_run:
            console.print(f"[dim][DRY-RUN] {' '.join(cmd)}[/dim]")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        try:
            return subprocess.run(
                cmd, capture_output=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired:
            console.print(f"[red]⏰ Timeout ({timeout}s): {cmd[0]}[/red]")
            raise
        except FileNotFoundError:
            console.print(f"[red]❌ Command not found: {cmd[0]}[/red]")
            raise

    # ── Winget ─────────────────────────────────────────────────────────────

    def install_via_winget(self, winget_id: str, skip_if_installed: bool = True) -> bool:
        """
        Install a package via Winget silently.

        Args:
            winget_id: Winget package identifier.
            skip_if_installed: If True, check registry first — saves time.

        Returns True on success or already installed.
        """
        if not self._win and not self.dry_run:
            console.print(f"[yellow]⚠️  Winget only on Windows — skipping {winget_id}[/yellow]")
            return False

        # Fast registry pre-check
        if skip_if_installed and not self.dry_run and is_app_installed(winget_id):
            console.print(f"[yellow]ℹ️  Already installed (registry): {winget_id}[/yellow]")
            return True

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
                console.print(f"[yellow]ℹ️  Already installed (winget): {winget_id}[/yellow]")
                return True

            if r.returncode == WINGET_NO_INTERNET:
                console.print(f"[red]🌐 No internet — skipping: {winget_id}[/red]")
                return False

            if r.returncode == WINGET_NOT_FOUND:
                console.print(
                    f"[red]🔍 Not found in Winget: {winget_id}[/red]\n"
                    f"[dim]   Try: winget search {winget_id}[/dim]"
                )
                return False

            err = (r.stderr or b"").decode("utf-8", errors="ignore")[:300]
            console.print(
                f"[red]❌ Winget error {hex(r.returncode)}: {winget_id}[/red]"
            )
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
            console.print(f"[red]❌ Unexpected: {e}[/red]")
            return False

    def apply_profile_apps(self, apps: list) -> dict:
        """Install a list of apps with a progress bar."""
        results: dict = {"success": [], "failed": [], "skipped": []}
        if not apps:
            return results

        console.print(Panel(
            f"[bold]📦 Installing {len(apps)} apps[/bold]",
            border_style="blue", expand=False,
        ))

        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"),
            BarColumn(), TaskProgressColumn(), console=console,
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
                    bucket = "failed" if app.get("required", True) else "skipped"
                    results[bucket].append(app.get("id"))
                progress.advance(task)

        console.print(
            f"\n✅ [green]{len(results['success'])}[/green]  "
            f"❌ [red]{len(results['failed'])}[/red]  "
            f"⏭  [yellow]{len(results['skipped'])}[/yellow]"
        )
        return results

    def apply_build(self, build: dict) -> dict:
        """
        Apply a loaded build file directly (no server needed).
        Used by: python main.py apply --file my_build.json
        """
        apps    = build.get("apps", [])
        scripts = build.get("powershell_scripts", [])

        console.print(Panel(
            f"[bold cyan]📂 Applying build file[/bold cyan]\n"
            f"Persona:   [cyan]{build.get('persona', '?')}[/cyan]\n"
            f"HW Profile:[cyan] {build.get('hw_profile', '?')}[/cyan]\n"
            f"Apps:      [cyan]{len(apps)}[/cyan]\n"
            f"Tweaks:    [cyan]{len(scripts)}[/cyan]\n"
            f"Created:   [dim]{build.get('created_at', '?')}[/dim]",
            border_style="cyan", expand=False,
        ))

        results = self.apply_profile_apps(apps)
        self._run_scripts(scripts)
        return results

    def _run_scripts(self, scripts: List[str]) -> None:
        ps_map = {
            "apply_dark_theme":            self.apply_dark_theme,
            "apply_light_theme":           self.apply_light_theme,
            "enable_developer_mode":       self.enable_developer_mode,
            "set_execution_policy":        self.set_execution_policy,
            "disable_xbox_game_bar":       self.disable_xbox_game_bar,
            "enable_ultimate_performance": self.enable_ultimate_performance,
            "optimize_gaming_performance": self.optimize_gaming_performance,
            "disable_telemetry":           self.disable_telemetry,
            "configure_uac_developer":     self.configure_uac_developer,
            "set_color_calibration":       self.set_color_calibration,
            "enable_night_light":          self.enable_night_light,
        }
        for name in scripts:
            fn = ps_map.get(name)
            if fn:
                fn()
            else:
                console.print(f"[yellow]⚠️  Unknown script: {name}[/yellow]")

    # ── PowerShell helpers ─────────────────────────────────────────────────

    def run_powershell(self, script: str, label: str = "PowerShell") -> bool:
        if not self._win and not self.dry_run:
            console.print("[yellow]⚠️  PowerShell only on Windows[/yellow]")
            return False
        cmd = [
            "powershell.exe", "-NonInteractive", "-NoProfile",
            "-ExecutionPolicy", "Bypass", "-Command", script,
        ]
        console.print(f"[magenta]⚡ {label}...[/magenta]")
        try:
            r = self._run(cmd, timeout=60)
            if r.returncode == 0:
                console.print(f"[green]✅ {label}[/green]")
                return True
            err = (r.stderr or b"").decode("utf-8", errors="ignore")[:300]
            console.print(f"[red]❌ {label} — exit {r.returncode}[/red]")
            if err.strip():
                console.print(f"[dim red]{err}[/dim red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ {label}: {e}[/red]")
            return False

    # ── System tweaks ──────────────────────────────────────────────────────

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
            "AppModelUnlock' /t REG_DWORD /f /v "
            "'AllowDevelopmentWithoutDevLicense' /d '1'",
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
            "CurrentVersion\\GameDVR' -Name 'AppCaptureEnabled' "
            "-Value 0 -Type DWord -Force",
            "Xbox Game Bar OFF"
        )

    def enable_ultimate_performance(self) -> bool:
        if not is_admin():
            console.print(
                "[yellow]⚠️  enable_ultimate_performance requires Admin[/yellow]"
            )
        # Check if an Ultimate Performance scheme already exists before duplicating.
        # powercfg -list lines look like:
        #   Power Scheme GUID: <guid>  (Ultimate Performance)
        script = (
            "$list = powercfg -list; "
            "$existing = $list | Where-Object { $_ -match 'Ultimate Performance' }; "
            "if ($existing) { "
            "    $guid = [regex]::Match($existing, "
            "        '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'"
            "    ).Value; "
            "    if ($guid) { powercfg -setactive $guid; "
            "        Write-Host 'Ultimate Performance already present — activated.' } "
            "} else { "
            "    powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61 "
            "}"
        )
        return self.run_powershell(script, "Ultimate Performance")

    def optimize_gaming_performance(self) -> bool:
        script = (
            "Set-ItemProperty -Path 'HKCU:\\System\\GameConfigStore' "
            "-Name 'GameDVR_Enabled' -Value 0 -Type DWord -Force; "
            "Set-ItemProperty -Path 'HKCU:\\System\\GameConfigStore' "
            "-Name 'GameDVR_FSEBehaviorMode' -Value 2 -Type DWord -Force"
        )
        return self.run_powershell(script, "Gaming Optimization")

    def disable_telemetry(self) -> bool:
        if not is_admin():
            console.print(
                "[yellow]⚠️  disable_telemetry: Stop-Service requires Admin[/yellow]"
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
                "[yellow]⚠️  configure_uac_developer requires Admin (HKLM)[/yellow]"
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