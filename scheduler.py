"""
Background worker for task notifications.

Uses a lightweight daemon thread instead of APScheduler.  The thread wakes
every hour to check overdue/upcoming tasks and send notifications.
"""

import threading
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from models import db, Task, TaskStatus, TaskCategory, User, TaskLog
from notifications import send_email_notification, send_line_notification

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 3600  # seconds (1 hour)


class TaskScheduler:
    """Background worker for task-related periodic checks."""

    def __init__(self, app=None):
        self.app = app
        self._thread = None
        self._stop_event = None
        self._last_summary_date = None

    def init_app(self, app):
        """Store Flask app reference."""
        self.app = app

    # -----------------------------------------------------------
    # Thread lifecycle
    # -----------------------------------------------------------

    def start(self):
        """Start the background thread."""
        if self._thread is not None:
            return
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name='task-worker')
        self._thread.start()
        logger.info("Background task worker started (interval=%ds)", CHECK_INTERVAL)

    def shutdown(self):
        """Signal the background thread to stop."""
        if self._stop_event:
            self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
            self._stop_event = None
            logger.info("Background task worker stopped")

    def _run_loop(self):
        """Main loop – runs immediately then every CHECK_INTERVAL seconds."""
        # Brief delay so Flask finishes booting
        self._stop_event.wait(timeout=5)

        while not self._stop_event.is_set():
            try:
                self.update_overdue_status()
                self.check_overdue_tasks()
                self.check_upcoming_tasks()
                self._maybe_send_daily_summary()
            except Exception as e:
                logger.error("Background loop error: %s", e)

            self._stop_event.wait(timeout=CHECK_INTERVAL)

    # -----------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------

    def _get_tz(self):
        return ZoneInfo(self.app.config.get('TIMEZONE', 'Asia/Bangkok'))

    def is_recurring_category(self, category):
        """Return True for categories that support recurring task creation."""
        return category in [TaskCategory.DAILY, TaskCategory.WEEKLY, TaskCategory.MONTHLY]

    def _calculate_next_due_date(self, current_date, category):
        if category == TaskCategory.DAILY:
            return current_date + timedelta(days=1)
        elif category == TaskCategory.WEEKLY:
            return current_date + timedelta(weeks=1)
        elif category == TaskCategory.MONTHLY:
            if current_date.month == 12:
                return current_date.replace(year=current_date.year + 1, month=1)
            else:
                new_month = current_date.month + 1
                max_day = self._days_in_month(current_date.year, new_month)
                return current_date.replace(month=new_month, day=min(current_date.day, max_day))
        elif category == TaskCategory.QUARTERLY:
            return current_date + timedelta(days=90)
        elif category == TaskCategory.YEARLY:
            next_year = current_date.year + 1
            max_day = self._days_in_month(next_year, current_date.month)
            return current_date.replace(year=next_year, day=min(current_date.day, max_day))
        else:
            return None

    def _days_in_month(self, year, month):
        if month == 12:
            return 31
        next_month = datetime(year, month + 1, 1)
        return (next_month - timedelta(days=1)).day

    # -----------------------------------------------------------
    # Background checks (called from _run_loop)
    # -----------------------------------------------------------

    def update_overdue_status(self):
        """Mark past-due pending tasks as overdue."""
        with self.app.app_context():
            try:
                overdue = Task.query.filter(
                    Task.due_date < datetime.utcnow(),
                    Task.status == TaskStatus.PENDING
                ).all()

                for task in overdue:
                    task.status = TaskStatus.OVERDUE

                db.session.commit()
                if overdue:
                    logger.info("Updated %d tasks to overdue", len(overdue))

            except Exception as e:
                db.session.rollback()
                logger.error("Error updating overdue status: %s", e)

    def check_overdue_tasks(self):
        """Send notifications for newly overdue tasks."""
        with self.app.app_context():
            try:
                overdue_tasks = Task.query.filter(
                    Task.due_date < datetime.utcnow(),
                    Task.status != TaskStatus.COMPLETED,
                    Task.status != TaskStatus.OVERDUE
                ).all()

                for task in overdue_tasks:
                    task.status = TaskStatus.OVERDUE

                    if task.assigned_to and task.assignee:
                        task_dict = task.to_dict()

                        if task.assignee.email:
                            send_email_notification(
                                task.assignee.email,
                                f"⚠️ OVERDUE Task: {task.title}",
                                task_dict
                            )

                        if task.assignee.line_id:
                            send_line_notification(task.assignee.line_id, task_dict, 'overdue')

                        task.last_notified = datetime.utcnow()

                        db.session.add(TaskLog(
                            task_id=task.id,
                            user_id=task.assigned_to,
                            action='notified_overdue',
                            details="Task marked as overdue and notification sent"
                        ))

                db.session.commit()
                if overdue_tasks:
                    logger.info("Notified %d overdue tasks", len(overdue_tasks))

            except Exception as e:
                db.session.rollback()
                logger.error("Error checking overdue tasks: %s", e)

    def check_upcoming_tasks(self):
        """Send notifications for tasks due within 24 hours."""
        with self.app.app_context():
            try:
                upcoming_deadline = datetime.utcnow() + timedelta(hours=24)

                upcoming_tasks = Task.query.filter(
                    Task.due_date <= upcoming_deadline,
                    Task.due_date > datetime.utcnow(),
                    Task.status != TaskStatus.COMPLETED
                ).all()

                notified = 0
                for task in upcoming_tasks:
                    if task.last_notified and task.last_notified >= datetime.utcnow() - timedelta(hours=12):
                        continue

                    if task.assigned_to and task.assignee:
                        task_dict = task.to_dict()

                        if task.assignee.email:
                            send_email_notification(
                                task.assignee.email,
                                f"🔔 Upcoming Task Due: {task.title}",
                                task_dict
                            )

                        if task.assignee.line_id:
                            send_line_notification(task.assignee.line_id, task_dict, 'upcoming')

                        task.last_notified = datetime.utcnow()
                        notified += 1

                        db.session.add(TaskLog(
                            task_id=task.id,
                            user_id=task.assigned_to,
                            action='notified_upcoming',
                            details="Upcoming due date notification sent"
                        ))

                db.session.commit()
                if notified:
                    logger.info("Notified %d upcoming tasks", notified)

            except Exception as e:
                db.session.rollback()
                logger.error("Error checking upcoming tasks: %s", e)

    def _maybe_send_daily_summary(self):
        """Send daily summaries once per day after 8 AM local time."""
        tz = self._get_tz()
        now_local = datetime.now(tz)
        today = now_local.date()

        if now_local.hour < 8 or self._last_summary_date == today:
            return

        self._last_summary_date = today
        self.send_daily_summaries()

    def send_daily_summaries(self):
        """Send daily task summaries to all active users."""
        with self.app.app_context():
            try:
                users = User.query.filter_by(is_active=True).all()

                for user in users:
                    total_tasks = Task.query.filter_by(assigned_to=user.id).count()
                    completed_today = Task.query.filter(
                        Task.assigned_to == user.id,
                        Task.status == TaskStatus.COMPLETED,
                        Task.completed_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    ).count()
                    pending = Task.query.filter(
                        Task.assigned_to == user.id,
                        Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
                    ).count()
                    overdue = Task.query.filter(
                        Task.assigned_to == user.id,
                        Task.status == TaskStatus.OVERDUE
                    ).count()

                    summary = {
                        'title': f"Daily Summary for {user.username}",
                        'category': 'daily_summary',
                        'priority': 'medium',
                        'status': 'summary',
                        'description': (
                            f"You have {pending} pending tasks and {overdue} overdue tasks.\n"
                            f"Completed {completed_today} tasks today.\n"
                            f"Total tasks assigned: {total_tasks}"
                        ),
                        'due_date': datetime.now().strftime('%Y-%m-%d')
                    }

                    if user.email:
                        send_email_notification(
                            user.email,
                            f"📊 Daily Task Summary - {datetime.now().strftime('%Y-%m-%d')}",
                            summary
                        )

                logger.info("Sent daily summaries to %d users", len(users))

            except Exception as e:
                logger.error("Error sending daily summaries: %s", e)


# Global scheduler instance
task_scheduler = TaskScheduler()
