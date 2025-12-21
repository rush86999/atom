import multiprocessing
import os

# Binding
bind = "0.0.0.0:8000"

# Workers
workers_per_core = 1
cores = multiprocessing.cpu_count()
default_web_concurrency = workers_per_core * cores + 1
web_concurrency = int(os.getenv("WEB_CONCURRENCY", default_web_concurrency))
workers = web_concurrency

# Worker Class
worker_class = "uvicorn.workers.UvicornWorker"

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"

# Timeouts
keepalive = 120
timeout = 120
