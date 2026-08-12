"""
Notification system for email and webhook.
"""

import smtplib
import requests
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def _get_setting(key, default=''):
    """Read a setting from the database, falling back to env vars."""
    try:
        from models import AppSetting
        row = AppSetting.query.filter_by(key=key).first()
        if row and row.value:
            return row.value
    except Exception:
        pass
    return os.environ.get(key.upper(), default)


def _get_smtp_config():
    """Build SMTP config dict from DB/env."""
    return {
        'server': _get_setting('smtp_server', 'localhost'),
        'port': int(_get_setting('smtp_port', '587')),
        'use_tls': _get_setting('smtp_use_tls', 'true').lower() == 'true',
        'username': _get_setting('smtp_username', ''),
        'password': _get_setting('smtp_password', ''),
        'from': _get_setting('email_from', 'noreply@tasktracker.local'),
    }


def send_email_notification(to_email: str, subject: str, task_data: Dict[str, Any]) -> bool:
    """
    Send email notification for a task.
    """
    cfg = _get_smtp_config()

    if not cfg['username'] or not cfg['password']:
        logger.warning("SMTP not configured, skipping email notification")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = cfg['from']
        msg['To'] = to_email

        html_body = f"""
        <html>
        <head></head>
        <body>
            <h2>Task Notification</h2>
            <table style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Title</th>
                    <td style="padding: 8px; border: 1px solid #ddd;">{task_data.get('title', 'N/A')}</td>
                </tr>
                <tr>
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Category</th>
                    <td style="padding: 8px; border: 1px solid #ddd;">{task_data.get('category', 'N/A')}</td>
                </tr>
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Priority</th>
                    <td style="padding: 8px; border: 1px solid #ddd;">{task_data.get('priority', 'N/A')}</td>
                </tr>
                <tr>
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Status</th>
                    <td style="padding: 8px; border: 1px solid #ddd;">{task_data.get('status', 'N/A')}</td>
                </tr>
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Due Date</th>
                    <td style="padding: 8px; border: 1px solid #ddd;">{task_data.get('due_date', 'N/A')}</td>
                </tr>
            </table>
            {f'<p><strong>Description:</strong> {task_data.get("description", "")}</p>' if task_data.get('description') else ''}
            <p style="color: #666; font-size: 12px;">This is an automated notification from Operation Task Monitoring.</p>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(cfg['server'], cfg['port']) as server:
            if cfg['use_tls']:
                server.starttls()
            server.login(cfg['username'], cfg['password'])
            server.send_message(msg)

        logger.info(f"Email sent to {to_email} for task {task_data.get('id')}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_line_notification(line_id: str, task_data: Dict[str, Any], message_type: str = 'overdue') -> bool:
    """
    Send notification via webhook (LINE Messaging API or generic webhook).
    """
    webhook_url = _get_setting('webhook_url') or _get_setting('LINE_WEBHOOK_URL')
    token = _get_setting('webhook_token') or _get_setting('LINE_CHANNEL_ACCESS_TOKEN')

    if not webhook_url:
        logger.warning("Webhook not configured, skipping notification")
        return False

    if not line_id:
        logger.warning("No recipient ID provided")
        return False

    try:
        # Format message based on type
        if message_type == 'overdue':
            emoji = '⚠️'
            status_text = 'OVERDUE'
        elif message_type == 'upcoming':
            emoji = '🔔'
            status_text = 'Due Soon'
        else:
            emoji = '📋'
            status_text = task_data.get('status', 'pending').upper()

        # Create flex message for rich display
        message = {
            "to": line_id,
            "messages": [
                {
                    "type": "flex",
                    "altText": f"{emoji} Task Notification: {task_data.get('title', 'N/A')}",
                    "contents": {
                        "type": "bubble",
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": f"{emoji} Task {status_text}",
                                    "weight": "bold",
                                    "size": "lg",
                                    "color": "#FF0000" if message_type == 'overdue' else "#1E90FF"
                                },
                                {
                                    "type": "separator",
                                    "margin": "md"
                                },
                                {
                                    "type": "text",
                                    "text": task_data.get('title', 'N/A'),
                                    "weight": "bold",
                                    "margin": "md"
                                },
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "margin": "md",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "Category",
                                            "size": "xs",
                                            "color": "#888888",
                                            "flex": 1
                                        },
                                        {
                                            "type": "text",
                                            "text": task_data.get('category', 'N/A'),
                                            "size": "xs",
                                            "align": "end"
                                        }
                                    ]
                                },
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "Priority",
                                            "size": "xs",
                                            "color": "#888888",
                                            "flex": 1
                                        },
                                        {
                                            "type": "text",
                                            "text": task_data.get('priority', 'N/A'),
                                            "size": "xs",
                                            "align": "end"
                                        }
                                    ]
                                },
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "Due Date",
                                            "size": "xs",
                                            "color": "#888888",
                                            "flex": 1
                                        },
                                        {
                                            "type": "text",
                                            "text": task_data.get('due_date', 'N/A') or 'No due date',
                                            "size": "xs",
                                            "align": "end"
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            ]
        }

        headers = {
            'Content-Type': 'application/json',
        }
        if token:
            headers['Authorization'] = f'Bearer {token}'

        response = requests.post(webhook_url, json=message, headers=headers, timeout=10)
        response.raise_for_status()

        logger.info(f"LINE notification sent to {line_id} for task {task_data.get('id')}")
        return True

    except Exception as e:
        logger.error(f"Failed to send LINE notification: {e}")
        return False


def send_daily_summary(user_email: str, line_id: Optional[str], summary: Dict[str, Any]) -> bool:
    """
    Send daily task summary via email and optionally LINE.

    Args:
        user_email: User's email address
        line_id: User's LINE ID (optional)
        summary: Dictionary with summary statistics

    Returns:
        True if at least one notification succeeded
    """
    email_sent = send_email_notification(
        user_email,
        f"Daily Task Summary - {datetime.now().strftime('%Y-%m-%d')}",
        summary
    )

    line_sent = False
    if line_id:
        line_sent = send_line_notification(line_id, summary, 'daily_summary')

    return email_sent or line_sent
