# client/tui.py — Textual TUI для AutoDeploy v2.0
# Запуск: cd client && python tui.py
from __future__ import annotations

import os
import sys
from typing import Optional

import httpx
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

# Дозволяємо запускати як `python tui.py` з папки client/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auditor import HardwareAuditor
from engine import ExecutionEngine, is_admin

SERVER = "http://localhost:8000"
PERSONAS = [
    ("developer", "💻 Developer"),
    ("gamer",     "🎮 Gamer"),
    ("designer",  "🎨 Designer"),
    ("common",    "🌐 Common"),
]

# ─── CYBERPUNK / HACKER CSS ───────────────────────────────────────────────────
CYBERPUNK_CSS = """
Screen {
    background: #080c10;
    color: #c8d6e5;
}

Header {
    background: #0d1117;
    color: #00ff9f;
    text-style: bold;
}

Footer {
    background: #0d1117;
    color: #39ff14;
}

/* ── Tabs ── */
TabbedContent {
    background: #080c10;
}

TabPane {
    padding: 1 2;
    background: #080c10;
}

Tabs {
    background: #0d1117;
    border-bottom: solid #00ff9f;
}

Tab {
    color: #445566;
    padding: 1 3;
}

Tab:focus, Tab.-active {
    color: #00ff9f;
    text-style: bold;
    background: #001a0f;
}

/* ── DataTable ── */
DataTable {
    height: auto;
    max-height: 14;
    border: solid #00ff9f;
    background: #0d1117;
    margin-bottom: 1;
}

DataTable > .datatable--header {
    background: #001a0f;
    color: #00ff9f;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #002a18;
    color: #00ff9f;
}

/* ── Buttons ── */
Button {
    margin: 0 1;
    background: #001a0f;
    color: #00ff9f;
    border: solid #00ff9f;
    min-width: 18;
}

Button:hover {
    background: #003020;
    border: solid #39ff14;
    color: #39ff14;
}

Button.-primary  { background: #002a18; }
Button.-success  { background: #001a30; color: #00aaff; border: solid #00aaff; }
Button.-error    { background: #2a0000; color: #ff4444; border: solid #ff4444; }

/* ── Misc ── */
#profile-badge {
    padding: 1 0;
    text-style: bold;
}

#status-hint {
    color: #334455;
    padding: 0 0 1 0;
}

RichLog {
    border: solid #00ff9f;
    background: #050810;
    height: 1fr;
    scrollbar-color: #00ff9f;
    scrollbar-background: #0d1117;
}

#app-container {
    height: 1fr;
    border: solid #00ff9f;
    padding: 0 1;
    background: #0d1117;
}

Select {
    width: 28;
}

.controls {
    height: 5;
    align: left middle;
    padding-bottom: 1;
}

.section-title {
    color: #00ff9f;
    text-style: bold;
    padding: 0 0 1 0;
}

.divider {
    color: #001a0f;
    padding: 0;
}
"""


