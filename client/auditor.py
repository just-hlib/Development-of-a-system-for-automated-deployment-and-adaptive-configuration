# client/auditor.py — Аудит апаратного забезпечення
import psutil
import platform
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.text import Text

console = Console()


class HardwareAuditor:
    """Аудит RAM, CPU, диску. Рекомендує Lite або Ultimate профіль."""

    def get_hardware_info(self) -> dict:
        """Збирає системну інформацію через psutil."""
        ram = psutil.virtual_memory()
        disk_path = "C:\\" if platform.system() == "Windows" else "/"
        disk = psutil.disk_usage(disk_path)

        return {
            "ram_gb":             round(ram.total / (1024**3), 1),
            "ram_used_percent":   ram.percent,
            "cpu_name":           platform.processor() or "Unknown CPU",
            "cpu_cores_physical": psutil.cpu_count(logical=False) or 1,
            "cpu_cores_logical":  psutil.cpu_count(logical=True) or 1,
            "cpu_usage":          psutil.cpu_percent(interval=1),
            "disk_total_gb":      round(disk.total / (1024**3), 1),
            "disk_free_gb":       round(disk.free / (1024**3), 1),
            "disk_used_percent":  disk.percent,
            "os_name":            f"{platform.system()} {platform.release()}",
        }

    def recommend_profile(self, ram_gb: float) -> str:
        """RAM < 8 GB → Lite, інакше → Ultimate."""
        return "Lite" if ram_gb < 8 else "Ultimate"

    def _status(self, value: float, good: float, warn: float,
                reverse=False, unit="") -> Text:
        """Повертає кольоровий Rich Text."""
        if reverse:
            color = "green" if value < good else ("yellow" if value < warn else "red")
        else:
            color = "green" if value >= warn else ("yellow" if value >= good else "red")
        return Text(f"{value}{unit}", style=f"bold {color}")

    def display_table(self, info: dict) -> None:
        """Виводить кольорову таблицю характеристик у термінал."""
        profile = self.recommend_profile(info["ram_gb"])
        color = "green" if profile == "Ultimate" else "yellow"

        console.print(Panel(
            f"[bold cyan]🔍 АУДИТ СИСТЕМИ[/bold cyan]\n"
            f"[dim]{info['os_name']}[/dim]\n"
            f"Рекомендований профіль: [bold {color}]{profile}[/bold {color}]",
            border_style="cyan", expand=False
        ))

        t = Table(box=box.ROUNDED, border_style="bright_blue",
                  header_style="bold magenta", show_lines=True)
        t.add_column("Компонент",  style="bold white", min_width=22)
        t.add_column("Значення",   min_width=22)
        t.add_column("Статус",     justify="center", min_width=10)

        t.add_row("🧠 RAM (загальна)",    f"{info['ram_gb']} GB",
                  self._status(info["ram_gb"], 4, 8, unit=" GB"))
        t.add_row("   └ Використання",    f"{info['ram_used_percent']}%",
                  self._status(info["ram_used_percent"], 50, 80, reverse=True, unit="%"))
        t.add_row("⚡ CPU",               info["cpu_name"][:40],
                  Text("OK", style="green"))
        t.add_row("   └ Ядра (физ/лог)", f"{info['cpu_cores_physical']} / {info['cpu_cores_logical']}",
                  self._status(info["cpu_cores_physical"], 2, 4))
        t.add_row("   └ Завантаженість",  f"{info['cpu_usage']}%",
                  self._status(info["cpu_usage"], 30, 70, reverse=True, unit="%"))
        t.add_row("💾 Диск (загальний)",  f"{info['disk_total_gb']} GB",
                  Text("OK", style="green"))
        t.add_row("   └ Вільно",          f"{info['disk_free_gb']} GB",
                  self._status(info["disk_free_gb"], 10, 50, unit=" GB"))
        t.add_row("   └ Зайнято",         f"{info['disk_used_percent']}%",
                  self._status(info["disk_used_percent"], 60, 85, reverse=True, unit="%"))

        console.print(t)

        if profile == "Lite":
            console.print(Panel("⚠️  [yellow]RAM < 8GB → профіль [bold]Lite[/bold]. "
                                "Анімації та ефекти вимкнено.[/yellow]",
                                border_style="yellow", expand=False))
        else:
            console.print(Panel("✅ [green]RAM ≥ 8GB → профіль [bold]Ultimate[/bold]. "
                                "Повний функціонал.[/green]",
                                border_style="green", expand=False))

    def run_audit(self) -> dict:
        """Головна точка входу: збирає дані, виводить таблицю, повертає dict."""
        console.print("\n[bold cyan]⏳ Аналіз системи...[/bold cyan]\n")
        info = self.get_hardware_info()
        self.display_table(info)
        info["recommended_profile"] = self.recommend_profile(info["ram_gb"])
        return info


if __name__ == "__main__":
    HardwareAuditor().run_audit()