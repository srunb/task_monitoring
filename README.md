# T.Cloud Operation Task Monitoring

A lightweight Flask task-management application for tracking operational work through a Kanban dashboard.

## Features

- Role-based access for users, editors, and administrators
- Task creation, assignment, filtering, editing, completion, and deletion
- Kanban dashboard with Ad-hoc, Daily, Weekly, Monthly, and Quarterly/Yearly columns
- Unassigned tasks visible to all users
- Daily, weekly, and monthly recurring task templates
- Automatic recurring task generation:
  - Daily at `00:01`
  - Every Monday at `00:01`
  - On the first day of each month at `00:01`
- Email and LINE notification hooks for overdue and upcoming tasks
- Bangkok timezone support using `Asia/Bangkok`
- Dark mode and responsive browser interface

## Requirements

- Python 3.12 or newer
- SQLite
- SMTP credentials for email notifications, if required
- LINE Messaging API credentials, if required

## Installation

```bash
git clone https://github.com/srunb/task_monitoring.git
cd task_monitoring
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

The application reads configuration from environment variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | Development fallback | Flask session signing key |
| `DATABASE_PATH` | `instance/tasktracker.db` | SQLite database path |
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `1235` | HTTP port |
| `TIMEZONE` | `Asia/Bangkok` | Scheduler and display timezone |
| `BOOTSTRAP_DEFAULT_DATA` | `false` in production | Create demo users and tasks |
| `SMTP_SERVER` | `localhost` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USERNAME` | Empty | SMTP username |
| `SMTP_PASSWORD` | Empty | SMTP password |
| `EMAIL_FROM` | `noreply@tasktracker.local` | Sender address |
| `LINE_WEBHOOK_URL` | Empty | LINE API endpoint |
| `LINE_CHANNEL_ACCESS_TOKEN` | Empty | LINE access token |

Set a strong `SECRET_KEY` and keep notification credentials outside the repository.

## Running Locally

```bash
source venv/bin/activate
FLASK_ENV=development python app.py
```

Open `http://localhost:1235` in a browser.

For development, the default bootstrap data can be enabled with:

```bash
BOOTSTRAP_DEFAULT_DATA=true FLASK_ENV=development python app.py
```

Never use the demo credentials in a production deployment.

## Production Service

The repository includes `task-tracker.service` for systemd deployments. Update its environment and paths for the target host, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now task-tracker
sudo systemctl status task-tracker
```

The built-in Flask server is suitable for internal use and development. For public production traffic, place the application behind a production WSGI server and reverse proxy.

## Project Layout

```text
app.py                 Flask routes and application factory
auth.py                Authentication and role checks
config.py              Environment-based configuration
models.py              SQLAlchemy models and serialization
notifications.py       Email and LINE notifications
scheduler.py           Background jobs and recurring task generation
templates/             Jinja2 HTML templates
static/                CSS and browser JavaScript
```

## License

This project is licensed under the MIT License. See `LICENSE`.