class AutoDeployTUI(App):
    """AutoDeploy v2.0 — Windows 11 Auto-Deploy Terminal UI."""

    TITLE = "⚡ AutoDeploy v2.0 — Windows 11 Auto-Deploy System"
    CSS = CYBERPUNK_CSS

    BINDINGS = [
        ("q",      "quit",       "Quit"),
        ("a",      "run_audit",  "Audit"),
        ("ctrl+l", "clear_log",  "Clear Log"),
        ("d",      "goto_dash",  "Dashboard"),
        ("p",      "goto_prov",  "Provisioning"),
        ("l",      "goto_logs",  "Logs"),
    ]

    # ── Internal state ─────────────────────────────────────────────────────
    _hw_info: dict = {}
    _profile: Optional[dict] = None
    _all_manifests: dict = {}

    # ── Layout ─────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(id="tabs"):

            # ── TAB 1: Dashboard ──────────────────────────────────────────
            with TabPane("🔍 Dashboard", id="tab-dash"):
                yield Static("🖥  Hardware Audit", classes="section-title")
                yield DataTable(id="hw-table", show_cursor=False)
                yield Static("", id="profile-badge")
                yield Static(
                    "[dim]Press [bold]A[/bold] or click [bold]Run Audit[/bold] to refresh[/dim]",
                    id="status-hint",
                )
                with Horizontal(classes="controls"):
                    yield Button("🔍 Run Audit", id="btn-audit")

            # ── TAB 2: Provisioning ───────────────────────────────────────
            with TabPane("📦 Provisioning", id="tab-provision"):
                yield Static("👤  Select Persona & Load Apps", classes="section-title")
                with Horizontal(classes="controls"):
                    yield Select(
                        [(v, lbl) for v, lbl in PERSONAS],
                        id="persona-select",
                        prompt="Choose persona...",
                    )
                    yield Button("📥 Load Apps", id="btn-load")
                    yield Button("🚀 Deploy",    id="btn-deploy", variant="success")
                with ScrollableContainer(id="app-container"):
                    yield Static(
                        "[dim]← Select a persona and click Load Apps[/dim]",
                        id="app-placeholder",
                    )

            # ── TAB 3: Logs ───────────────────────────────────────────────
            with TabPane("📜 Logs", id="tab-logs"):
                yield Static("📋  Live Output", classes="section-title")
                yield RichLog(id="log", highlight=True, markup=True)

        yield Footer()

    def on_mount(self) -> None:
        """Init table columns and auto-run first audit."""
        t = self.query_one("#hw-table", DataTable)
        t.add_columns("Component", "Value", "Status")
        self._run_audit_worker()

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 1 — DASHBOARD
    # ═══════════════════════════════════════════════════════════════════════

    def action_run_audit(self) -> None:
        self._run_audit_worker()

    @on(Button.Pressed, "#btn-audit")
    def _on_audit_btn(self) -> None:
        self._run_audit_worker()

    @work(thread=True, exclusive=True)
    def _run_audit_worker(self) -> None:
        """Collect hardware info in background thread, update UI thread-safely."""
        log = self.query_one("#log", RichLog)
        self.call_from_thread(log.write, "[cyan]⏳ Running hardware audit...[/cyan]")
        try:
            auditor = HardwareAuditor()
            info = auditor.get_hardware_info()
            profile = auditor.recommend_profile(info["ram_gb"])
            self._hw_info = info

            self.call_from_thread(self._refresh_hw_table, info, profile)
            self.call_from_thread(
                log.write,
                f"[green]✅ Audit complete — Recommended profile: [bold]{profile}[/bold][/green]",
            )
            if not is_admin():
                self.call_from_thread(
                    log.write,
                    "[yellow]⚠️  Not running as Administrator — "
                    "PowerShell tweaks & powercfg may fail.[/yellow]",
                )
        except Exception as e:
            self.call_from_thread(log.write, f"[red]❌ Audit failed: {e}[/red]")

    def _refresh_hw_table(self, info: dict, profile: str) -> None:
        """Rebuild the hardware DataTable (must be called from UI thread)."""
        t = self.query_one("#hw-table", DataTable)
        t.clear()

        def s(val: float, good: float, warn: float,
              rev: bool = False, u: str = "") -> Text:
            """Coloured status cell."""
            if rev:
                c = "green" if val < good else ("yellow" if val < warn else "red")
            else:
                c = "green" if val >= warn else ("yellow" if val >= good else "red")
            icon = "✅" if c == "green" else ("⚠️ " if c == "yellow" else "❌")
            return Text.from_markup(f"[{c}]{icon} {val}{u}[/{c}]")

        t.add_row("🧠 RAM Total",   f"{info['ram_gb']} GB",
                  s(info["ram_gb"], 4, 8, u=" GB"))
        t.add_row("  └ Used",       f"{info['ram_used_percent']}%",
                  s(info["ram_used_percent"], 50, 80, rev=True, u="%"))
        t.add_row("⚡ CPU",          info["cpu_name"][:40], Text("OK", style="green"))
        t.add_row("  └ Cores ph/lg",
                  f"{info['cpu_cores_physical']} / {info['cpu_cores_logical']}",
                  s(info["cpu_cores_physical"], 2, 4))
        t.add_row("  └ Load",       f"{info['cpu_usage']}%",
                  s(info["cpu_usage"], 30, 70, rev=True, u="%"))
        t.add_row("💾 Disk Free",   f"{info['disk_free_gb']} GB",
                  s(info["disk_free_gb"], 10, 50, u=" GB"))
        t.add_row("  └ Used",       f"{info['disk_used_percent']}%",
                  s(info["disk_used_percent"], 60, 85, rev=True, u="%"))

        badge = self.query_one("#profile-badge", Static)
        if profile == "Ultimate":
            badge.update(
                "[bold green]⚡ Profile: ULTIMATE — RAM ≥ 8 GB — "
                "Full effects & Ultimate Performance enabled[/bold green]"
            )
        else:
            badge.update(
                "[bold yellow]⚠️  Profile: LITE — RAM < 8 GB — "
                "Heavy effects disabled[/bold yellow]"
            )

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 2 — PROVISIONING
    # ═══════════════════════════════════════════════════════════════════════

    @on(Button.Pressed, "#btn-load")
    def _on_load_btn(self) -> None:
        sel = self.query_one("#persona-select", Select)
        if sel.value is Select.BLANK:
            self.notify("⚠️  Select a persona first!", severity="warning")
            return
        self._load_apps_worker(str(sel.value))

    @work(thread=True, exclusive=True)
    def _load_apps_worker(self, persona: str) -> None:
        """Fetch profile + manifests from server in background thread."""
        log = self.query_one("#log", RichLog)
        self.call_from_thread(
            log.write, f"[cyan]📥 Fetching profile [bold]{persona}[/bold] from server...[/cyan]"
        )
        try:
            with httpx.Client(timeout=10) as client:
                pr = client.get(f"{SERVER}/profile/{persona}")
                mr = client.get(f"{SERVER}/manifests")

            if pr.status_code == 404:
                self.call_from_thread(log.write, f"[red]❌ Persona '{persona}' not found[/red]")
                return

            profile   = pr.json()
            manifests = {m["id"]: m for m in mr.json()["manifests"]}

            self._profile       = profile
            self._all_manifests = manifests

            self.call_from_thread(self._render_app_list, profile, manifests)
            self.call_from_thread(
                log.write,
                f"[green]✅ Loaded [bold]{len(profile['apps'])}[/bold] apps "
                f"for [bold]{persona}[/bold][/green]",
            )

        except httpx.ConnectError:
            self.call_from_thread(
                log.write,
                "[red]❌ Cannot reach server!\n"
                "   Start it: [bold]cd server && uvicorn main:app --reload --port 8000[/bold][/red]",
            )
            self.call_from_thread(self.notify, "Server offline!", severity="error")
        except Exception as e:
            self.call_from_thread(log.write, f"[red]❌ Load error: {e}[/red]")

    def _render_app_list(self, profile: dict, manifests: dict) -> None:
        """Build checkbox list for apps (UI thread)."""
        container = self.query_one("#app-container", ScrollableContainer)
        container.remove_children()

        prev_cat = None
        for ref in profile["apps"]:
            aid = ref["id"]
            m   = manifests.get(aid, {})
            cat = m.get("category", "?")

            # Category separator
            if cat != prev_cat:
                container.mount(
                    Static(f"\n[bold cyan]── {cat.upper()} ──[/bold cyan]")
                )
                prev_cat = cat

            name = m.get("name", aid)
            size = m.get("size_mb", "?")
            req  = " [dim](required)[/dim]" if ref["required"] else " [dim](optional)[/dim]"
            label = f"[white]{name}[/white]  [dim]{size} MB[/dim]{req}"

            container.mount(
                Checkbox(label, value=ref["required"], id=f"app-{aid}")
            )

    @on(Button.Pressed, "#btn-deploy")
    def _on_deploy_btn(self) -> None:
        if not self._profile:
            self.notify("⚠️  Load apps first!", severity="warning")
            return

        # Collect checked apps
        selected = []
        for ref in self._profile["apps"]:
            aid = ref["id"]
            try:
                cb = self.query_one(f"#app-{aid}", Checkbox)
                if cb.value:
                    m = self._all_manifests.get(aid, {})
                    selected.append({
                        "id":       aid,
                        "winget_id": m.get("winget_id", ""),
                        "required": ref["required"],
                    })
            except Exception:
                pass

        if not selected:
            self.notify("No apps selected!", severity="warning")
            return

        # Switch to Logs tab for live output
        self.query_one(TabbedContent).active = "tab-logs"
        self._deploy_worker(selected, self._profile)

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 3 — DEPLOY WORKER
    # ═══════════════════════════════════════════════════════════════════════

    @work(thread=True, exclusive=True)
    def _deploy_worker(self, apps: list, profile: dict) -> None:
        """Full deploy pipeline: winget install → PS tweaks (background thread)."""
        log = self.query_one("#log", RichLog)

        def lw(msg: str) -> None:
            self.call_from_thread(log.write, msg)

        lw("\n[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
        lw(f"[bold cyan]  🚀 DEPLOY: {profile['display_name']}[/bold cyan]")
        lw("[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]\n")

        # ── Admin warning ──────────────────────────────────────────────────
        if not is_admin():
            lw("[yellow]⚠️  WARNING: Not running as Administrator![/yellow]")
            lw("[yellow]   • powercfg (Ultimate Performance) will fail[/yellow]")
            lw("[yellow]   • Registry tweaks may be blocked[/yellow]")
            lw("[yellow]   Restart terminal as Admin for full deploy.\n[/yellow]")

        engine = ExecutionEngine(dry_run=False)
        ok_count = failed_count = skip_count = 0

        # ── Step 1: Install Apps ───────────────────────────────────────────
        lw(f"[bold white]📦 Step 1/2 — Installing {len(apps)} apps[/bold white]")
        lw("[dim]─────────────────────────────────────────[/dim]")

        for app in apps:
            wid = app.get("winget_id", "")
            if not wid:
                lw(f"  [yellow]⏭  Skipped {app['id']} (no Winget ID)[/yellow]")
                skip_count += 1
                continue

            lw(f"  [dim]⏳ {app['id']}  [{wid}]...[/dim]")
            ok = engine.install_via_winget(wid)

            if ok:
                lw(f"  [green]✅ {app['id']}[/green]")
                ok_count += 1
            elif app["required"]:
                lw(f"  [red]❌ {app['id']} (required — FAILED)[/red]")
                failed_count += 1
            else:
                lw(f"  [yellow]⏭  {app['id']} (optional — skipped)[/yellow]")
                skip_count += 1

        # ── Step 2: PowerShell Tweaks ──────────────────────────────────────
        ps_map = {
            "apply_dark_theme":            engine.apply_dark_theme,
            "apply_light_theme":           engine.apply_light_theme,
            "enable_developer_mode":       engine.enable_developer_mode,
            "set_execution_policy":        engine.set_execution_policy,
            "disable_xbox_game_bar":       engine.disable_xbox_game_bar,
            "enable_ultimate_performance": engine.enable_ultimate_performance,
            "optimize_gaming_performance": engine.optimize_gaming_performance,
            "disable_telemetry":           engine.disable_telemetry,
            "configure_uac_developer":     engine.configure_uac_developer,
            "set_color_calibration":       engine.set_color_calibration,
            "enable_night_light":          engine.enable_night_light,
        }

        scripts = profile.get("powershell_scripts", [])
        lw(f"\n[bold white]⚙️  Step 2/2 — {len(scripts)} System Tweaks[/bold white]")
        lw("[dim]─────────────────────────────────────────[/dim]")

        for name in scripts:
            fn = ps_map.get(name)
            if fn:
                result = fn()
                ico = "[green]✅" if result else "[red]❌"
                end = "[/green]"  if result else "[/red]"
                lw(f"  {ico} {name}{end}")
            else:
                lw(f"  [yellow]⚠️  Unknown script: {name}[/yellow]")

        # ── Summary ────────────────────────────────────────────────────────
        lw("\n[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
        lw(
            f"[bold green]🎉 Deploy complete![/bold green]  "
            f"[green]✅ {ok_count}[/green]  "
            f"[red]❌ {failed_count}[/red]  "
            f"[yellow]⏭  {skip_count}[/yellow]"
        )
        lw("[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]\n")

        severity = "information" if failed_count == 0 else "warning"
        self.call_from_thread(
            self.notify,
            f"Deploy done! ✅{ok_count} installed  ❌{failed_count} failed",
            severity=severity,
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  NAVIGATION ACTIONS
    # ═══════════════════════════════════════════════════════════════════════

    def action_goto_dash(self)  -> None: self.query_one(TabbedContent).active = "tab-dash"
    def action_goto_prov(self)  -> None: self.query_one(TabbedContent).active = "tab-provision"
    def action_goto_logs(self)  -> None: self.query_one(TabbedContent).active = "tab-logs"
    def action_clear_log(self)  -> None: self.query_one("#log", RichLog).clear()


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    AutoDeployTUI().run()