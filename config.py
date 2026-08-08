"""
Configuration for Task Tracker application.
"""

import os
from pathlib import Path


def env_flag(name, default='false'):
    """Read a boolean flag from the environment."""
    return os.environ.get(name, default).lower() == 'true'


class Config:
    """Base configuration class."""

    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database
    BASE_DIR = Path(__file__).resolve().parent
    DATABASE_PATH = os.environ.get('DATABASE_PATH') or 'instance/tasktracker.db'
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{BASE_DIR / DATABASE_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Email settings (SMTP)
    SMTP_SERVER = os.environ.get('SMTP_SERVER') or 'localhost'
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true'
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME') or ''
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD') or ''
    EMAIL_FROM = os.environ.get('EMAIL_FROM') or 'noreply@tasktracker.local'

    # LINE Messaging API settings
    LINE_WEBHOOK_URL = os.environ.get('LINE_WEBHOOK_URL') or ''
    LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET') or ''
    LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN') or ''

    # Notification settings
    NOTIFICATION_CHECK_INTERVAL = 300  # Check every 5 minutes
    UPCOMING_TASK_HOURS = 24  # Notify for tasks due within 24 hours
    DAILY_SUMMARY_TIME = '08:00'  # Daily summary at 8 AM
    TIMEZONE = os.environ.get('TIMEZONE') or 'Asia/Bangkok'

    # Application settings
    APP_HOST = os.environ.get('APP_HOST') or '0.0.0.0'
    APP_PORT = int(os.environ.get('APP_PORT', 1235))
    DEBUG = env_flag('DEBUG')
    BOOTSTRAP_DEFAULT_DATA = env_flag('BOOTSTRAP_DEFAULT_DATA')

    # Pagination
    TASKS_PER_PAGE = 50
    USERS_PER_PAGE = 20

    # Session
    PERMANENT_SESSION_LIFETIME = 3600 * 24  # 24 hours


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    BOOTSTRAP_DEFAULT_DATA = env_flag('BOOTSTRAP_DEFAULT_DATA', 'true')


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    BOOTSTRAP_DEFAULT_DATA = env_flag('BOOTSTRAP_DEFAULT_DATA')


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
