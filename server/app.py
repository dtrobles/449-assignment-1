"""Shared planner server launched through the Jac entry point."""

from __future__ import annotations

import json
import mimetypes
import sqlite3
from datetime import date, datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "planner.db"
WEB_ROOT = PROJECT_ROOT / "web"
MOBILE_ROOT = PROJECT_ROOT / "mobile"
VALID_PRIORITIES = {"low", "medium", "high"}


def connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    with connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL CHECK(length(trim(title)) > 0),
                due_date TEXT,
                category TEXT NOT NULL DEFAULT 'Personal',
                priority TEXT NOT NULL DEFAULT 'medium',
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )


def task_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "due_date": row["due_date"],
        "category": row["category"],
        "priority": row["priority"],
        "completed": bool(row["completed"]),
        "created_at": row["created_at"],
    }


class PlannerHandler(SimpleHTTPRequestHandler):
    """Serves the two clients and the small shared JSON API."""

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/tasks":
            self.list_tasks(parse_qs(parsed.query))
        elif parsed.path == "/api/summary":
            self.summary()
        elif parsed.path.startswith("/mobile"):
            self.serve_static(MOBILE_ROOT, parsed.path.removeprefix("/mobile").lstrip("/") or "index.html")
        elif parsed.path == "/" or parsed.path.startswith("/assets/"):
            self.serve_static(WEB_ROOT, "/index.html" if parsed.path == "/" else parsed.path)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/tasks":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        payload = self.read_json()
        if payload is None:
            return
        title = str(payload.get("title", "")).strip()
        due_date = payload.get("due_date") or None
        category = str(payload.get("category", "Personal")).strip() or "Personal"
        priority = str(payload.get("priority", "medium")).lower()
        if not title:
            self.json_response({"error": "A task title is required."}, HTTPStatus.BAD_REQUEST)
            return
        if priority not in VALID_PRIORITIES:
            self.json_response({"error": "Priority must be low, medium, or high."}, HTTPStatus.BAD_REQUEST)
            return
        if due_date:
            try:
                date.fromisoformat(str(due_date))
            except ValueError:
                self.json_response({"error": "Due date must use YYYY-MM-DD."}, HTTPStatus.BAD_REQUEST)
                return
        with connection() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (title, due_date, category, priority, created_at) VALUES (?, ?, ?, ?, ?)",
                (title, due_date, category, priority, datetime.now(timezone.utc).isoformat()),
            )
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
        self.json_response(task_dict(row), HTTPStatus.CREATED)

    def do_PATCH(self) -> None:  # noqa: N802
        task_id = self.task_id()
        if task_id is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        payload = self.read_json()
        if payload is None:
            return
        if set(payload) != {"completed"} or not isinstance(payload["completed"], bool):
            self.json_response({"error": "Only a boolean completed value may be updated."}, HTTPStatus.BAD_REQUEST)
            return
        with connection() as conn:
            cursor = conn.execute(
                "UPDATE tasks SET completed = ? WHERE id = ?", (int(payload["completed"]), task_id)
            )
            if cursor.rowcount == 0:
                self.json_response({"error": "Task not found."}, HTTPStatus.NOT_FOUND)
                return
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        self.json_response(task_dict(row))

    def do_DELETE(self) -> None:  # noqa: N802
        task_id = self.task_id()
        if task_id is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        with connection() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cursor.rowcount == 0:
            self.json_response({"error": "Task not found."}, HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def list_tasks(self, query: dict[str, list[str]]) -> None:
        due_date = query.get("date", [None])[0]
        completed = query.get("completed", [None])[0]
        clauses, values = [], []
        if due_date:
            try:
                date.fromisoformat(due_date)
            except ValueError:
                self.json_response({"error": "Date must use YYYY-MM-DD."}, HTTPStatus.BAD_REQUEST)
                return
            clauses.append("due_date = ?")
            values.append(due_date)
        if completed in {"true", "false"}:
            clauses.append("completed = ?")
            values.append(int(completed == "true"))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM tasks {where} ORDER BY completed, due_date IS NULL, due_date, "
                "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, id DESC",
                values,
            ).fetchall()
        self.json_response([task_dict(row) for row in rows])

    def summary(self) -> None:
        today = date.today().isoformat()
        with connection() as conn:
            totals = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(completed) AS completed,
                    SUM(CASE WHEN due_date = ? AND NOT completed THEN 1 ELSE 0 END) AS today,
                    SUM(CASE WHEN due_date < ? AND NOT completed THEN 1 ELSE 0 END) AS overdue
                FROM tasks
                """,
                (today, today),
            ).fetchone()
        self.json_response({key: int(totals[key] or 0) for key in totals.keys()})

    def read_json(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self.json_response({"error": "Request body must be valid JSON."}, HTTPStatus.BAD_REQUEST)
            return None
        if not isinstance(payload, dict):
            self.json_response({"error": "Request body must be a JSON object."}, HTTPStatus.BAD_REQUEST)
            return None
        return payload

    def task_id(self) -> int | None:
        pieces = urlparse(self.path).path.split("/")
        if len(pieces) != 4 or pieces[:3] != ["", "api", "tasks"]:
            return None
        try:
            return int(pieces[3])
        except ValueError:
            return None

    def serve_static(self, root: Path, request_path: str) -> None:
        candidate = (root / request_path.lstrip("/")).resolve()
        if root.resolve() not in candidate.parents or not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        content = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def json_response(self, body: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[planner] {self.address_string()} - {format % args}")


def run() -> None:
    initialize_database()
    server = ThreadingHTTPServer(("127.0.0.1", 8000), PlannerHandler)
    print("Planboard is running at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPlanboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
