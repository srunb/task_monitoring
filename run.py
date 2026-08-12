import os
os.environ.setdefault('APP_PORT', '1239')
os.environ.setdefault('APP_HOST', '0.0.0.0')
os.environ.setdefault('BOOTSTRAP_DEFAULT_DATA', 'true')
os.environ.setdefault('FLASK_ENV', 'production')

from app import create_app, task_scheduler

app = create_app(os.environ.get('FLASK_ENV', 'production'))
task_scheduler.start()

if __name__ == '__main__':
    app.run(
        host=app.config['APP_HOST'],
        port=app.config['APP_PORT'],
        debug=False,
        use_reloader=False
    )
