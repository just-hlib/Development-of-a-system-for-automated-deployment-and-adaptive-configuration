# server/main.py — FastAPI сервер
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import Manifest, ManifestList, ProfileResponse, AppRef
import json, os

app = FastAPI(
    title="AutoDeploy Server",
    description="Сервер автоматизованого розгортання Windows 11",
    version="2.0.0"
)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/")
def root():
    return {"status": "online", "version": "2.0.0", "apps_count": 52}


@app.get("/manifests", response_model=ManifestList)
def get_manifests(category: str = None):
    """Список програм. Опційна фільтрація за категорією."""
    data = load_json(os.path.join(DATA_DIR, "manifests.json"))
    manifests = data["manifests"]
    if category:
        manifests = [m for m in manifests if m["category"] == category]
    return ManifestList(manifests=manifests)


@app.get("/manifests/{app_id}", response_model=Manifest)
def get_manifest(app_id: str):
    data = load_json(os.path.join(DATA_DIR, "manifests.json"))
    for m in data["manifests"]:
        if m["id"] == app_id:
            return Manifest(**m)
    raise HTTPException(404, f"Програма '{app_id}' не знайдена")


@app.get("/profile/{persona}", response_model=ProfileResponse)
def get_profile(persona: str):
    """Профіль для: developer, gamer, designer, common"""
    valid = ["developer", "gamer", "designer", "common"]
    if persona.lower() not in valid:
        raise HTTPException(404, f"Персона '{persona}' не існує. Доступні: {valid}")
    data = load_json(os.path.join(DATA_DIR, "profiles.json"))
    p = data["profiles"][persona.lower()]
    return ProfileResponse(
        persona=persona.lower(),
        display_name=p["display_name"],
        description=p["description"],
        apps=[AppRef(**a) for a in p["apps"]],
        powershell_scripts=p["powershell_scripts"],
        configs=p["configs"]
    )


@app.get("/categories")
def get_categories():
    """Список унікальних категорій програм."""
    data = load_json(os.path.join(DATA_DIR, "manifests.json"))
    cats = sorted(set(m["category"] for m in data["manifests"]))
    return {"categories": cats}