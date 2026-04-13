# client/engine.py — Двигун встановлення програм через Winget та PowerShell
import subprocess
import sys
from typing import List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

console = Console()

# Коди помилок Winget
WINGET_ALREADY_INSTALLED = 0x8A150011  # Програма вже встановлена
WINGET_NO_INTERNET = 0x8A150014        # Немає підключення до інтернету
WINGET_NOT_FOUND = 0x8A150015         # Пакет не знайдено


class ExecutionEngine:
    """
    Клас для запуску команд встановлення через Winget та PowerShell.
    Обробляє помилки та виводить статус через Rich.
    """

    def __init__(self, dry_run: bool = False):
        """
        dry_run=True — режим симуляції, команди не виконуються (для тестування).
        """
        self.dry_run = dry_run
        self._is_windows = sys.platform == "win32"

    def _run_command(self, command: List[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """
        Внутрішній метод для виконання команди через subprocess.
        Повертає CompletedProcess з кодом виходу та stdout/stderr.
        """
        if self.dry_run:
            console.print(f"[dim][DRY RUN] Команда: {' '.join(command)}[/dim]")
            # Симулюємо успішне виконання
            return subprocess.CompletedProcess(command, returncode=0, stdout=b"", stderr=b"")

        try:
            result = subprocess.run(
                command,
                capture_output=True,      # Захоплюємо stdout та stderr
                timeout=timeout,          # Таймаут у секундах
                check=False               # Не кидаємо виняток при ненульовому коді
            )
            return result
        except subprocess.TimeoutExpired:
            console.print(f"[red]⏰ Таймаут команди ({timeout}с): {' '.join(command)}[/red]")
            raise
        except FileNotFoundError as e:
            console.print(f"[red]❌ Команда не знайдена: {command[0]}. Встановлено?[/red]")
            raise

    def install_via_winget(self, winget_id: str, extra_args: Optional[List[str]] = None) -> bool:
        """
        Встановлює програму через Winget пакетний менеджер.

        Args:
            winget_id: Winget ID програми (наприклад 'Microsoft.VisualStudioCode')
            extra_args: Додаткові аргументи для winget

        Returns:
            True якщо встановлення успішне або програма вже встановлена.
        """
        command = [
            "winget", "install",
            "--id", winget_id,
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]

        # Додаємо extra аргументи якщо є
        if extra_args:
            command.extend(extra_args)

        console.print(f"[cyan]⏳ Встановлення: [bold]{winget_id}[/bold]...[/cyan]")

        try:
            result = self._run_command(command, timeout=300)

            # Аналізуємо код виходу
            if result.returncode == 0:
                console.print(f"[green]✅ Успішно встановлено: {winget_id}[/green]")
                return True

            elif result.returncode == WINGET_ALREADY_INSTALLED:
                console.print(f"[yellow]ℹ️  Вже встановлено: {winget_id}[/yellow]")
                return True  # Це не помилка — ціль досягнута

            elif result.returncode == WINGET_NO_INTERNET:
                console.print(f"[red]🌐 Немає підключення до інтернету! Пропускаємо: {winget_id}[/red]")
                return False

            elif result.returncode == WINGET_NOT_FOUND:
                console.print(f"[red]🔍 Пакет не знайдено в Winget: {winget_id}[/red]")
                return False

            else:
                # Невідома помилка — виводимо код та stderr
                stderr_text = result.stderr.decode("utf-8", errors="ignore") if result.stderr else ""
                console.print(f"[red]❌ Помилка встановлення {winget_id}. Код: {result.returncode}[/red]")
                if stderr_text:
                    console.print(f"[dim red]{stderr_text[:300]}[/dim red]")
                return False

        except subprocess.TimeoutExpired:
            console.print(f"[red]⏰ Час очікування вийшов для: {winget_id}[/red]")
            return False
        except FileNotFoundError:
            console.print("[red]❌ Winget не знайдено! Переконайтесь що Windows App Installer встановлено.[/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Несподівана помилка: {e}[/red]")
            return False

    def run_powershell(self, script: str) -> bool:
        """
        Виконує рядок коду PowerShell.

        Args:
            script: PowerShell команда або скрипт для виконання

        Returns:
            True якщо виконання успішне.
        """
        if not self._is_windows and not self.dry_run:
            console.print("[yellow]⚠️  PowerShell доступний тільки на Windows[/yellow]")
            return False

        command = [
            "powershell.exe",
            "-NonInteractive",        # Без діалогових вікон
            "-NoProfile",             # Без завантаження профілю (швидше)
            "-ExecutionPolicy", "Bypass",  # Дозволяємо виконання скриптів
            "-Command", script
        ]

        console.print(f"[magenta]⚡ PowerShell: [dim]{script[:80]}...[/dim][/magenta]")

        try:
            result = self._run_command(command, timeout=60)

            if result.returncode == 0:
                console.print("[green]✅ PowerShell команда виконана[/green]")
                return True
            else:
                stderr_text = result.stderr.decode("utf-8", errors="ignore") if result.stderr else ""
                console.print(f"[red]❌ PowerShell помилка (код {result.returncode})[/red]")
                if stderr_text:
                    console.print(f"[dim red]{stderr_text[:300]}[/dim red]")
                return False

        except FileNotFoundError:
            console.print("[red]❌ powershell.exe не знайдено![/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Помилка PowerShell: {e}[/red]")
            return False

    def apply_dark_theme(self) -> bool:
        """
        Застосовує темну тему Windows через реєстр.
        Змінює параметри AppsUseLightTheme та SystemUsesLightTheme.
        """
        console.print("[cyan]🌑 Застосування темної теми...[/cyan]")

        # PowerShell скрипт для зміни теми через реєстр
        script = (
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' "
            "-Name 'AppsUseLightTheme' -Value 0 -Type DWord -Force; "
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' "
            "-Name 'SystemUsesLightTheme' -Value 0 -Type DWord -Force"
        )

        return self.run_powershell(script)

    def apply_light_theme(self) -> bool:
        """Застосовує світлу тему Windows через реєстр."""
        console.print("[cyan]☀️  Застосування світлої теми...[/cyan]")
        script = (
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' "
            "-Name 'AppsUseLightTheme' -Value 1 -Type DWord -Force; "
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' "
            "-Name 'SystemUsesLightTheme' -Value 1 -Type DWord -Force"
        )
        return self.run_powershell(script)

    def enable_developer_mode(self) -> bool:
        """Вмикає режим розробника Windows."""
        console.print("[cyan]🛠️  Увімкнення режиму розробника...[/cyan]")
        script = (
            "reg add 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\AppModelUnlock' "
            "/t REG_DWORD /f /v 'AllowDevelopmentWithoutDevLicense' /d '1'"
        )
        return self.run_powershell(script)

    def disable_xbox_game_bar(self) -> bool:
        """Вимикає Xbox Game Bar для підвищення продуктивності в іграх."""
        console.print("[cyan]🎮 Вимкнення Xbox Game Bar...[/cyan]")
        script = (
            "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\GameDVR' "
            "-Name 'AppCaptureEnabled' -Value 0 -Type DWord -Force"
        )
        return self.run_powershell(script)

    def set_execution_policy(self) -> bool:
        """Встановлює RemoteSigned для запуску PowerShell скриптів."""
        console.print("[cyan]🔐 Налаштування PowerShell ExecutionPolicy...[/cyan]")
        script = "Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force"
        return self.run_powershell(script)

    def apply_profile_apps(self, apps: list) -> dict:
        """
        Встановлює список програм з красивим прогрес-баром Rich.

        Args:
            apps: Список словників [{"id": "vscode", "winget_id": "...", "required": True}]

        Returns:
            Словник з результатами: {"success": [...], "failed": [...], "skipped": [...]}
        """
        results = {"success": [], "failed": [], "skipped": []}

        if not apps:
            console.print("[yellow]⚠️  Список програм порожній[/yellow]")
            return results

        console.print(Panel(
            f"[bold]📦 Встановлення {len(apps)} програм[/bold]",
            border_style="blue", expand=False
        ))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Встановлення...", total=len(apps))

            for app in apps:
                app_id = app.get("id", "unknown")
                winget_id = app.get("winget_id", "")
                required = app.get("required", True)

                # Оновлюємо прогрес-бар
                progress.update(task, description=f"[cyan]⏳ {app_id}")

                if not winget_id:
                    console.print(f"[yellow]⚠️  Немає winget_id для: {app_id}[/yellow]")
                    results["skipped"].append(app_id)
                else:
                    success = self.install_via_winget(winget_id)
                    if success:
                        results["success"].append(app_id)
                    else:
                        if required:
                            results["failed"].append(app_id)
                        else:
                            results["skipped"].append(app_id)
                            console.print(f"[dim]ℹ️  Пропущено (опціонально): {app_id}[/dim]")

                progress.advance(task)

        # Підсумок
        console.print(f"\n[bold]📊 Результат:[/bold]")
        console.print(f"  ✅ Встановлено: [green]{len(results['success'])}[/green]")
        console.print(f"  ❌ Помилка:    [red]{len(results['failed'])}[/red]")
        console.print(f"  ⏭️  Пропущено:  [yellow]{len(results['skipped'])}[/yellow]")

        return results
