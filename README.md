# AutoDeploy — Система автоматизованого розгортання Windows

Клієнт-серверна система для автоматизації налаштування Windows 11 через єдиний термінальний інтерфейс.

## Структура проєкту

```
project/
├── server/
│   ├── main.py          ← FastAPI сервер
│   ├── models.py        ← Pydantic моделі
│   └── data/
│       ├── manifests.json   ← База програм
│       └── profiles.json    ← Профілі персон
├── client/
│   ├── main.py          ← CLI (Typer)
│   ├── auditor.py       ← Аудит заліза (psutil + Rich)
│   ├── engine.py        ← Встановлення (Winget + PowerShell)
│   └── injector.py      ← Копіювання конфігів
├── configs/
│   ├── developer.json
│   ├── gamer.json
│   └── designer.json
└── tests/
    └── test_auditor.py
```

## Встановлення

```bash
pip install -r requirements.txt
```

## Запуск сервера

```bash
cd server
uvicorn main:app --reload --port 8000
```

API документація: http://localhost:8000/docs

## Використання CLI

```bash
cd client

# Аудит системи
python main.py audit

# Повне розгортання для розробника
python main.py deploy --persona developer

# Повне розгортання для геймера
python main.py deploy --persona gamer

# Встановити одну програму
python main.py install vscode

# Режим симуляції (без реального встановлення)
python main.py deploy --persona developer --dry-run
```

## Логіка адаптивності (Smart System)

| RAM       | Профіль    | Особливості                        |
|-----------|------------|------------------------------------|
| < 8 GB    | **Lite**   | Без анімацій, прозорості, ефектів  |
| ≥ 8 GB    | **Ultimate** | Повний функціонал                |

## Персони

| Персона    | Програми                          | Налаштування              |
|------------|-----------------------------------|---------------------------|
| Developer  | VSCode, Git, Python, Node.js      | Темна тема, dev-mode      |
| Gamer      | Steam, Discord, OBS               | Оптимізація продуктивності|
| Designer   | Figma, Chrome                     | Калібрування кольору      |

## Тести

```bash
pytest tests/ -v
```
