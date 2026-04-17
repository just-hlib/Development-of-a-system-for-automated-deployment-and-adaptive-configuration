# AutoDeploy v2.0 — Windows 11 Auto-Deploy System

> Клієнт-серверна система автоматизованого розгортання та адаптивної конфігурації Windows 11.

---

## ⚡ Quick Start (5 хвилин)

### 1 · Клонуй / розпакуй проєкт

```
prod_cloud/
├── server/          ← FastAPI backend
├── client/          ← CLI + TUI
├── configs/         ← JSON dotfiles
├── tests/
└── requirements.txt
```

### 2 · Створи віртуальне середовище та встанови залежності

```bash
# З кореневої папки проєкту (prod_cloud/)
python -m venv .venv

# Активація
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

# Встановлення залежностей
pip install -r requirements.txt
```

### 3 · Запусти FastAPI сервер

```bash
cd server
uvicorn main:app --reload --port 8000
```

Перевір що сервер працює: http://localhost:8000/docs
Очікуваний відповідь кореня: `{"status":"online","version":"2.0.0","apps_count":52}`

> ⚠️ Тримай цей термінал відкритим — сервер має бути запущений для роботи клієнта.

---

## 🖥 Запуск клієнта

### Варіант A — TUI (рекомендовано)

```bash
cd client
python tui.py
```

Відкриється інтерактивний термінальний інтерфейс з трьома вкладками:

| Вкладка       | Що робить                                         |
|---------------|---------------------------------------------------|
| 🔍 Dashboard  | Аудит RAM/CPU/Disk, рекомендований профіль        |
| 📦 Provisioning| Вибір персони, чекбокси програм, кнопка Deploy  |
| 📜 Logs       | Живий вивід встановлення та PowerShell tweaks     |

**Гарячі клавіші TUI:**

| Клавіша  | Дія                    |
|----------|------------------------|
| `Q`      | Вийти                  |
| `A`      | Запустити аудит        |
| `D`      | Вкладка Dashboard      |
| `P`      | Вкладка Provisioning   |
| `L`      | Вкладка Logs           |
| `Ctrl+L` | Очистити лог           |

### Варіант B — CLI (Typer)

```bash
cd client

# Аудит системи
python main.py audit

# Повне розгортання для розробника
python main.py deploy --persona developer

# Симуляція без реального встановлення
python main.py deploy --persona gamer --dry-run

# Встановити одну програму
python main.py install vscode

# Список програм (з фільтром)
python main.py list
python main.py list --category ide

# Окремий системний твік
python main.py tweak dark
python main.py tweak telemetry --dry-run
python main.py tweak ultimate --dry-run
```

---

## 👤 Персони

| Персона    | Ключові програми              | Tweaks                                   |
|------------|-------------------------------|------------------------------------------|
| Developer  | VSCode, Git, Python, Node.js  | Dark theme, DevMode, ExecutionPolicy, UAC|
| Gamer      | Steam, Discord, OBS           | Dark theme, GameBar OFF, Gaming Perf     |
| Designer   | Figma, GIMP, Blender          | Light theme, Color calibration           |
| Common     | Chrome, VLC, 7zip, Telegram   | Dark theme, Telemetry OFF                |

---

## 🧠 Smart System (адаптивна логіка)

| RAM       | Профіль        | Поведінка                                  |
|-----------|----------------|--------------------------------------------|
| < 8 GB    | **Lite**       | Без анімацій, прозорості, важких ефектів   |
| ≥ 8 GB    | **Ultimate**   | Повний функціонал, всі tweaks увімкнено    |

---

## 🔐 Права адміністратора

Деякі PowerShell tweaks **вимагають** запуску з правами адміністратора:

| Tweak                       | Потребує Admin |
|-----------------------------|----------------|
| `enable_ultimate_performance`| ✅ Так (powercfg) |
| `enable_developer_mode`      | ✅ Так (HKLM)  |
| `configure_uac_developer`    | ✅ Так (HKLM)  |
| `disable_telemetry`          | ✅ Так (Stop-Service) |
| `apply_dark_theme`           | ❌ Ні (HKCU)  |
| Winget install               | ❌ Ні          |

**Як запустити з правами адміна:**
```
# PowerShell (правою кнопкою → "Запуск від імені адміністратора")
cd prod_cloud
.venv\Scripts\Activate.ps1
cd client
python tui.py   # або python main.py deploy --persona developer
```

---

## 🧪 Тести

```bash
# З кореня проєкту
pytest tests/ -v
```

---

## 📡 API Endpoints

| Метод | URL                   | Опис                          |
|-------|-----------------------|-------------------------------|
| GET   | `/`                   | Статус сервера                |
| GET   | `/manifests`          | Всі 52 програми               |
| GET   | `/manifests/{id}`     | Одна програма за ID           |
| GET   | `/profile/{persona}`  | Профіль персони               |
| GET   | `/categories`         | Унікальні категорії           |

Swagger UI: http://localhost:8000/docs

---

## 📁 Структура проєкту

```
prod_cloud/
├── server/
│   ├── main.py          ← FastAPI сервер
│   ├── models.py        ← Pydantic моделі
│   └── data/
│       ├── manifests.json   ← 52 програми з Winget ID
│       └── profiles.json    ← 4 персони
├── client/
│   ├── tui.py           ← Textual TUI (NEW)
│   ├── main.py          ← Typer CLI
│   ├── auditor.py       ← HardwareAuditor (psutil)
│   ├── engine.py        ← ExecutionEngine (Winget + PowerShell)
│   └── injector.py      ← ConfigInjector (%APPDATA%)
├── configs/
│   ├── developer.json
│   ├── gamer.json
│   └── designer.json
├── tests/
│   └── test_auditor.py
└── requirements.txt
```

---

## 🐛 Troubleshooting

**Сервер не запускається:**
```bash
# Перевір що ти в папці server/
cd server
uvicorn main:app --reload --port 8000
```

**`winget` не знайдено:**
Встанови "App Installer" з Microsoft Store або через:
```powershell
winget --version   # перевірка
```

**PowerShell execution policy:**
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

**Textual не встановлено:**
```bash
pip install textual>=0.61.0
```