"""
Task Tracker - Flask Web Application
A task management system with role-based access control and notifications.
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_cors import CORS
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_, inspect, text

from config import config
from models import db, User, Task, TaskLog, UserRole, TaskCategory, TaskStatus, TaskPriority
from auth import init_auth, admin_required, editor_required, can_edit_task, can_delete_task
from notifications import send_email_notification, send_line_notification
from scheduler import task_scheduler


def create_app(config_name='default'):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    def visible_task_query(query):
        """Limit task visibility for regular users."""
        if current_user.is_editor():
            return query
        return query.filter(
            Task.is_recurring.is_(False),
            or_(Task.assigned_to == current_user.id, Task.assigned_to.is_(None))
        )

    def recurrence_rule_for_category(category):
        """Store recurrence metadata for recurring task categories."""
        if task_scheduler.is_recurring_category(category):
            return f'FREQ={category.value.upper()}'
        return None

    def parse_recurring_flag(data, category):
        """Recurring templates are only supported for daily, weekly, and monthly tasks."""
        is_recurring = data.get('is_recurring', False)
        if isinstance(is_recurring, str):
            is_recurring = is_recurring.lower() == 'true'
        return bool(is_recurring) and task_scheduler.is_recurring_category(category)

    # Initialize extensions
    CORS(app)
    db.init_app(app)
    init_auth(app)

    # Initialize scheduler
    task_scheduler.init_app(app)

    with app.app_context():
        db.create_all()
        ensure_schema_updates()
        if app.config['BOOTSTRAP_DEFAULT_DATA']:
            create_default_data()
        elif User.query.count() == 0:
            app.logger.warning(
                'No users found. Create users manually or temporarily set BOOTSTRAP_DEFAULT_DATA=true for initial setup.'
            )

    # ============ Routes ============

    @app.route('/')
    def index():
        """Main page - redirect to dashboard or login."""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login_page'))

    @app.route('/login')
    def login_page():
        """Serve login page."""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('login.html')

    @app.route('/dashboard')
    @login_required
    def dashboard():
        """Serve main dashboard page."""
        return render_template('dashboard.html')

    @app.route('/tasks')
    @login_required
    def tasks_page():
        """Serve task management page."""
        return render_template('tasks.html')

    @app.route('/users')
    @admin_required
    def users_page():
        """Serve user management page (admin only)."""
        return render_template('users.html')

    # ============ API: Authentication ============

    @app.route('/api/auth/login', methods=['POST'])
    def api_login():
        """Handle user login."""
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=data.get('remember', False))
            return jsonify({
                'success': True,
                'user': user.to_dict(),
                'message': 'Login successful'
            })

        return jsonify({
            'success': False,
            'message': 'Invalid username or password'
        }), 401

    @app.route('/api/auth/logout', methods=['POST'])
    @login_required
    def api_logout():
        """Handle user logout."""
        logout_user()
        return jsonify({'success': True, 'message': 'Logged out successfully'})

    @app.route('/api/auth/me', methods=['GET'])
    @login_required
    def api_me():
        """Get current user info."""
        return jsonify({'user': current_user.to_dict()})

    # ============ API: Tasks ============

    @app.route('/api/tasks', methods=['GET'])
    @login_required
    def api_tasks():
        """Get list of tasks (filtered by user role)."""
        category = request.args.get('category')
        status = request.args.get('status')
        assigned_to = request.args.get('assigned_to')

        query = Task.query

        # Filter by role
        query = visible_task_query(query)

        # Apply filters
        if category:
            query = query.filter(Task.category == TaskCategory(category))
        if status:
            query = query.filter(Task.status == TaskStatus(status))
        if assigned_to:
            query = query.filter(Task.assigned_to == int(assigned_to))

        tasks = query.order_by(Task.created_at.desc()).all()

        return jsonify({
            'tasks': [t.to_dict(include_assignee=True, include_creator=True) for t in tasks],
            'user_role': current_user.role.value
        })

    @app.route('/api/tasks/<int:task_id>', methods=['GET'])
    @login_required
    def api_task_detail(task_id):
        """Get task details."""
        task = Task.query.get_or_404(task_id)

        # Check access
        if not current_user.is_editor() and (task.is_recurring or task.assigned_to not in (None, current_user.id)):
            return jsonify({'error': 'Access denied'}), 403

        return jsonify(task.to_dict(include_assignee=True, include_creator=True))

    @app.route('/api/tasks', methods=['POST'])
    @editor_required
    def api_create_task():
        """Create a new task (editor/admin only)."""
        data = request.get_json()

        try:
            category = TaskCategory(data.get('category', 'adhoc'))
            is_recurring = parse_recurring_flag(data, category)
            task = Task(
                title=data.get('title'),
                description=data.get('description'),
                category=category,
                priority=TaskPriority(data.get('priority', 'medium')),
                status=TaskStatus(data.get('status', 'pending')),
                assigned_to=data.get('assigned_to'),
                created_by=current_user.id,
                due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None,
                is_recurring=is_recurring,
                recurrence_rule=(data.get('recurrence_rule') or recurrence_rule_for_category(category)) if is_recurring else None
            )

            db.session.add(task)
            db.session.commit()

            # Log creation
            log = TaskLog(
                task_id=task.id,
                user_id=current_user.id,
                action='created',
                details=f"Task created by {current_user.username}"
            )
            db.session.add(log)
            db.session.commit()

            return jsonify({
                'success': True,
                'task': task.to_dict(include_assignee=True, include_creator=True)
            }), 201

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/api/tasks/<int:task_id>', methods=['PUT'])
    @login_required
    def api_update_task(task_id):
        """Update a task."""
        task = Task.query.get_or_404(task_id)

        # Check edit permission
        if not can_edit_task(current_user, task):
            return jsonify({'error': 'Permission denied'}), 403

        data = request.get_json()

        try:
            # Track changes for logging
            changes = []

            if 'title' in data and data['title'] != task.title:
                changes.append(f"title: '{task.title}' -> '{data['title']}'")
                task.title = data['title']

            if 'description' in data:
                changes.append("description updated")
                task.description = data['description']

            if 'status' in data:
                new_status = TaskStatus(data['status'])
                if new_status != task.status:
                    changes.append(f"status: {task.status.value} -> {new_status.value}")
                    old_status = task.status
                    task.status = new_status
                    if new_status == TaskStatus.COMPLETED:
                        task.completed_at = datetime.utcnow()
                    elif old_status == TaskStatus.COMPLETED and new_status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]:
                        task.completed_at = None

            if 'priority' in data:
                task.priority = TaskPriority(data['priority'])

            if 'category' in data:
                task.category = TaskCategory(data['category'])
                task.is_recurring = parse_recurring_flag(data, task.category) if 'is_recurring' in data else (task.is_recurring and task_scheduler.is_recurring_category(task.category))
                task.recurrence_rule = recurrence_rule_for_category(task.category) if task.is_recurring else None

            if 'is_recurring' in data and 'category' not in data:
                task.is_recurring = parse_recurring_flag(data, task.category)
                task.recurrence_rule = recurrence_rule_for_category(task.category) if task.is_recurring else None

            if 'due_date' in data:
                task.due_date = datetime.fromisoformat(data['due_date']) if data['due_date'] else None

            if 'assigned_to' in data and current_user.is_editor():
                task.assigned_to = data['assigned_to']

            task.updated_at = datetime.utcnow()
            db.session.commit()

            # Log update
            if changes:
                log = TaskLog(
                    task_id=task.id,
                    user_id=current_user.id,
                    action='updated',
                    details=', '.join(changes)
                )
                db.session.add(log)
                db.session.commit()

            return jsonify({
                'success': True,
                'task': task.to_dict(include_assignee=True, include_creator=True)
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
    @editor_required
    def api_delete_task(task_id):
        """Delete a task (editor/admin only)."""
        task = Task.query.get_or_404(task_id)

        try:
            # Log deletion
            log = TaskLog(
                task_id=task.id,
                user_id=current_user.id,
                action='deleted',
                details=f"Task '{task.title}' deleted by {current_user.username}"
            )
            db.session.add(log)

            db.session.delete(task)
            db.session.commit()

            return jsonify({'success': True, 'message': 'Task deleted'})

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
    @login_required
    def api_complete_task(task_id):
        """Mark task as complete."""
        task = Task.query.get_or_404(task_id)

        # Check permission
        if not can_edit_task(current_user, task):
            return jsonify({'error': 'Permission denied'}), 403

        try:
            task.mark_completed()

            log = TaskLog(
                task_id=task.id,
                user_id=current_user.id,
                action='completed',
                details=f"Task marked complete by {current_user.username}"
            )

            db.session.add(log)
            db.session.commit()

            return jsonify({
                'success': True,
                'task': task.to_dict(include_assignee=True, include_creator=True)
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400

    # ============ API: Dashboard ============

    @app.route('/api/dashboard/summary', methods=['GET'])
    @login_required
    def api_dashboard_summary():
        """Get dashboard summary statistics."""
        # Base query
        if current_user.is_editor():
            task_query = Task.query
        else:
            task_query = visible_task_query(Task.query)

        total = task_query.count()
        completed = task_query.filter_by(status=TaskStatus.COMPLETED).count()
        pending = task_query.filter(Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS])).count()
        overdue = task_query.filter_by(status=TaskStatus.OVERDUE).count()

        # Count by category
        category_counts = {}
        for cat in TaskCategory:
            count = task_query.filter_by(category=cat).count()
            category_counts[cat.value] = count

        # Count by priority
        priority_counts = {}
        for pri in TaskPriority:
            count = task_query.filter_by(priority=pri).count()
            priority_counts[pri.value] = count

        # Recent tasks
        recent_tasks = task_query.order_by(Task.updated_at.desc()).limit(5).all()

        return jsonify({
            'summary': {
                'total': total,
                'completed': completed,
                'pending': pending,
                'overdue': overdue,
                'completion_rate': round((completed / total * 100) if total > 0 else 0, 1)
            },
            'category_counts': category_counts,
            'priority_counts': priority_counts,
            'recent_tasks': [t.to_dict(include_assignee=True) for t in recent_tasks]
        })

    @app.route('/api/dashboard/overdue', methods=['GET'])
    @login_required
    def api_dashboard_overdue():
        """Get overdue tasks."""
        if current_user.is_editor():
            tasks = Task.query.filter_by(status=TaskStatus.OVERDUE).all()
        else:
            tasks = visible_task_query(Task.query).filter_by(status=TaskStatus.OVERDUE).all()

        return jsonify({'tasks': [t.to_dict(include_assignee=True) for t in tasks]})

    @app.route('/api/dashboard/my-tasks', methods=['GET'])
    @login_required
    def api_dashboard_my_tasks():
        """Get tasks assigned to current user."""
        tasks = Task.query.filter_by(assigned_to=current_user.id).order_by(Task.due_date.asc()).all()

        return jsonify({'tasks': [t.to_dict(include_assignee=True) for t in tasks]})

    # ============ API: Users (Admin Only) ============

    @app.route('/api/users', methods=['GET'])
    @admin_required
    def api_users():
        """Get list of all users (admin only)."""
        users = User.query.all()
        return jsonify({'users': [u.to_dict() for u in users]})

    @app.route('/api/users/assignable', methods=['GET'])
    @editor_required
    def api_assignable_users():
        """Get active users that tasks can be assigned to."""
        users = User.query.filter_by(is_active=True).order_by(User.username.asc()).all()
        return jsonify({
            'users': [
                {
                    'id': user.id,
                    'username': user.username
                }
                for user in users
            ]
        })

    @app.route('/api/users', methods=['POST'])
    @admin_required
    def api_create_user():
        """Create a new user (admin only)."""
        data = request.get_json()

        try:
            # Check if username exists
            if User.query.filter_by(username=data['username']).first():
                return jsonify({'success': False, 'error': 'Username already exists'}), 400

            user = User(
                username=data['username'],
                email=data['email'],
                role=UserRole(data.get('role', 'user')),
                line_id=data.get('line_id')
            )
            user.set_password(data['password'])

            db.session.add(user)
            db.session.commit()

            return jsonify({
                'success': True,
                'user': user.to_dict()
            }), 201

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/api/users/<int:user_id>', methods=['PUT'])
    @admin_required
    def api_update_user(user_id):
        """Update a user (admin only)."""
        user = User.query.get_or_404(user_id)
        data = request.get_json()

        try:
            if 'email' in data:
                user.email = data['email']
            if 'role' in data:
                user.role = UserRole(data['role'])
            if 'line_id' in data:
                user.line_id = data['line_id']
            if 'is_active' in data:
                user.is_active = data['is_active']
            if 'password' in data:
                user.set_password(data['password'])

            db.session.commit()
            return jsonify({'success': True, 'user': user.to_dict()})

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/api/users/<int:user_id>', methods=['DELETE'])
    @admin_required
    def api_delete_user(user_id):
        """Delete a user (admin only)."""
        if user_id == current_user.id:
            return jsonify({'success': False, 'error': 'Cannot delete yourself'}), 400

        user = User.query.get_or_404(user_id)

        try:
            # Unassign tasks
            Task.query.filter_by(assigned_to=user_id).update({'assigned_to': None})
            db.session.delete(user)
            db.session.commit()

            return jsonify({'success': True, 'message': 'User deleted'})

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400

    # ============ API: Utility ============

    @app.route('/api/time')
    def api_time():
        """Get current server time."""
        timezone = ZoneInfo(app.config.get('TIMEZONE', 'Asia/Bangkok'))
        return jsonify({'time': datetime.now(timezone).isoformat()})

    # ============ Error Handlers ============

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

    return app


def create_default_data():
    """Create default admin user and sample data if database is empty."""
    # Check if users exist
    if User.query.count() == 0:
        print("Creating default admin user...")

        # Create default admin
        admin = User(
            username='admin',
            email='admin@tasktracker.local',
            role=UserRole.ADMIN
        )
        admin.set_password('admin123')
        db.session.add(admin)

        # Create sample users
        editor = User(
            username='editor',
            email='editor@tasktracker.local',
            role=UserRole.EDITOR
        )
        editor.set_password('editor123')
        db.session.add(editor)

        user = User(
            username='user',
            email='user@tasktracker.local',
            role=UserRole.USER
        )
        user.set_password('user123')
        db.session.add(user)

        db.session.commit()
        print("Default users created: admin/admin123, editor/editor123, user/user123")

    # Check if tasks exist
    if Task.query.count() == 0:
        print("Creating sample tasks...")

        users = User.query.all()

        sample_tasks = [
            {
                'title': 'Daily server backup check',
                'description': 'Verify that daily backups completed successfully',
                'category': TaskCategory.DAILY,
                'priority': TaskPriority.HIGH,
                'assigned_to': 2
            },
            {
                'title': 'Weekly security scan',
                'description': 'Run vulnerability scanner on all servers',
                'category': TaskCategory.WEEKLY,
                'priority': TaskPriority.MEDIUM,
                'assigned_to': 2
            },
            {
                'title': 'Monthly performance review',
                'description': 'Review system performance metrics for the month',
                'category': TaskCategory.MONTHLY,
                'priority': TaskPriority.LOW,
                'assigned_to': 1
            },
            {
                'title': 'Quarterly audit preparation',
                'description': 'Prepare documents for quarterly security audit',
                'category': TaskCategory.QUARTERLY,
                'priority': TaskPriority.HIGH,
                'assigned_to': 1
            },
            {
                'title': 'Yearly license renewal',
                'description': 'Review and renew software licenses',
                'category': TaskCategory.YEARLY,
                'priority': TaskPriority.CRITICAL,
                'assigned_to': 1
            },
            {
                'title': 'Fix database connection issue',
                'description': 'Investigate intermittent connection failures',
                'category': TaskCategory.ADHOC,
                'priority': TaskPriority.CRITICAL,
                'assigned_to': 3
            }
        ]

        for task_data in sample_tasks:
            is_recurring = task_data['category'] in [TaskCategory.DAILY, TaskCategory.WEEKLY, TaskCategory.MONTHLY]
            task = Task(
                title=task_data['title'],
                description=task_data['description'],
                category=task_data['category'],
                priority=task_data['priority'],
                assigned_to=task_data['assigned_to'],
                created_by=1,
                due_date=datetime.utcnow() + timedelta(days=7),
                is_recurring=is_recurring,
                recurrence_rule=f"FREQ={task_data['category'].value.upper()}" if is_recurring else None
            )
            db.session.add(task)

        db.session.commit()
        print("Sample tasks created")


def ensure_schema_updates():
    """Add columns required by newer app versions for SQLite deployments."""
    inspector = inspect(db.engine)
    columns = {column['name'] for column in inspector.get_columns('tasks')}
    alter_statements = []

    if 'is_recurring' not in columns:
        alter_statements.append("ALTER TABLE tasks ADD COLUMN is_recurring BOOLEAN NOT NULL DEFAULT 0")
    if 'recurrence_source_id' not in columns:
        alter_statements.append("ALTER TABLE tasks ADD COLUMN recurrence_source_id INTEGER")
    if 'last_generated_at' not in columns:
        alter_statements.append("ALTER TABLE tasks ADD COLUMN last_generated_at DATETIME")

    for statement in alter_statements:
        db.session.execute(text(statement))

    if alter_statements:
        db.session.commit()


if __name__ == '__main__':
    app = create_app(os.environ.get('FLASK_ENV', 'default'))

    # Start scheduler
    task_scheduler.start()

    # Run application
    app.run(
        host=app.config['APP_HOST'],
        port=app.config['APP_PORT'],
        debug=app.config['DEBUG']
    )
