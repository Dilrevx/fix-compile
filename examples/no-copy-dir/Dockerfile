# Dockerfile with path error example
FROM python:3.11-slim

WORKDIR /app

# This will fail because requirements.txt doesn't exist
COPY requirements.txt .
RUN pip install -r requirements.txt

# This will fail because src/ may not exist at build time
COPY src/ ./src/

EXPOSE 8000

CMD ["python", "main.py"]
