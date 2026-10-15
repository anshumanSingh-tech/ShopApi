FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first: this layer is rebuilt only when requirements.txt changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# collectstatic imports the settings, which insist on a SECRET_KEY. This key exists only
# for this build step and is not stored in the image.
RUN SECRET_KEY=build-only-key DEBUG=False python manage.py collectstatic --no-input

# Do not run the app as root.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER 10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request as u; u.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/health/', timeout=3)"]

CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]