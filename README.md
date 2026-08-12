# Operation Task Monitoring

A lightweight Flask task-management application for tracking operational work through a Kanban dashboard.


<img width="1531" height="859" alt="image" src="https://github.com/user-attachments/assets/c609e74f-75dd-44b1-9f52-7941465276ad" />


## Features

- Role-based access for users, editors, and administrators
- Task creation, assignment, filtering, editing, completion, and deletion
- Kanban dashboard with Ad-hoc, Daily, Weekly, Monthly, and Quarterly/Yearly columns
- Unassigned tasks visible to all users
- Daily, weekly, and monthly task completion prompts
- Optional next-instance creation after the user confirms completion
- Admin settings for application title, JPG logo, SMTP, and webhook notifications
- Email and LINE-compatible webhook notifications for overdue and upcoming tasks
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
| `APP_PORT` | `1235` for `app.py`; `1239` for `run.py` | HTTP port |
| `FLASK_ENV` | `default` for `app.py`; `production` for `run.py` | Application configuration profile |
| `DEBUG` | `false` outside the development profile | Enable Flask debug mode |
| `TIMEZONE` | `Asia/Bangkok` | Scheduler and display timezone |
| `BOOTSTRAP_DEFAULT_DATA` | `true` in development; `false` in production | Create demo users and tasks |
| `SMTP_SERVER` | `localhost` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USE_TLS` | `true` | Enable STARTTLS for SMTP |
| `SMTP_USERNAME` | Empty | SMTP username |
| `SMTP_PASSWORD` | Empty | SMTP password |
| `EMAIL_FROM` | `noreply@tasktracker.local` | Sender address |
| `WEBHOOK_URL` or `LINE_WEBHOOK_URL` | Empty | Generic webhook or LINE Messaging API endpoint |
| `WEBHOOK_TOKEN` or `LINE_CHANNEL_ACCESS_TOKEN` | Empty | Webhook bearer token or LINE access token |

The admin **Settings** page stores SMTP and webhook values in the database. Non-empty saved values take precedence over environment values. It also allows an administrator to change the application title and upload a JPG logo up to 2 MB, which appear in the navigation bar and login page.

Set a strong `SECRET_KEY` and keep notification credentials outside the repository.

## Running Locally

```bash
source venv/bin/activate
FLASK_ENV=development python app.py
```

Open `http://localhost:1235` in a browser.

The development profile creates demo users and tasks by default. The demo accounts are:

- `admin` / `admin123`
- `editor` / `editor123`
- `user` / `user123`

To start development with an empty database, disable bootstrap data:

```bash
BOOTSTRAP_DEFAULT_DATA=false FLASK_ENV=development python app.py
```

Never use the demo credentials in a production deployment.

## Production Service

The repository includes `task-tracker-1239.service`, a systemd template that runs `app.py` on port `1239`. Before installing it, update the `User`, `WorkingDirectory`, `PATH`, and `ExecStart` values for the target host. Set a strong `SECRET_KEY` and change `BOOTSTRAP_DEFAULT_DATA` to `false`.

Install the edited unit as `task-tracker-1239.service`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now task-tracker-1239
sudo systemctl status task-tracker-1239
```

`run.py` is a convenience launcher with production defaults and port `1239`. It currently enables bootstrap data unless `BOOTSTRAP_DEFAULT_DATA=false` is supplied, so do not use it unchanged for a production database.

The built-in Flask server is suitable for internal use and development. For public production traffic, place the application behind a production WSGI server and reverse proxy.

## Project Layout

```text
app.py                 Flask routes and application factory
auth.py                Authentication and role checks
config.py              Environment-based configuration
models.py              SQLAlchemy models and serialization
notifications.py       Email and LINE notifications
scheduler.py           Background notification jobs
run.py                 Convenience launcher for port 1239
task-tracker-1239.service
                       systemd service template for port 1239
templates/             Jinja2 HTML templates
static/                CSS, browser JavaScript, and uploaded branding assets
```

## License

This project is licensed under the Apache License 2.0. See `LICENSE`.
