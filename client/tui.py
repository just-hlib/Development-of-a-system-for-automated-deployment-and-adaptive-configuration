# client/tui.py — AutoDeploy v2.0 Textual TUI
# Запуск: cd client && python tui.py
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import httpx
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auditor import HardwareAuditor
from engine import ExecutionEngine, is_admin

SERVER     = "http://localhost:8000"
ADMIN_PASS = "admin123"   # change as needed
_TCSS_FILE = Path(__file__).parent / "autodeploy.tcss"

PERSONAS = [
    ("developer", "💻 Developer"),
    ("gamer",     "🎮 Gamer"),
    ("designer",  "🎨 Designer"),
    ("common",    "🌐 Common"),
]

# ── Fallback inline CSS (used when .tcss file is absent) ────────────────────
_FALLBACK_CSS = """
Screen { background: #0a0a0a; color: #c8d6e5; }
Header { background: #0d1117; color: #00ff00; text-style: bold; }
Footer { background: #0d1117; color: #008080; }
Tabs   { background: #0d1117; border-bottom: solid #008080; }
Tab    { color: #334455; padding: 1 3; }
Tab:focus, Tab.-active { color: #00ff00; text-style: bold; background: #001400; }
DataTable { border: solid #008080; background: #0d1117; height: auto; max-height: 14; }
DataTable > .datatable--header { background: #001400; color: #00ff00; text-style: bold; }
Button { margin: 0 1; background: #001400; color: #00ff00; border: solid #008080; }
Button:hover { background: #002800; border: solid #00ff00; }
Button.-primary { background: #001400; border: solid #00ff00; color: #00ff00; }
Button.-success { background: #001a30; color: #00aaff; border: solid #00aaff; }
Button.-error   { background: #2a0000; color: #ff4444; border: solid #ff4444; }
Button.-warning { background: #1a1a00; color: #ffaa00; border: solid #ffaa00; }
Input  { background: #0d1117; border: solid #008080; color: #c8d6e5; }
Input:focus { border: solid #00ff00; }
Select { width: 30; }
RichLog { border: solid #008080; background: #050810; height: 1fr; }
ScrollableContainer { border: solid #008080; background: #0d1117; height: 1fr; }
Checkbox { background: #0a0a0a; color: #c8d6e5; padding: 0 1; }
Checkbox.-on { color: #00ff00; }
LoadingIndicator { color: #00ff00; }
#profile-badge { padding: 1 0; text-style: bold; }
#admin-status  { padding: 0 0 1 0; height: 3; }
.section-title { color: #00ff00; text-style: bold; padding: 0 0 1 0; }
.controls      { height: 5; align: left middle; padding-bottom: 1; }
.admin-form    { border: solid #008080; padding: 1 2; background: #0d1117; margin-bottom: 1; }
.admin-form-row { height: 3; align: left middle; margin-bottom: 1; }
.form-label    { width: 14; color: #008080; text-style: bold; }
"""


