"""
Authentication and authorization helpers for Task Tracker.
"""

from functools import wraps
from flask_login import LoginManager, current_user
from flask import redirect, url_for, flash
from models import User, UserRole

login_manager = LoginManager()


def init_auth(app):
    """Initialize Flask-Login with the app."""
    login_manager.init_app(app)
    login_manager.login_view = 'login_page'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login."""
        return User.query.get(int(user_id))


def admin_required(f):
    """Decorator that requires admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login_page'))
        if not current_user.is_admin():
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def editor_required(f):
    """Decorator that requires editor or admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login_page'))
        if not current_user.is_editor():
            flash('Editor access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def can_edit_task(user, task):
    """Check if user can edit a task."""
    if user.is_admin():
        return True
    if user.is_editor():
        return True
    # Regular users can only update their own assigned tasks
    return task.assigned_to == user.id


def can_delete_task(user):
    """Check if user can delete tasks."""
    return user.is_editor()
