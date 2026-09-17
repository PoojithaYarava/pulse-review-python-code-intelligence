# Pulse Review

A lightweight Python code-review assistant built with FastAPI, AST analysis, and SQLite.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. API docs are available at http://127.0.0.1:8000/docs.

## Run with Docker

Build and start the app with Docker Compose:

```powershell
docker compose up --build
```

Open http://127.0.0.1:8000. Review history is stored in the local `data` folder through a mounted SQLite volume. Stop the app with:

```powershell
docker compose down
```

## What it checks

- Syntax errors with `ast.parse`
- Loop depth and sorting-based complexity estimates
- Long functions, parameter count, naming, unused variables, bare exceptions, and nested conditionals
- Review score and issue history in SQLite

Complexity is intentionally a static approximation, not a formal proof of runtime behavior.

## Test

```powershell
pytest
```