class AutoDeployTUI(App):
    """AutoDeploy v2.0 — Windows 11 Auto-Deploy Terminal UI."""

    TITLE = "⚡ AutoDeploy v2.0 — Windows 11"
    ENABLE_COMMAND_PALETTE = False   # disable ^p palette shortcut

    # Use external .tcss if present; otherwise fall back to inline CSS
    CSS_PATH = _TCSS_FILE if _TCSS_FILE.exists() else None
    CSS      = "" if _TCSS_FILE.exists() else _FALLBACK_CSS

    BINDINGS = [
        # F-keys work regardless of which widget has focus (Select, Input, etc.)
        Binding("q",      "quit",       "Quit",         priority=True),
        Binding("f1",     "goto_dash",  "Dashboard",    priority=True),
        Binding("f2",     "goto_prov",  "Provision",    priority=True),
        Binding("f3",     "goto_logs",  "Logs",         priority=True),
        Binding("f4",     "goto_admin", "Admin",        priority=True),
        Binding("ctrl+r", "run_audit",  "Audit",        priority=True),
        Binding("ctrl+l", "clear_log",  "Clear Log",    priority=True),
        # Single-letter shortcuts still work when no input widget is focused
        Binding("d",      "goto_dash",  "Dashboard",    priority=True, show=False),
        Binding("p",      "goto_prov",  "Provisioning", priority=True, show=False),
        Binding("l",      "goto_logs",  "Logs",         priority=True, show=False),
        Binding("a",      "run_audit",  "Audit",        priority=True, show=False),
        Binding("ctrl+a", "goto_admin", "Admin",        priority=True, show=False),
    ]

    _hw_info    : dict           = {}
    _profile    : Optional[dict] = None
    _manifests  : dict           = {}
    _admin_authed: bool          = False

    # ══════════════════════════════════════════════════════════════════════
    # COMPOSE
    # ══════════════════════════════════════════════════════════════════════

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(id="tabs"):

            # ── Tab 1: Dashboard ─────────────────────────────────────────
            with TabPane("🔍 Dashboard", id="tab-dash"):
                yield Static("🖥  Hardware Audit", classes="section-title")
                yield DataTable(id="hw-table", show_cursor=False)
                yield Static("", id="profile-badge")
                yield Static(
                    "[dim]Press [bold]A[/bold] or click "
                    "[bold]Run Audit[/bold] to refresh.[/dim]",
                    id="status-hint",
                )
                with Horizontal(classes="controls"):
                    yield Button("🔍 Run Audit",     id="btn-audit")
                    yield Button("📦 → Provisioning", id="btn-goto-provision",
                                 variant="primary")

            # ── Tab 2: Provisioning ──────────────────────────────────────
            with TabPane("📦 Provisioning", id="tab-provision"):
                yield Static("👤  Select Persona & Apps", classes="section-title")
                with Horizontal(classes="controls"):
                    yield Select(
                        [(lbl, v) for v, lbl in PERSONAS],  # Textual 8.x: (label, value)
                        id="persona-select",
                        prompt="Choose persona...",
                    )
                    yield Button("📥 Load Apps", id="btn-load",   variant="primary")
                    yield Button("🚀 Deploy",     id="btn-deploy", variant="success")
                    yield Button("✅ All",         id="btn-check-all")
                    yield Button("☐ None",        id="btn-uncheck-all")

                yield LoadingIndicator(id="prov-spinner")
                with ScrollableContainer(id="app-container"):
                    yield Static(
                        "[dim]← Select a persona and click Load Apps[/dim]",
                        id="app-placeholder",
                    )

            # ── Tab 3: Logs ──────────────────────────────────────────────
            with TabPane("📜 Logs", id="tab-logs"):
                yield Static("📋  Live Output", classes="section-title")
                with Horizontal(classes="controls"):
                    yield Button("🗑 Clear",      id="btn-clear-log")
                    yield Button("ℹ Copy hint",   id="btn-copy-hint",
                                 variant="warning")
                yield RichLog(id="log", highlight=True, markup=True)

            # ── Tab 4: Admin ─────────────────────────────────────────────
            with TabPane("🔐 Admin", id="tab-admin"):
                yield Static("🔐  Admin Dashboard", classes="section-title")
                yield Static("", id="admin-status")

                with Vertical(id="admin-login-form", classes="admin-form"):
                    yield Static("[dim]Enter admin password to unlock:[/dim]")
                    with Horizontal(classes="admin-form-row"):
                        yield Label("Password:", classes="form-label")
                        yield Input(id="admin-pass-input", password=True,
                                    placeholder="admin password...")
                    with Horizontal(classes="admin-form-row"):
                        yield Button("🔓 Unlock", id="btn-admin-login",
                                     variant="warning")

                with Vertical(id="admin-panel", classes="admin-form"):
                    yield Static(
                        "[bold cyan]➕  Add New App to manifests.json[/bold cyan]"
                    )
                    with Horizontal(classes="admin-form-row"):
                        yield Label("App ID:",    classes="form-label")
                        yield Input(id="new-app-id",   placeholder="e.g.  notepadpp")
                    with Horizontal(classes="admin-form-row"):
                        yield Label("Name:",      classes="form-label")
                        yield Input(id="new-app-name", placeholder="e.g.  Notepad++")
                    with Horizontal(classes="admin-form-row"):
                        yield Label("Winget ID:", classes="form-label")
                        yield Input(id="new-app-wid",  placeholder="e.g.  Notepad++.Notepad++")
                    with Horizontal(classes="admin-form-row"):
                        yield Label("Category:",  classes="form-label")
                        yield Input(id="new-app-cat",  placeholder="e.g.  editor")
                    with Horizontal(classes="admin-form-row"):
                        yield Label("Size (MB):", classes="form-label")
                        yield Input(id="new-app-size", placeholder="e.g.  15")
                    with Horizontal(classes="admin-form-row"):
                        yield Button("💾 Save App",     id="btn-save-app",
                                     variant="success")
                        yield Button("🔄 Refresh List", id="btn-reload-manifests")

                    yield Static("\n[bold cyan]📋  Current Manifests[/bold cyan]")
                    yield DataTable(id="manifest-table", show_cursor=True)

        yield Footer()

    # ══════════════════════════════════════════════════════════════════════
    # MOUNT
    # ══════════════════════════════════════════════════════════════════════

    def on_mount(self) -> None:
        self.query_one("#admin-panel").display  = False
        self.query_one("#prov-spinner").display = False

        hw = self.query_one("#hw-table", DataTable)
        hw.add_columns("Component", "Value", "Status")

        mt = self.query_one("#manifest-table", DataTable)
        mt.add_columns("ID", "Name", "Winget ID", "Category", "MB")

        self._run_audit_worker()

    # ══════════════════════════════════════════════════════════════════════
    # TAB NAVIGATION
    # ══════════════════════════════════════════════════════════════════════

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Refresh admin table whenever the Admin tab is opened."""
        tab_id = event.tab.id or ""
        if "admin" in tab_id and self._admin_authed:
            self._reload_manifests_worker()

    def action_goto_dash(self)  -> None:
        self.query_one(TabbedContent).active = "tab-dash"

    def action_goto_prov(self)  -> None:
        self.query_one(TabbedContent).active = "tab-provision"

    def action_goto_logs(self)  -> None:
        self.query_one(TabbedContent).active = "tab-logs"

    def action_goto_admin(self) -> None:
        self.query_one(TabbedContent).active = "tab-admin"

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — DASHBOARD
    # ══════════════════════════════════════════════════════════════════════

    def action_run_audit(self) -> None:
        self._run_audit_worker()

    @on(Button.Pressed, "#btn-audit")
    def _on_audit_btn(self) -> None:
        self._run_audit_worker()

    @on(Button.Pressed, "#btn-goto-provision")
    def _on_goto_prov(self) -> None:
        self.action_goto_prov()

    @work(thread=True, exclusive=True, group="audit")
    def _run_audit_worker(self) -> None:
        log = self.query_one("#log", RichLog)
        self.call_from_thread(log.write, "[cyan]⏳ Running hardware audit...[/cyan]")
        try:
            info    = HardwareAuditor().get_hardware_info()
            profile = HardwareAuditor().recommend_profile(info["ram_gb"])
            self._hw_info = info
            self.call_from_thread(self._refresh_hw_table, info, profile)
            self.call_from_thread(
                log.write,
                f"[green]✅ Audit done — recommended: [bold]{profile}[/bold][/green]",
            )
            if not is_admin():
                self.call_from_thread(
                    log.write,
                    "[yellow]⚠️  Not running as Administrator — "
                    "powercfg/HKLM tweaks may fail.[/yellow]",
                )
        except Exception as e:
            self.call_from_thread(log.write, f"[red]❌ Audit error: {e}[/red]")

    def _refresh_hw_table(self, info: dict, profile: str) -> None:
        t = self.query_one("#hw-table", DataTable)
        t.clear()

        def cell(val: float, good: float, warn: float,
                 rev: bool = False, u: str = "") -> Text:
            if rev:
                c = "green" if val < good else ("yellow" if val < warn else "red")
            else:
                c = "green" if val >= warn else ("yellow" if val >= good else "red")
            icon = "✅" if c == "green" else ("⚠️ " if c == "yellow" else "❌")
            return Text.from_markup(f"[{c}]{icon} {val}{u}[/{c}]")

        rows = [
            ("🧠 RAM Total",      f"{info['ram_gb']} GB",
             cell(info["ram_gb"], 4, 8, u=" GB")),
            ("   └ Used",         f"{info['ram_used_percent']}%",
             cell(info["ram_used_percent"], 50, 80, rev=True, u="%")),
            ("⚡ CPU",             info["cpu_name"][:40],
             Text("OK", style="green")),
            ("   └ Cores ph/lg",  f"{info['cpu_cores_physical']} / "
                                  f"{info['cpu_cores_logical']}",
             cell(info["cpu_cores_physical"], 2, 4)),
            ("   └ Load",         f"{info['cpu_usage']}%",
             cell(info["cpu_usage"], 30, 70, rev=True, u="%")),
            ("💾 Disk Free",      f"{info['disk_free_gb']} GB",
             cell(info["disk_free_gb"], 10, 50, u=" GB")),
            ("   └ Used",         f"{info['disk_used_percent']}%",
             cell(info["disk_used_percent"], 60, 85, rev=True, u="%")),
        ]
        for r in rows:
            t.add_row(*r)

        badge = self.query_one("#profile-badge", Static)
        if profile == "Ultimate":
            badge.update(
                "[bold green]⚡ ULTIMATE — RAM ≥ 8 GB — Full effects enabled[/bold green]"
            )
        else:
            badge.update(
                "[bold yellow]⚠️  LITE — RAM < 8 GB — Heavy effects disabled[/bold yellow]"
            )

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — PROVISIONING (reactive)
    # ══════════════════════════════════════════════════════════════════════

    @on(Select.Changed, "#persona-select")
    def _on_persona_changed(self, event: Select.Changed) -> None:
        """Auto-load apps when persona changes."""
        if event.value is not Select.NULL:
            self._load_apps_worker(str(event.value))

    @on(Button.Pressed, "#btn-load")
    def _on_load_btn(self) -> None:
        sel = self.query_one("#persona-select", Select)
        if sel.value is Select.NULL:
            self.notify("⚠️  Select a persona first!", severity="warning")
            return
        self._load_apps_worker(str(sel.value))

    @on(Button.Pressed, "#btn-check-all")
    def _on_check_all(self) -> None:
        for cb in self.query_one("#app-container").query(Checkbox):
            cb.value = True

    @on(Button.Pressed, "#btn-uncheck-all")
    def _on_uncheck_all(self) -> None:
        for cb in self.query_one("#app-container").query(Checkbox):
            cb.value = False

    @work(thread=True, exclusive=True, group="load")
    def _load_apps_worker(self, persona: str) -> None:
        spinner = self.query_one("#prov-spinner", LoadingIndicator)
        log     = self.query_one("#log", RichLog)

        self.call_from_thread(setattr, spinner, "display", True)
        self.call_from_thread(
            log.write,
            f"[cyan]📥 Loading profile [bold]{persona}[/bold]...[/cyan]",
        )
        try:
            with httpx.Client(timeout=10) as client:
                pr = client.get(f"{SERVER}/profile/{persona}")
                mr = client.get(f"{SERVER}/manifests")

            if pr.status_code == 404:
                self.call_from_thread(
                    log.write,
                    f"[red]❌ Persona '{persona}' not found on server.[/red]",
                )
                return

            profile   = pr.json()
            manifests = {m["id"]: m for m in mr.json()["manifests"]}
            self._profile   = profile
            self._manifests = manifests

            self.call_from_thread(self._render_app_list, profile, manifests)
            self.call_from_thread(
                log.write,
                f"[green]✅ Loaded [bold]{len(profile['apps'])}[/bold] apps "
                f"for [bold]{profile['display_name']}[/bold][/green]",
            )

        except httpx.ConnectError:
            self.call_from_thread(
                log.write,
                "[red]❌ Server unreachable!\n"
                "   [dim]cd server && uvicorn main:app --reload --port 8000[/dim][/red]",
            )
            self.call_from_thread(self.notify, "Server offline!", severity="error")
        except Exception as e:
            self.call_from_thread(log.write, f"[red]❌ Load error: {e}[/red]")
        finally:
            self.call_from_thread(setattr, spinner, "display", False)

    def _render_app_list(self, profile: dict, manifests: dict) -> None:
        """Rebuild checkbox list on the UI thread."""
        container = self.query_one("#app-container")
        container.remove_children()  # atomic bulk remove (Textual 8.x safe)

        # Build all widgets first, then mount once — avoids async remove/mount races
        new_widgets = []
        prev_cat: Optional[str] = None
        for ref in profile["apps"]:
            aid = ref["id"]
            m   = manifests.get(aid, {})
            cat = m.get("category", "?")

            if cat != prev_cat:
                new_widgets.append(
                    Static(f"\n[bold cyan]── {cat.upper()} ──[/bold cyan]")
                )
                prev_cat = cat

            name    = m.get("name", aid)
            size    = m.get("size_mb", "?")
            req_tag = (
                " [bold green](required)[/bold green]"
                if ref["required"] else " [dim](optional)[/dim]"
            )
            new_widgets.append(
                Checkbox(
                    f"[white]{name}[/white]  [dim]{size} MB[/dim]{req_tag}",
                    value=ref["required"],
                    id=f"app-{aid}",
                )
            )

        if new_widgets:
            container.mount(*new_widgets)  # single bulk mount
        else:
            container.mount(Static("[dim]No apps found for this persona.[/dim]"))

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — DEPLOY
    # ══════════════════════════════════════════════════════════════════════

    @on(Button.Pressed, "#btn-deploy")
    def _on_deploy_btn(self) -> None:
        if not self._profile:
            self.notify("⚠️  Load apps first!", severity="warning")
            return

        selected = []
        for ref in self._profile["apps"]:
            aid = ref["id"]
            try:
                cb = self.query_one(f"#app-{aid}", Checkbox)
                if cb.value:
                    m = self._manifests.get(aid, {})
                    selected.append({
                        "id":        aid,
                        "winget_id": m.get("winget_id", ""),
                        "required":  ref["required"],
                    })
            except Exception:
                pass

        if not selected:
            self.notify("No apps selected!", severity="warning")
            return

        # Redirect to Logs tab immediately
        self.query_one(TabbedContent).active = "tab-logs"
        self._deploy_worker(selected, self._profile)

    @work(thread=True, exclusive=True, group="deploy")
    def _deploy_worker(self, apps: list, profile: dict) -> None:
        log = self.query_one("#log", RichLog)

        def lw(msg: str) -> None:
            self.call_from_thread(log.write, msg)

        lw("\n[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
        lw(f"[bold cyan]  🚀  DEPLOY: {profile['display_name']}[/bold cyan]")
        lw("[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]\n")

        if not is_admin():
            lw("[yellow]⚠️  Not Administrator — HKLM/powercfg tweaks may fail[/yellow]\n")

        engine = ExecutionEngine(dry_run=False)
        ok = fail = skip = 0

        # Step 1 — Apps
        lw(f"[bold white]📦  Step 1/2 — Installing {len(apps)} apps[/bold white]")
        lw("[dim]───────────────────────────────────[/dim]")
        for app in apps:
            wid = app.get("winget_id", "")
            if not wid:
                lw(f"  [yellow]⏭  {app['id']} (no Winget ID)[/yellow]")
                skip += 1
                continue
            result = engine.install_via_winget(wid)
            if result:
                lw(f"  [green]✅ {app['id']}[/green]")
                ok += 1
            elif app["required"]:
                lw(f"  [red]❌ {app['id']} (required — FAILED)[/red]")
                fail += 1
            else:
                lw(f"  [yellow]⏭  {app['id']} (optional)[/yellow]")
                skip += 1

        # Step 2 — Tweaks
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
        lw(f"\n[bold white]⚙️   Step 2/2 — {len(scripts)} System Tweaks[/bold white]")
        lw("[dim]───────────────────────────────────[/dim]")
        for name in scripts:
            fn = ps_map.get(name)
            if fn:
                r   = fn()
                tag = "[green]✅" if r else "[red]❌"
                end = "[/green]" if r else "[/red]"
                lw(f"  {tag} {name}{end}")
            else:
                lw(f"  [yellow]⚠️  Unknown script: {name}[/yellow]")

        # Summary
        lw("\n[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
        lw(
            f"[bold green]🎉  Done![/bold green]  "
            f"[green]✅ {ok}[/green]  [red]❌ {fail}[/red]  "
            f"[yellow]⏭  {skip}[/yellow]"
        )
        lw("[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]\n")

        sev = "information" if fail == 0 else "warning"
        self.call_from_thread(
            self.notify,
            f"Deploy done!  ✅ {ok} installed  ❌ {fail} failed",
            severity=sev,
        )

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3 — LOGS
    # ══════════════════════════════════════════════════════════════════════

    @on(Button.Pressed, "#btn-clear-log")
    def _on_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()

    @on(Button.Pressed, "#btn-copy-hint")
    def _on_copy_hint(self) -> None:
        self.notify(
            "Scroll the log with the mouse, highlight text, then Ctrl+C.",
            severity="information",
        )

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()

    # ══════════════════════════════════════════════════════════════════════
    # TAB 4 — ADMIN DASHBOARD
    # ══════════════════════════════════════════════════════════════════════

    @on(Button.Pressed, "#btn-admin-login")
    def _on_admin_login(self) -> None:
        pwd = self.query_one("#admin-pass-input", Input).value.strip()
        if pwd == ADMIN_PASS:
            self._admin_authed = True
            self.query_one("#admin-login-form").display = False
            self.query_one("#admin-panel").display      = True
            self.query_one("#admin-status", Static).update(
                "[bold green]🔓 Authenticated as Admin[/bold green]"
            )
            self._reload_manifests_worker()
        else:
            self.query_one("#admin-status", Static).update(
                "[bold red]❌ Incorrect password[/bold red]"
            )
            self.notify("Wrong password!", severity="error")

    @on(Input.Submitted, "#admin-pass-input")
    def _on_pass_submit(self, _: Input.Submitted) -> None:
        self._on_admin_login()

    @on(Button.Pressed, "#btn-save-app")
    def _on_save_app(self) -> None:
        if not self._admin_authed:
            self.notify("Not authenticated!", severity="error")
            return

        app_id   = self.query_one("#new-app-id",   Input).value.strip()
        name     = self.query_one("#new-app-name",  Input).value.strip()
        wid      = self.query_one("#new-app-wid",   Input).value.strip()
        category = self.query_one("#new-app-cat",   Input).value.strip()
        size_raw = self.query_one("#new-app-size",  Input).value.strip()

        if not all([app_id, name, wid, category]):
            self.notify("Fill in ID, Name, Winget ID, Category!", severity="warning")
            return

        try:
            size_mb: Optional[int] = int(size_raw) if size_raw else None
        except ValueError:
            self.notify("Size must be a number!", severity="warning")
            return

        self._save_app_worker(app_id, name, wid, category, size_mb)

    @on(Button.Pressed, "#btn-reload-manifests")
    def _on_reload_manifests(self) -> None:
        self._reload_manifests_worker()

    @work(thread=True, exclusive=True, group="admin-write")
    def _save_app_worker(
        self,
        app_id: str, name: str, wid: str, category: str,
        size_mb: Optional[int],
    ) -> None:
        """POST new app to server."""
        log     = self.query_one("#log", RichLog)
        payload = {
            "id":          app_id,
            "name":        name,
            "winget_id":   wid,
            "category":    category,
            "size_mb":     size_mb,
            "description": name,
        }
        self.call_from_thread(
            log.write,
            f"[cyan]💾 Saving new app [bold]{app_id}[/bold]...[/cyan]",
        )
        try:
            with httpx.Client(timeout=10) as client:
                r = client.post(f"{SERVER}/manifests", json=payload)
            if r.status_code in (200, 201):
                self.call_from_thread(
                    log.write, f"[green]✅ App '{app_id}' saved![/green]"
                )
                self.call_from_thread(
                    self.notify, f"App '{app_id}' added!", severity="information"
                )
                self.call_from_thread(self._clear_admin_form)
                self._reload_manifests_worker()
            else:
                detail = r.json().get("detail", r.text)
                self.call_from_thread(
                    log.write,
                    f"[red]❌ Server error {r.status_code}: {detail}[/red]",
                )
        except httpx.ConnectError:
            self.call_from_thread(log.write, "[red]❌ Server offline![/red]")
        except Exception as e:
            self.call_from_thread(log.write, f"[red]❌ {e}[/red]")

    @work(thread=True, exclusive=True, group="admin-read")
    def _reload_manifests_worker(self) -> None:
        """Refresh the manifests DataTable from server."""
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{SERVER}/manifests")
            self.call_from_thread(
                self._refresh_manifest_table, r.json()["manifests"]
            )
        except Exception:
            pass  # silently skip if server not up

    def _refresh_manifest_table(self, manifests: list) -> None:
        t = self.query_one("#manifest-table", DataTable)
        t.clear()
        for m in manifests:
            t.add_row(
                m.get("id", ""),
                m.get("name", ""),
                m.get("winget_id", ""),
                m.get("category", ""),
                str(m.get("size_mb", "?")),
            )

    def _clear_admin_form(self) -> None:
        for fid in ("#new-app-id", "#new-app-name",
                    "#new-app-wid", "#new-app-cat", "#new-app-size"):
            self.query_one(fid, Input).value = ""


if __name__ == "__main__":
    AutoDeployTUI().run()