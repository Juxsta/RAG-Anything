# Multi-stage build for RAG-Anything API Server

# Stage 1: Build stage for Node.js
FROM node:20-alpine AS node-builder

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./

# Install dependencies
RUN npm ci --only=production && \
    npm cache clean --force

# Copy source code
COPY src/ ./src/

# Build the application
RUN npm run build

# Stage 2: Python dependencies stage
FROM python:3.11-slim AS python-deps

# Install system dependencies for Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY ../requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install RAG-Anything package
COPY ../ /tmp/rag-anything/
RUN cd /tmp/rag-anything && pip install -e .

# Stage 3: Final production image
FROM node:20-alpine AS production

# Install Python and system dependencies
RUN apk add --no-cache \
    python3 \
    python3-dev \
    py3-pip \
    gcc \
    musl-dev \
    postgresql-dev \
    libffi-dev \
    openssl-dev \
    && ln -sf python3 /usr/bin/python

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S ragapi -u 1001 -G nodejs

WORKDIR /app

# Copy Python virtual environment
COPY --from=python-deps /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy built Node.js application
COPY --from=node-builder --chown=ragapi:nodejs /app/dist ./dist
COPY --from=node-builder --chown=ragapi:nodejs /app/node_modules ./node_modules
COPY --from=node-builder --chown=ragapi:nodejs /app/package.json ./

# Copy Python worker script
COPY --chown=ragapi:nodejs scripts/ ./scripts/

# Copy RAG-Anything source code
COPY --from=python-deps --chown=ragapi:nodejs /tmp/rag-anything /app/rag-anything

# Create necessary directories
RUN mkdir -p logs temp uploads rag_storage output && \
    chown -R ragapi:nodejs logs temp uploads rag_storage output

# Set Python path to include RAG-Anything
ENV PYTHONPATH="/app/rag-anything:$PYTHONPATH"
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3000}/health || exit 1

# Switch to non-root user
USER ragapi

# Expose port
EXPOSE 3000

# Start the application
CMD ["node", "dist/server.js"]