# server/main.py — FastAPI сервер для системи автоматизованого розгортання
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import Manifest, ManifestList, ProfileResponse
import json
import os

app = FastAPI(
    title="AutoDeploy Server",
    description="Сервер для автоматизованого розгортання Windows середовища",
    version="1.0.0"
)

# CORS — дозволяємо запити від клієнта
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Шляхи до JSON файлів з даними
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MANIFESTS_FILE = os.path.join(DATA_DIR, "manifests.json")
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")


def load_json(path: str) -> dict:
    """Завантажує JSON файл і повертає словник."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/", summary="Перевірка сервера")
def root():
    """Перевірка що сервер живий."""
    return {"status": "online", "message": "AutoDeploy Server v1.0.0"}


@app.get("/manifests", response_model=ManifestList, summary="Список програм")
def get_manifests():
    """
    Повертає повний список доступних програм із Winget ID
    та параметрами тихого встановлення.
    """
    try:
        data = load_json(MANIFESTS_FILE)
        return ManifestList(manifests=data["manifests"])
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="manifests.json не знайдено")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@app.get("/profile/{persona}", response_model=ProfileResponse, summary="Профіль персони")
def get_profile(persona: str):
    """
    Повертає набір програм та конфігурацій для обраної персони.
    Доступні персони: developer, gamer, designer
    """
    valid_personas = ["developer", "gamer", "designer"]
    persona_lower = persona.lower()

    if persona_lower not in valid_personas:
        raise HTTPException(
            status_code=404,
            detail=f"Персона '{persona}' не знайдена. Доступні: {', '.join(valid_personas)}"
        )

    try:
        data = load_json(PROFILES_FILE)
        profile_data = data["profiles"].get(persona_lower)

        if not profile_data:
            raise HTTPException(status_code=404, detail=f"Дані для '{persona}' відсутні")

        return ProfileResponse(
            persona=persona_lower,
            display_name=profile_data["display_name"],
            description=profile_data["description"],
            apps=profile_data["apps"],
            powershell_scripts=profile_data["powershell_scripts"],
            configs=profile_data["configs"]
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="profiles.json не знайдено")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@app.get("/manifests/{app_id}", response_model=Manifest, summary="Дані однієї програми")
def get_manifest_by_id(app_id: str):
    """Повертає маніфест конкретної програми за її ID."""
    try:
        data = load_json(MANIFESTS_FILE)
        for app in data["manifests"]:
            if app["id"] == app_id:
                return Manifest(**app)
        raise HTTPException(status_code=404, detail=f"Програма '{app_id}' не знайдена")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
