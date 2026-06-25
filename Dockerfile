FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin ccld

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY schemas ./schemas
COPY src ./src
COPY tests/fixtures/hosted_seeded_corpus ./tests/fixtures/hosted_seeded_corpus
COPY tests/fixtures/public_source_facilities ./tests/fixtures/public_source_facilities

RUN mkdir -p /app/data/raw /app/data/processed /app/data/logs \
    && chown -R ccld:ccld /app

USER ccld

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read()"

CMD ["python", "-m", "ccld_complaints.hosted_app", "--host", "0.0.0.0", "--port", "8000"]
