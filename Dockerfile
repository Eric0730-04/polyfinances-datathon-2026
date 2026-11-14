FROM python:3.11-slim
# AWS Lambda Web Adapter: runs this ordinary web server inside Lambda, with response streaming for live agent progress
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AWS_DEFAULT_REGION=us-east-1 RATE_LIMIT=1 \
    PORT=8080 AWS_LWA_INVOKE_MODE=response_stream AWS_LWA_READINESS_CHECK_PATH=/healthz
WORKDIR /app
COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt
COPY server.py aws_resources.json ./
COPY src ./src
COPY web ./web
COPY personas ./personas
COPY data ./data
EXPOSE 8080
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--timeout-keep-alive", "75"]
