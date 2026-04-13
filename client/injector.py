# client/injector.py — Копіювання конфігів у %APPDATA%
import os, shutil
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()


class ConfigInjector:
    def __init__(self, configs_base_dir: str = None):
        self.configs_base = Path(configs_base_dir) if configs_base_dir \
            else Path(__file__).parent.parent / "configs"
        self.appdata = Path(os.environ.get("APPDATA",
                            Path.home() / "AppData" / "Roaming"))

    def inject(self, app_name: str, config_source_path: str) -> bool:
        source = self.configs_base.parent / config_source_path
        if not source.exists():
            console.print(f"[yellow]⚠️  Конфіг не знайдено: {source}[/yellow]")
            return False
        target_dir = self.appdata / app_name
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(target_dir / source.name))
            console.print(f"[green]✅ Конфіг: {app_name}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Помилка конфігу {app_name}: {e}[/red]")
            return False

    def inject_all(self, configs: dict) -> dict:
        results = {"success": [], "failed": []}
        if not configs:
            return results
        with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                      BarColumn(), console=console) as p:
            task = p.add_task("[cyan]Конфіги...", total=len(configs))
            for app_name, path in configs.items():
                p.update(task, description=f"[cyan]📄 {app_name}")
                (results["success"] if self.inject(app_name, path)
                 else results["failed"]).append(app_name)
                p.advance(task)
        return results