# Use official Playwright Python image
FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure Chromium browser is installed
RUN playwright install chromium

# Copy application source
COPY . .

# Ensure data directories exist
RUN mkdir -p data/browser_profile data/artifacts data/uploads configs

# Expose Web UI & API port
EXPOSE 8000

# Set environment defaults
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000
ENV HEADLESS=true
ENV PYTHONUNBUFFERED=1

CMD ["python", "run.py"]
