FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AWS_DEFAULT_REGION=us-east-1 RATE_LIMIT=1
WORKDIR /app
COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt
COPY server.py aws_resources.json ./
COPY src ./src
COPY web ./web
COPY personas ./personas
COPY data ./data
RUN useradd -m app && mkdir -p /app/runs && chown -R app /app
USER app
EXPOSE 8080
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--timeout-keep-alive", "75"]
