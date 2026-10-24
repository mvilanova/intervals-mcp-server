FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install build dependencies and Python build backend
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python build tool
RUN pip install --no-cache-dir hatchling

# Copy project files
COPY pyproject.toml pyproject.toml
COPY src src
COPY README.md README.md
COPY .env.example .env.example

# Install the package and runtime dependencies
RUN pip install --no-cache-dir .

# Runs the server module so MCP_TRANSPORT applies (stdio by default); `mcp run` always uses stdio
CMD ["python", "-m", "intervals_mcp_server.server"]
