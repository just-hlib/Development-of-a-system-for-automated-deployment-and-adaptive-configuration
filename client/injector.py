# client/injector.py — Копіювання конфігураційних файлів у AppData
import os
import shutil
import json
from pathlib import Path
from typing import Dict
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()


class ConfigInjector:
    """
    Клас для копіювання конфігураційних файлів програм у відповідні папки AppData.
    """

    def __init__(self, configs_base_dir: str = None):
        """
        configs_base_dir — базова папка де лежать .json конфіги.
        За замовчуванням папка 'configs' поруч із скриптом.
        """
        if configs_base_dir:
            self.configs_base = Path(configs_base_dir)
        else:
            # configs/ поруч із цим файлом
            self.configs_base = Path(__file__).parent.parent / "configs"

        # AppData шлях (Windows)
        self.appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))

    def inject(self, app_name: str, config_source_path: str) -> bool:
        """
        Копіює JSON конфіг у папку %APPDATA%/{app_name}/.

        Args:
            app_name: Назва папки у AppData (наприклад 'Code' для VSCode)
            config_source_path: Відносний шлях до конфігу (наприклад 'configs/developer.json')

        Returns:
            True якщо копіювання успішне.
        """
        source = self.configs_base.parent / config_source_path

        if not source.exists():
            console.print(f"[yellow]⚠️  Конфіг не знайдено: {source}[/yellow]")
            return False

        # Цільова папка у AppData
        target_dir = self.appdata / app_name
        target_file = target_dir / source.name

        try:
            # Створюємо папку якщо не існує
            target_dir.mkdir(parents=True, exist_ok=True)

            # Копіюємо файл
            shutil.copy2(str(source), str(target_file))

            console.print(f"[green]✅ Конфіг скопійовано: {app_name} → {target_file}[/green]")
            return True

        except PermissionError:
            console.print(f"[red]🔒 Немає прав запису у: {target_dir}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Помилка копіювання для {app_name}: {e}[/red]")
            return False

    def inject_all(self, configs: Dict[str, str]) -> dict:
        """
        Масове копіювання конфігів із прогрес-баром Rich.

        Args:
            configs: Словник {app_name: config_path}
                     Наприклад: {"Code": "configs/developer.json"}

        Returns:
            {"success": [...], "failed": [...]}
        """
        results = {"success": [], "failed": []}

        if not configs:
            console.print("[yellow]Нема конфігів для копіювання[/yellow]")
            return results

        console.print(f"[cyan]📁 Копіювання {len(configs)} конфігів...[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Конфіги...", total=len(configs))

            for app_name, config_path in configs.items():
                progress.update(task, description=f"[cyan]📄 {app_name}")

                success = self.inject(app_name, config_path)
                if success:
                    results["success"].append(app_name)
                else:
                    results["failed"].append(app_name)

                progress.advance(task)

        console.print(f"[bold]Конфіги: ✅ {len(results['success'])} / ❌ {len(results['failed'])}[/bold]")
        return results
