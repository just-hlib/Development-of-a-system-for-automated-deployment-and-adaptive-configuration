# server/models.py — Pydantic моделі для валідації даних
from pydantic import BaseModel
from typing import List, Optional


class Manifest(BaseModel):
    """Модель одного програмного маніфесту."""
    id: str                          # Унікальний ID програми
    name: str                        # Людська назва
    winget_id: str                   # ID для Winget пакетного менеджера
    version: Optional[str] = "latest"
    silent_args: str                 # Аргументи тихого встановлення
    category: str                    # Категорія (ide, browser, game, design...)
    description: str                 # Опис програми
    size_mb: Optional[int] = None    # Приблизний розмір у МБ


class ManifestList(BaseModel):
    """Список усіх маніфестів."""
    manifests: List[Manifest]
    total: int = 0

    def model_post_init(self, __context):
        # Автоматично рахуємо кількість
        self.total = len(self.manifests)


class AppRef(BaseModel):
    """Посилання на програму у профілі."""
    id: str           # ID із маніфесту
    required: bool = True  # Обов'язкова чи опціональна


class ProfileResponse(BaseModel):
    """Повна відповідь з профілем персони."""
    persona: str                          # developer / gamer / designer
    display_name: str                     # "💻 Developer"
    description: str                      # Опис персони
    apps: List[AppRef]                    # Список програм для встановлення
    powershell_scripts: List[str]         # Назви PowerShell скриптів для запуску
    configs: dict                         # Конфіги для копіювання {app: path}
