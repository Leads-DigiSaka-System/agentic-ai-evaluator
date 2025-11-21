"""
Gunicorn configuration for production deployment
"""
import multiprocessing
import os

# Server socket
# Railway and other platforms provide PORT env var
# Priority: PORT > GUNICORN_BIND > default 8000
port = os.getenv("PORT") or (os.getenv("GUNICORN_BIND", "0.0.0.0:8000").split(":")[-1])
bind = f"0.0.0.0:{port}"
backlog = int(os.getenv("GUNICORN_BACKLOG", "2048"))

# Worker processes
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", "1000"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "300"))  # 5 minutes for long-running jobs
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Logging
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")  # "-" means stdout
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")  # "-" means stderr
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info").lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "agentic-ai-evaluator"

# Server mechanics
daemon = False
pidfile = os.getenv("GUNICORN_PIDFILE", None)  # Set if you want a PID file
umask = 0o007
tmp_upload_dir = None

# SSL (if needed)
# keyfile = None
# certfile = None

# Preload app for better performance
preload_app = True

# Graceful timeout for worker shutdown
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))

# Max requests per worker (helps prevent memory leaks)
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "50"))

# Worker restart after this many requests (helps with memory management)
# Use /dev/shm on Linux, fallback to None on other systems
worker_tmp_dir = os.getenv("GUNICORN_WORKER_TMP_DIR", "/dev/shm" if os.path.exists("/dev/shm") else None)

def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting Gunicorn server...")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading Gunicorn server...")

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Gunicorn server is ready. Spawning workers...")

def worker_int(worker):
    """Called when a worker receives the INT or QUIT signal."""
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    worker.log.info(f"Worker {worker.pid} initialized")

def worker_abort(worker):
    """Called when a worker times out."""
    worker.log.warning(f"Worker {worker.pid} timed out")

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forking new master process...")

def on_exit(server):
    """Called just before exiting Gunicorn."""
    server.log.info("Shutting down Gunicorn server...")

