"""
Background scheduler for task notifications and recurring task management.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
from models import db, Task, TaskStatus, TaskCategory, User, TaskLog
from notifications import send_email_notification, send_line_notification

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Background scheduler for task-related periodic tasks."""

    def __init__(self, app=None):
        self.scheduler = None
        self.app = app

    def init_app(self, app):
        """Initialize scheduler with Flask app."""
        self.app = app
        self.scheduler = BackgroundScheduler()
        timezone = ZoneInfo(app.config.get('TIMEZONE', 'Asia/Bangkok'))

        # Add jobs
        self.scheduler.add_job(
            func=self.check_overdue_tasks,
            trigger='interval',
            minutes=5,
            id='check_overdue',
            name='Check for overdue tasks every 5 minutes'
        )

        self.scheduler.add_job(
            func=self.check_upcoming_tasks,
            trigger='interval',
            hours=1,
            id='check_upcoming',
            name='Check for upcoming due tasks every hour'
        )

        self.scheduler.add_job(
            func=self.send_daily_summaries,
            trigger=CronTrigger(hour=8, minute=0, timezone=timezone),
            id='daily_summary',
            name='Send daily task summaries at 8 AM'
        )

        self.scheduler.add_job(
            func=self.update_overdue_status,
            trigger='interval',
            minutes=10,
            id='update_overdue',
            name='Update task status to overdue every 10 minutes'
        )

        self.scheduler.add_job(
            func=self.generate_daily_tasks,
            trigger=CronTrigger(hour=0, minute=1, timezone=timezone),
            id='generate_daily_tasks',
            name='Generate daily recurring tasks at 00:01'
        )

        self.scheduler.add_job(
            func=self.generate_weekly_tasks,
            trigger=CronTrigger(day_of_week='mon', hour=0, minute=1, timezone=timezone),
            id='generate_weekly_tasks',
            name='Generate weekly recurring tasks every Monday at 00:01'
        )

        self.scheduler.add_job(
            func=self.generate_monthly_tasks,
            trigger=CronTrigger(day=1, hour=0, minute=1, timezone=timezone),
            id='generate_monthly_tasks',
            name='Generate monthly recurring tasks on day 1 at 00:01'
        )

    def start(self):
        """Start the scheduler."""
        if self.scheduler and not self.scheduler.running:
            self.scheduler.start()
            logger.info("Task scheduler started")

    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Task scheduler shutdown")

    def is_recurring_category(self, category):
        """Return True for categories that automatically roll to the next due date."""
        return category in [TaskCategory.DAILY, TaskCategory.WEEKLY, TaskCategory.MONTHLY]

    def calculate_next_due_date(self, current_date, category):
        """Public wrapper for the next due date calculation."""
        return self._calculate_next_due_date(current_date, category)

    def generate_daily_tasks(self):
        """Generate daily recurring tasks."""
        scheduled_for = datetime.utcnow().replace(hour=0, minute=1, second=0, microsecond=0)
        self._generate_recurring_tasks(TaskCategory.DAILY, scheduled_for)

    def generate_weekly_tasks(self):
        """Generate weekly recurring tasks."""
        scheduled_for = datetime.utcnow().replace(hour=0, minute=1, second=0, microsecond=0)
        self._generate_recurring_tasks(TaskCategory.WEEKLY, scheduled_for)

    def generate_monthly_tasks(self):
        """Generate monthly recurring tasks."""
        scheduled_for = datetime.utcnow().replace(hour=0, minute=1, second=0, microsecond=0)
        self._generate_recurring_tasks(TaskCategory.MONTHLY, scheduled_for)

    def _generate_recurring_tasks(self, category, scheduled_for):
        """Create task instances from recurring templates."""
        with self.app.app_context():
            try:
                templates = Task.query.filter(
                    Task.category == category,
                    Task.is_recurring.is_(True),
                    Task.recurrence_source_id.is_(None),
                    Task.status != TaskStatus.COMPLETED
                ).all()

                created_count = 0
                for template in templates:
                    if self._was_generated_for_period(template, scheduled_for, category):
                        continue

                    new_task = Task(
                        title=template.title,
                        description=template.description,
                        category=template.category,
                        priority=template.priority,
                        assigned_to=template.assigned_to,
                        created_by=template.created_by,
                        due_date=self._scheduled_due_date(template, scheduled_for),
                        recurrence_rule=template.recurrence_rule,
                        status=TaskStatus.PENDING,
                        is_recurring=False,
                        recurrence_source_id=template.id
                    )
                    db.session.add(new_task)
                    db.session.flush()

                    template.last_generated_at = scheduled_for

                    log = TaskLog(
                        task_id=new_task.id,
                        user_id=template.created_by,
                        action='auto_created',
                        details=f"Auto-created from recurring template {template.id}"
                    )
                    db.session.add(log)
                    created_count += 1

                db.session.commit()
                logger.info(f"Generated {created_count} recurring tasks for {category.value}")

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error generating recurring tasks for {category.value}: {e}")

    def _scheduled_due_date(self, template, scheduled_for):
        """Build the due date for a generated task."""
        if not template.due_date:
            return scheduled_for

        return scheduled_for.replace(
            hour=template.due_date.hour,
            minute=template.due_date.minute,
            second=template.due_date.second,
            microsecond=template.due_date.microsecond
        )

    def _was_generated_for_period(self, template, scheduled_for, category):
        """Prevent duplicate generation for the same recurrence period."""
        if not template.last_generated_at:
            return False

        last_generated = template.last_generated_at
        if category == TaskCategory.DAILY:
            return last_generated.date() == scheduled_for.date()
        if category == TaskCategory.WEEKLY:
            return last_generated.isocalendar()[:2] == scheduled_for.isocalendar()[:2]
        if category == TaskCategory.MONTHLY:
            return last_generated.year == scheduled_for.year and last_generated.month == scheduled_for.month
        return False

    def check_overdue_tasks(self):
        """Check for overdue tasks and send notifications."""
        with self.app.app_context():
            try:
                overdue_tasks = Task.query.filter(
                    Task.is_recurring.is_(False),
                    Task.due_date < datetime.utcnow(),
                    Task.status != TaskStatus.COMPLETED,
                    Task.status != TaskStatus.OVERDUE
                ).all()

                for task in overdue_tasks:
                    # Mark as overdue
                    task.status = TaskStatus.OVERDUE

                    # Send notification if assigned
                    if task.assigned_to and task.assignee:
                        task_dict = task.to_dict()

                        # Email notification
                        if task.assignee.email:
                            send_email_notification(
                                task.assignee.email,
                                f"⚠️ OVERDUE Task: {task.title}",
                                task_dict
                            )

                        # LINE notification
                        if task.assignee.line_id:
                            send_line_notification(
                                task.assignee.line_id,
                                task_dict,
                                'overdue'
                            )

                        # Update last notified
                        task.last_notified = datetime.utcnow()

                        # Log the notification
                        log = TaskLog(
                            task_id=task.id,
                            user_id=task.assigned_to,
                            action='notified_overdue',
                            details=f"Task marked as overdue and notification sent"
                        )
                        db.session.add(log)

                db.session.commit()
                logger.info(f"Checked {len(overdue_tasks)} overdue tasks")

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error checking overdue tasks: {e}")

    def check_upcoming_tasks(self):
        """Check for tasks due within 24 hours and send notifications."""
        with self.app.app_context():
            try:
                upcoming_deadline = datetime.utcnow() + timedelta(hours=24)

                upcoming_tasks = Task.query.filter(
                    Task.is_recurring.is_(False),
                    Task.due_date <= upcoming_deadline,
                    Task.due_date > datetime.utcnow(),
                    Task.status != TaskStatus.COMPLETED
                ).all()

                for task in upcoming_tasks:
                    # Check if we haven't notified in the last 12 hours
                    if not task.last_notified or task.last_notified < datetime.utcnow() - timedelta(hours=12):
                        if task.assigned_to and task.assignee:
                            task_dict = task.to_dict()

                            # Email notification
                            if task.assignee.email:
                                send_email_notification(
                                    task.assignee.email,
                                    f"🔔 Upcoming Task Due: {task.title}",
                                    task_dict
                                )

                            # LINE notification
                            if task.assignee.line_id:
                                send_line_notification(
                                    task.assignee.line_id,
                                    task_dict,
                                    'upcoming'
                                )

                            task.last_notified = datetime.utcnow()

                            # Log the notification
                            log = TaskLog(
                                task_id=task.id,
                                user_id=task.assigned_to,
                                action='notified_upcoming',
                                details=f"Upcoming due date notification sent"
                            )
                            db.session.add(log)

                db.session.commit()
                logger.info(f"Checked {len(upcoming_tasks)} upcoming tasks")

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error checking upcoming tasks: {e}")

    def send_daily_summaries(self):
        """Send daily task summaries to all users."""
        with self.app.app_context():
            try:
                users = User.query.filter_by(is_active=True).all()

                for user in users:
                    # Get task counts
                    total_tasks = Task.query.filter_by(assigned_to=user.id).count()
                    completed_today = Task.query.filter(
                        Task.is_recurring.is_(False),
                        Task.assigned_to == user.id,
                        Task.status == TaskStatus.COMPLETED,
                        Task.completed_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    ).count()
                    pending = Task.query.filter(
                        Task.is_recurring.is_(False),
                        Task.assigned_to == user.id,
                        Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
                    ).count()
                    overdue = Task.query.filter(
                        Task.is_recurring.is_(False),
                        Task.assigned_to == user.id,
                        Task.status == TaskStatus.OVERDUE
                    ).count()

                    summary = {
                        'title': f"Daily Summary for {user.username}",
                        'category': 'daily_summary',
                        'priority': 'medium',
                        'status': 'summary',
                        'description': f"""
You have {pending} pending tasks and {overdue} overdue tasks.
Completed {completed_today} tasks today.
Total tasks assigned: {total_tasks}
                        """.strip(),
                        'due_date': datetime.now().strftime('%Y-%m-%d')
                    }

                    # Send summary
                    if user.email:
                        send_email_notification(
                            user.email,
                            f"📊 Daily Task Summary - {datetime.now().strftime('%Y-%m-%d')}",
                            summary
                        )

                logger.info(f"Sent daily summaries to {len(users)} users")

            except Exception as e:
                logger.error(f"Error sending daily summaries: {e}")

    def update_overdue_status(self):
        """Update task status to overdue for past-due tasks."""
        with self.app.app_context():
            try:
                overdue = Task.query.filter(
                    Task.is_recurring.is_(False),
                    Task.due_date < datetime.utcnow(),
                    Task.status == TaskStatus.PENDING
                ).all()

                for task in overdue:
                    task.status = TaskStatus.OVERDUE

                db.session.commit()
                logger.info(f"Updated {len(overdue)} tasks to overdue status")

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating overdue status: {e}")

    def create_next_recurring_task(self, completed_task):
        """
        Create the next instance of a recurring task.

        Args:
            completed_task: The completed recurring task
        """
        with self.app.app_context():
            try:
                if not completed_task.recurrence_rule:
                    return

                # Calculate next due date based on recurrence
                current_due = completed_task.due_date or datetime.utcnow()
                next_due = self._calculate_next_due_date(current_due, completed_task.category)

                if next_due:
                    new_task = Task(
                        title=completed_task.title,
                        description=completed_task.description,
                        category=completed_task.category,
                        priority=completed_task.priority,
                        assigned_to=completed_task.assigned_to,
                        created_by=completed_task.created_by,
                        due_date=next_due,
                        recurrence_rule=completed_task.recurrence_rule,
                        status=TaskStatus.PENDING
                    )
                    db.session.add(new_task)
                    db.session.flush()

                    # Log the creation
                    log = TaskLog(
                        task_id=new_task.id,
                        user_id=completed_task.created_by,
                        action='auto_created',
                        details=f"Auto-created from recurring task {completed_task.id}"
                    )
                    db.session.add(log)

                    db.session.commit()
                    logger.info(f"Created next recurring task {new_task.id} from {completed_task.id}")

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error creating next recurring task: {e}")

    def _calculate_next_due_date(self, current_date, category):
        """Calculate the next due date based on task category."""
        if category == TaskCategory.DAILY:
            return current_date + timedelta(days=1)
        elif category == TaskCategory.WEEKLY:
            return current_date + timedelta(weeks=1)
        elif category == TaskCategory.MONTHLY:
            # Add approximately one month
            if current_date.month == 12:
                return current_date.replace(year=current_date.year + 1, month=1)
            else:
                new_month = current_date.month + 1
                max_day = self._days_in_month(current_date.year, new_month)
                new_day = min(current_date.day, max_day)
                return current_date.replace(month=new_month, day=new_day)
        elif category == TaskCategory.QUARTERLY:
            return current_date + timedelta(days=90)
        elif category == TaskCategory.YEARLY:
            next_year = current_date.year + 1
            max_day = self._days_in_month(next_year, current_date.month)
            return current_date.replace(year=next_year, day=min(current_date.day, max_day))
        else:
            return None

    def _days_in_month(self, year, month):
        """Get the number of days in a month."""
        if month == 12:
            return 31
        next_month = month + 1
        first_of_next = datetime(year, next_month, 1)
        last_of_current = first_of_next - timedelta(days=1)
        return last_of_current.day


# Global scheduler instance
task_scheduler = TaskScheduler()
