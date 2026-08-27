FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects $PORT — default 8080 matches .env.example for local parity.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn warden.gateway:app --host 0.0.0.0 --port ${PORT}"]
