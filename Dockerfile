# Multi-stage Dockerfile for manga video pipeline

# Build stage for dependencies
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Install Playwright dependencies
RUN playwright install chromium --with-deps


# Production stage
FROM python:3.13-slim

# Install system dependencies needed for the application
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /root/.local

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
WORKDIR /app

# Copy application source code
COPY . .

# Set PATH to include user-installed packages
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Create necessary directories
RUN mkdir -p /app/data /app/logs && chown -R appuser:appuser /app
RUN chmod -R 755 /app/data /app/logs

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Switch to non-root user
USER appuser

EXPOSE 8000

# Command to run the application (will be overridden by docker-compose for specific services)
CMD ["uvicorn", "src.dashboard.main:app", "--host", "0.0.0.0", "--port", "8000"]