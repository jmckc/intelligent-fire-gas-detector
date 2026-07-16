FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Persistent data directory for SQLite
RUN mkdir -p /app/data

EXPOSE 5000

CMD ["python", "app.py"]
