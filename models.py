"""
Database models for Task Tracker application.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from datetime import timezone
import enum

db = SQLAlchemy()


def utc_iso(value):
    """Serialize naive database UTC timestamps with an explicit UTC offset."""
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class UserRole(enum.Enum):
    USER = "user"
    EDITOR = "editor"
    ADMIN = "admin"


class TaskCategory(enum.Enum):
    ADHOC = "adhoc"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class TaskStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"


class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class User(UserMixin, db.Model):
    """User model for authentication and authorization."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.USER, nullable=False)
    line_id = db.Column(db.String(120), nullable=True)  # LINE user ID for notifications
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    created_tasks = db.relationship('Task', foreign_keys='Task.created_by',
                                     backref='creator', lazy='dynamic')
    assigned_tasks = db.relationship('Task', foreign_keys='Task.assigned_to',
                                      backref='assignee', lazy='dynamic')
    task_logs = db.relationship('TaskLog', backref='user', lazy='dynamic')

    def set_password(self, password):
        """Hash and set the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify the user's password."""
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        """Check if user is admin."""
        return self.role == UserRole.ADMIN

    def is_editor(self):
        """Check if user is editor or admin."""
        return self.role in [UserRole.EDITOR, UserRole.ADMIN]

    def to_dict(self):
        """Convert user to dictionary (excluding sensitive data)."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role.value,
            'line_id': self.line_id,
            'created_at': utc_iso(self.created_at),
            'is_active': self.is_active
        }


class Task(db.Model):
    """Task model for tracking work items."""
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.Enum(TaskCategory), nullable=False)
    priority = db.Column(db.Enum(TaskPriority), default=TaskPriority.MEDIUM)
    status = db.Column(db.Enum(TaskStatus), default=TaskStatus.PENDING)

    # Assignment
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Dates
    due_date = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Recurrence for recurring tasks
    is_recurring = db.Column(db.Boolean, default=False, nullable=False)
    recurrence_rule = db.Column(db.String(100), nullable=True)  # e.g., "FREQ=WEEKLY;BYDAY=MO"
    recurrence_source_id = db.Column(db.Integer, nullable=True)
    last_generated_at = db.Column(db.DateTime, nullable=True)
    last_notified = db.Column(db.DateTime, nullable=True)

    # Relationships
    logs = db.relationship('TaskLog', backref='task', lazy='dynamic', cascade='all, delete-orphan')

    def is_overdue(self):
        """Check if task is overdue."""
        if self.is_recurring:
            return False
        if self.status == TaskStatus.COMPLETED:
            return False
        if self.due_date and self.due_date < datetime.utcnow():
            return True
        return False

    def mark_completed(self):
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    def to_dict(self, include_assignee=False, include_creator=False):
        """Convert task to dictionary."""
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category.value,
            'priority': self.priority.value,
            'status': self.status.value,
            'assigned_to': self.assigned_to,
            'created_by': self.created_by,
            'due_date': utc_iso(self.due_date),
            'completed_at': utc_iso(self.completed_at),
            'created_at': utc_iso(self.created_at),
            'updated_at': utc_iso(self.updated_at),
            'is_recurring': self.is_recurring,
            'recurrence_rule': self.recurrence_rule,
            'recurrence_source_id': self.recurrence_source_id,
            'last_generated_at': utc_iso(self.last_generated_at),
            'is_overdue': self.is_overdue()
        }

        if include_assignee and self.assignee:
            data['assignee'] = {
                'id': self.assignee.id,
                'username': self.assignee.username
            }

        if include_creator and self.creator:
            data['creator'] = {
                'id': self.creator.id,
                'username': self.creator.username
            }

        return data


class TaskLog(db.Model):
    """Audit log for task changes."""
    __tablename__ = 'task_logs'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # created, updated, completed, deleted
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text, nullable=True)  # JSON string of changes

    def to_dict(self):
        """Convert log entry to dictionary."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'action': self.action,
            'timestamp': utc_iso(self.timestamp),
            'details': self.details
        }
