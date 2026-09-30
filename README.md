## Name and UMID
- Dylan Robles (dtrobles)

## Features

- Persistent SQLite task storage with due dates, categories, and priorities
- Web dashboard with task capture, summary counts, completion, and deletion
- Installable mobile PWA for quickly adding and completing today's tasks
- Terminal client for adding tasks, viewing today's plan, listing tasks, and completing items

## Setup and run

Planboard requires Python 3.11+ and Jac.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
jac run
```

Then open <http://127.0.0.1:8000>. Task data is saved locally in `data\planner.db` and remains available when the server restarts.

## Mobile app

With the server running, open <http://127.0.0.1:8000/mobile/> on a phone that can reach the computer running the server. To use it on another device, change the server binding in `server\app.py` from `127.0.0.1` to the computer's local network address, then open that address on the phone. Use the browser's **Install app** or **Add to Home Screen** action to install the PWA.

## CLI

Start the server with `jac run` in one terminal. In another activated terminal:

```powershell
py cli\planner.py add "Read Jac documentation" --due 2026-10-05 --category Coursework --priority high
py cli\planner.py today
py cli\planner.py list
py cli\planner.py complete 1
```

## Architecture

`main.jac` is the default Jac entry point and launches the shared planner server. The web dashboard and mobile PWA are served by that server and call its JSON API. The terminal client calls the same API; `cli\main.jac` remains its Jac entry point for Jac environments that support script arguments. This keeps every interface synchronized while SQLite provides persistence between sessions.

# Short Description
Planboard uses one shared Jac-launched server and SQLite database as its core. The web frontend provides a full dashboard for adding, organizing, completing, and deleting tasks. The mobile PWA connects to the same API for quick daily task capture and completion on a phone. The CLI also uses that API, making it easy to add tasks or check today’s plan from a terminal. Because each interface communicates with the same backend, every task stays synchronized.

What makes the project impressive is that it is a complete, cohesive planning tool rather than separate demos: it has persistent data, a polished responsive web interface, a mobile-installable experience, useful terminal workflows, input validation, and a single shared backend that keeps every client consistent.
