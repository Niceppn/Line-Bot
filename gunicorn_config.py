import multiprocessing

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = '/var/www/linebot/logs/access.log'
errorlog = '/var/www/linebot/logs/error.log'
loglevel = 'info'

# Process naming
proc_name = 'linebot'

# Server mechanics
daemon = False
pidfile = '/var/www/linebot/gunicorn.pid'
user = None
group = None
tmp_upload_dir = None

# SSL
keyfile = None
certfile = None
