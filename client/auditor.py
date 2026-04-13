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
    """
    Клас для аудиту апаратного забезпечення комп'ютера.
    Збирає дані про RAM, CPU, диск та рекомендує профіль.
    """

    def get_hardware_info(self) -> dict:
        """
        Збирає інформацію про апаратне забезпечення через psutil.
        Повертає словник з характеристиками ПК.
        """
        # RAM — отримуємо загальний обсяг у гігабайтах
        ram_bytes = psutil.virtual_memory().total
        ram_gb = round(ram_bytes / (1024 ** 3), 1)
        ram_used_percent = psutil.virtual_memory().percent

        # CPU — назва, кількість ядер та поточне завантаження
        cpu_name = platform.processor() or "Невідомий CPU"
        cpu_cores_physical = psutil.cpu_count(logical=False) or 1
        cpu_cores_logical = psutil.cpu_count(logical=True) or 1
        cpu_usage = psutil.cpu_percent(interval=1)  # % завантаження за 1 сек

        # Диск — головний системний диск (C: на Windows, / на Linux)
        disk = psutil.disk_usage("C:\\" if platform.system() == "Windows" else "/")
        disk_total_gb = round(disk.total / (1024 ** 3), 1)
        disk_free_gb = round(disk.free / (1024 ** 3), 1)
        disk_used_percent = disk.percent

        # ОС — назва та версія
        os_name = f"{platform.system()} {platform.release()}"

        return {
            "ram_gb": ram_gb,
            "ram_used_percent": ram_used_percent,
            "cpu_name": cpu_name,
            "cpu_cores_physical": cpu_cores_physical,
            "cpu_cores_logical": cpu_cores_logical,
            "cpu_usage": cpu_usage,
            "disk_total_gb": disk_total_gb,
            "disk_free_gb": disk_free_gb,
            "disk_used_percent": disk_used_percent,
            "os_name": os_name,
        }

    def recommend_profile(self, ram_gb: float) -> str:
        """
        Рекомендує профіль на основі обсягу RAM.
        RAM < 8 GB  → Lite  (без важких ефектів)
        RAM >= 8 GB → Ultimate (повний функціонал)
        """
        if ram_gb < 8:
            return "Lite"
        else:
            return "Ultimate"

    def _colorize(self, value: float, low: float, mid: float, reverse: bool = False) -> Text:
        """
        Повертає Rich Text з кольором залежно від значення.
        reverse=True — менше значення краще (наприклад завантаженість диску).
        """
        if reverse:
            # Для % використання: низьке % = добре (зелений)
            if value < low:
                return Text(f"{value}%", style="bold green")
            elif value < mid:
                return Text(f"{value}%", style="bold yellow")
            else:
                return Text(f"{value}%", style="bold red")
        else:
            # Для ресурсів: більше = краще (зелений)
            if value >= mid:
                return Text(str(value), style="bold green")
            elif value >= low:
                return Text(str(value), style="bold yellow")
            else:
                return Text(str(value), style="bold red")

    def display_table(self, info: dict) -> None:
        """
        Виводить красиву таблицю з характеристиками ПК у консоль через Rich.
        🟢 Зелений = добре, 🟡 Жовтий = прийнятно, 🔴 Червоний = слабко.
        """
        profile = self.recommend_profile(info["ram_gb"])
        profile_color = "green" if profile == "Ultimate" else "yellow"

        # Заголовок панелі
        console.print(Panel(
            f"[bold cyan]🔍 АУДИТ СИСТЕМИ[/bold cyan]\n"
            f"[dim]{info['os_name']}[/dim]\n"
            f"Рекомендований профіль: [bold {profile_color}]{profile}[/bold {profile_color}]",
            border_style="cyan",
            expand=False
        ))

        # Таблиця характеристик
        table = Table(
            title="Характеристики ПК",
            box=box.ROUNDED,
            border_style="bright_blue",
            header_style="bold magenta",
            show_lines=True,
        )

        table.add_column("Компонент", style="bold white", min_width=20)
        table.add_column("Значення", min_width=25)
        table.add_column("Статус", justify="center", min_width=12)

        # RAM рядок
        ram_status = self._colorize(info["ram_gb"], 4, 8)
        ram_usage_status = self._colorize(info["ram_used_percent"], 50, 80, reverse=True)
        table.add_row(
            "🧠 RAM (загальна)",
            f"{info['ram_gb']} GB",
            ram_status
        )
        table.add_row(
            "   └ Завантаженість",
            f"{info['ram_used_percent']}%",
            ram_usage_status
        )

        # CPU рядок
        cpu_status = self._colorize(info["cpu_cores_physical"], 2, 4)
        cpu_usage_status = self._colorize(info["cpu_usage"], 30, 70, reverse=True)
        table.add_row(
            "⚡ CPU",
            info["cpu_name"][:40],  # Обрізаємо якщо дуже довга назва
            cpu_status
        )
        table.add_row(
            "   └ Ядра (физ/лог)",
            f"{info['cpu_cores_physical']} / {info['cpu_cores_logical']}",
            Text("ОК", style="green")
        )
        table.add_row(
            "   └ Завантаженість",
            f"{info['cpu_usage']}%",
            cpu_usage_status
        )

        # Диск рядок
        disk_free_status = self._colorize(info["disk_free_gb"], 10, 50)
        disk_usage_status = self._colorize(info["disk_used_percent"], 60, 85, reverse=True)
        table.add_row(
            "💾 Диск (загальний)",
            f"{info['disk_total_gb']} GB",
            Text("ОК", style="green")
        )
        table.add_row(
            "   └ Вільно",
            f"{info['disk_free_gb']} GB",
            disk_free_status
        )
        table.add_row(
            "   └ Зайнято",
            f"{info['disk_used_percent']}%",
            disk_usage_status
        )

        console.print(table)

        # Вивід рекомендації
        if profile == "Lite":
            console.print(Panel(
                "⚠️  [yellow]RAM < 8GB. Рекомендовано профіль [bold]Lite[/bold].[/yellow]\n"
                "[dim]Буде вимкнено: анімації, прозорість, ефекти Aero.[/dim]",
                border_style="yellow", expand=False
            ))
        else:
            console.print(Panel(
                "✅ [green]RAM ≥ 8GB. Рекомендовано профіль [bold]Ultimate[/bold].[/green]\n"
                "[dim]Усі ефекти, анімації та функції будуть активовані.[/dim]",
                border_style="green", expand=False
            ))

    def run_audit(self) -> dict:
        """
        Запускає повний аудит: збирає дані, виводить таблицю, повертає результат.
        Головна точка входу для використання з CLI.
        """
        console.print("\n[bold cyan]⏳ Збираємо інформацію про систему...[/bold cyan]\n")

        # Збираємо дані
        info = self.get_hardware_info()

        # Виводимо таблицю
        self.display_table(info)

        # Додаємо рекомендацію до результату
        info["recommended_profile"] = self.recommend_profile(info["ram_gb"])

        return info


# Точка запуску як самостійного скрипту
if __name__ == "__main__":
    auditor = HardwareAuditor()
    result = auditor.run_audit()
    console.print(f"\n[dim]Дані аудиту: {result}[/dim]")
