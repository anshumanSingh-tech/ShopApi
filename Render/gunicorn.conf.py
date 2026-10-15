import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = 60
accesslog = "-"

if os.path.isdir("/dev/shm"):
    worker_tmp_dir = "/dev/shm"
