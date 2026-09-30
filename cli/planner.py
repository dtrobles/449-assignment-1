"""Terminal interface for the Planboard server."""

from __future__ import annotations

import argparse
import json
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000/api"


def request(path: str, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    try:
        with urlopen(Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method), timeout=5) as response:
            return json.loads(response.read()) if response.status != 204 else None
    except HTTPError as error:
        message = json.loads(error.read()).get("error", error.reason)
        raise SystemExit(f"Server rejected the request: {message}") from error
    except URLError as error:
        raise SystemExit("Cannot reach Planboard. Start it first with `jac run`.") from error


def print_tasks(tasks: list[dict]) -> None:
    if not tasks:
        print("No tasks found.")
        return
    for task in tasks:
        marker = "x" if task["completed"] else " "
        due = task["due_date"] or "no due date"
        print(f"[{marker}] {task['id']:>3}  {task['title']}  ({task['priority']}, {task['category']}, {due})")


def run() -> None:
    parser = argparse.ArgumentParser(description="Planboard command-line planner")
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="Add a task")
    add.add_argument("title")
    add.add_argument("--due", help="Due date in YYYY-MM-DD format")
    add.add_argument("--category", default="Personal")
    add.add_argument("--priority", choices=("low", "medium", "high"), default="medium")

    commands.add_parser("today", help="Show tasks due today")
    commands.add_parser("list", help="Show all tasks")
    complete = commands.add_parser("complete", help="Mark a task complete")
    complete.add_argument("task_id", type=int)

    args = parser.parse_args()
    if args.command == "add":
        task = request("/tasks", "POST", vars(args) | {"due_date": args.due})
        print(f"Added #{task['id']}: {task['title']}")
    elif args.command == "today":
        print_tasks(request(f"/tasks?date={date.today().isoformat()}"))
    elif args.command == "list":
        print_tasks(request("/tasks"))
    else:
        task = request(f"/tasks/{args.task_id}", "PATCH", {"completed": True})
        print(f"Completed #{task['id']}: {task['title']}")


if __name__ == "__main__":
    run()
