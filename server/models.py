# server/models.py — Pydantic моделі для валідації даних API
from pydantic import BaseModel
from typing import List, Optional


class Manifest(BaseModel):
    """Модель одного програмного маніфесту."""
    id: str
    name: str
    winget_id: str
    category: str
    description: str
    size_mb: Optional[int] = None


class ManifestList(BaseModel):
    """Список усіх маніфестів."""
    manifests: List[Manifest]
    total: int = 0

    def model_post_init(self, __context):
        self.total = len(self.manifests)


class AppRef(BaseModel):
    """Посилання на програму у профілі."""
    id: str
    required: bool = True


class ProfileResponse(BaseModel):
    """Повна відповідь з профілем персони."""
    persona: str
    display_name: str
    description: str
    apps: List[AppRef]
    powershell_scripts: List[str]
    configs: dict