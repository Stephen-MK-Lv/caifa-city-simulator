FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CAIFA_HOST=0.0.0.0 \
    CAIFA_AUTH_REQUIRED=1 \
    CAIFA_DISABLE_BOOTSTRAP=1 \
    CAIFA_DB=/data/caifa.sqlite3

WORKDIR /app

COPY requirements-railway.txt ./requirements-railway.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-railway.txt

COPY app ./app
COPY run.py ./run.py
RUN mkdir -p /data

EXPOSE 8080
CMD ["python", "run.py", "--no-browser"]
