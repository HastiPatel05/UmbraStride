FROM python:3.12-slim

# Install system dependencies needed for geos/gdal
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy the entire workspace configuration and source files
COPY pyproject.toml /app/
COPY packages /app/packages
COPY services/api /app/services/api

# Sync Python packages
RUN uv sync --frozen --no-dev --package umbrastride-api

# Expose port
EXPOSE 8000

# Run FastAPI app
CMD ["/app/.venv/bin/uvicorn", "umbrastride_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
