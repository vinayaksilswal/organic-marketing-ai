FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for Prisma and async DB drivers
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .



# Create a non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Create necessary directories and set ownership
RUN mkdir -p /app/uploads /app/uploads/cache && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8000

# Set production environment
ENV ENVIRONMENT=production

# Health check — Render/Docker use this to verify the service is healthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Run with Gunicorn + Uvicorn workers
# IMPORTANT: -w 1 (single worker) is REQUIRED because APScheduler runs
# the marketing loop. Multiple workers would cause duplicate posts.
CMD ["sh", "-c", "gunicorn main:app -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} --timeout 120 --graceful-timeout 30"]
