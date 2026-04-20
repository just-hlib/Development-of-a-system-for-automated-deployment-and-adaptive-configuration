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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MANIFESTS_PATH = os.path.join(DATA_DIR, "manifests.json")


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifests(data: dict) -> None:
    """Persist manifests.json atomically."""
    tmp = MANIFESTS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MANIFESTS_PATH)  # atomic on all platforms


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    data = load_json(MANIFESTS_PATH)
    return {
        "status": "online",
        "version": "2.0.0",
        "apps_count": len(data["manifests"]),
    }


@app.get("/manifests", response_model=ManifestList)
def get_manifests(category: str = None):
    """List apps, optionally filtered by category."""
    data = load_json(MANIFESTS_PATH)
    manifests = data["manifests"]
    if category:
        manifests = [m for m in manifests if m["category"] == category]
    return ManifestList(manifests=manifests)


@app.get("/manifests/{app_id}", response_model=Manifest)
def get_manifest(app_id: str):
    data = load_json(MANIFESTS_PATH)
    for m in data["manifests"]:
        if m["id"] == app_id:
            return Manifest(**m)
    raise HTTPException(404, f"App '{app_id}' not found")


@app.post("/manifests", response_model=Manifest, status_code=201)
def add_manifest(manifest: Manifest):
    """
    Admin endpoint — add a new app to manifests.json.
    Called from the TUI Admin Dashboard.
    Returns 409 if the ID already exists.
    """
    data = load_json(MANIFESTS_PATH)

    # Duplicate check
    if any(m["id"] == manifest.id for m in data["manifests"]):
        raise HTTPException(
            409, f"App '{manifest.id}' already exists. Use PUT to update."
        )

    data["manifests"].append(manifest.model_dump())
    save_manifests(data)
    return manifest


@app.put("/manifests/{app_id}", response_model=Manifest)
def update_manifest(app_id: str, manifest: Manifest):
    """Admin endpoint — update an existing app entry."""
    data = load_json(MANIFESTS_PATH)
    for i, m in enumerate(data["manifests"]):
        if m["id"] == app_id:
            data["manifests"][i] = manifest.model_dump()
            save_manifests(data)
            return manifest
    raise HTTPException(404, f"App '{app_id}' not found")


@app.delete("/manifests/{app_id}")
def delete_manifest(app_id: str):
    """Admin endpoint — remove an app from manifests.json."""
    data = load_json(MANIFESTS_PATH)
    before = len(data["manifests"])
    data["manifests"] = [m for m in data["manifests"] if m["id"] != app_id]
    if len(data["manifests"]) == before:
        raise HTTPException(404, f"App '{app_id}' not found")
    save_manifests(data)
    return {"deleted": app_id}


@app.get("/profile/{persona}", response_model=ProfileResponse)
def get_profile(persona: str):
    """Profile for: developer, gamer, designer, common."""
    valid = ["developer", "gamer", "designer", "common"]
    if persona.lower() not in valid:
        raise HTTPException(
            404, f"Persona '{persona}' not found. Available: {valid}"
        )
    data = load_json(os.path.join(DATA_DIR, "profiles.json"))
    p    = data["profiles"][persona.lower()]
    return ProfileResponse(
        persona=persona.lower(),
        display_name=p["display_name"],
        description=p["description"],
        apps=[AppRef(**a) for a in p["apps"]],
        powershell_scripts=p["powershell_scripts"],
        configs=p["configs"],
    )


@app.get("/categories")
def get_categories():
    """List unique app categories."""
    data = load_json(MANIFESTS_PATH)
    cats = sorted(set(m["category"] for m in data["manifests"]))
    return {"categories": cats}