# Makefile for RAG-Anything development and testing

.PHONY: help install test test-security test-backends test-integration test-performance test-all coverage lint format clean docs docker

# Default target
help:
	@echo "RAG-Anything Development Commands"
	@echo "=================================="
	@echo ""
	@echo "Installation:"
	@echo "  install          Install development dependencies"
	@echo "  install-prod     Install production dependencies only"
	@echo "  install-graphiti Install with Graphiti integration"
	@echo "  build-graphiti   Build graphiti-core from source"
	@echo ""
	@echo "Testing:"
	@echo "  test             Run all tests with coverage"
	@echo "  test-security    Run security tests only"
	@echo "  test-backends    Run backend tests only"
	@echo "  test-graphiti    Run Graphiti integration tests"
	@echo "  test-integration Run integration tests only"
	@echo "  test-performance Run performance tests only"
	@echo "  test-all         Run comprehensive test suite"
	@echo "  coverage         Generate coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint             Run linting checks"
	@echo "  format           Format code with black and isort"
	@echo "  type-check       Run type checking with mypy"
	@echo "  security-scan    Run security scanning"
	@echo ""
	@echo "Documentation:"
	@echo "  docs             Build documentation"
	@echo "  docs-serve       Serve documentation locally"
	@echo ""
	@echo "Services:"
	@echo "  serve            Start FastAPI development server"
	@echo "  serve-graphiti   Start FastAPI server with Graphiti backend"
	@echo "  start-db         Start required database services"
	@echo "  stop-db          Stop database services"
	@echo ""
	@echo "Deployment:"
	@echo "  docker           Build Docker image"
	@echo "  docker-run       Run Docker container"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean            Clean up build artifacts"
	@echo "  clean-all        Clean everything including venv"

# Python interpreter and virtual environment
PYTHON := python3
VENV_DIR := venv
PIP := $(VENV_DIR)/bin/pip
PYTHON_VENV := $(VENV_DIR)/bin/python

# Project directories
SRC_DIR := raganything
TEST_DIR := tests
DOCS_DIR := docs
BUILD_DIR := build
DIST_DIR := dist

# Dependencies
DEV_REQUIREMENTS := requirements-dev.txt
REQUIREMENTS := requirements.txt

# Installation targets
install: $(VENV_DIR)
	$(PIP) install -r $(REQUIREMENTS)
	$(PIP) install -r $(DEV_REQUIREMENTS)
	$(PIP) install -e .
	@echo "Development environment ready!"

install-prod: $(VENV_DIR)
	$(PIP) install -r $(REQUIREMENTS)
	$(PIP) install -e .
	@echo "Production environment ready!"

install-graphiti: $(VENV_DIR) build-graphiti
	$(PIP) install -e .[graphiti,api]
	@echo "RAG-Anything with Graphiti integration ready!"

build-graphiti:
	@echo "Building graphiti-core from source..."
	@if [ -d "../graphiti" ]; then \
		cd ../graphiti && pip install -e . --user --verbose; \
		echo "✅ graphiti-core built and installed from source"; \
	else \
		echo "❌ Graphiti source directory not found at ../graphiti"; \
		echo "Please clone graphiti repository to ../graphiti or install from PyPI:"; \
		echo "pip install graphiti-core[falkordb]"; \
		exit 1; \
	fi

$(VENV_DIR):
	$(PYTHON) -m venv $(VENV_DIR)
	$(PIP) install --upgrade pip setuptools wheel

# Testing targets
test: $(VENV_DIR)
	$(PYTHON_VENV) -m pytest $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=term-missing

test-security: $(VENV_DIR)
	$(PYTHON_VENV) -m pytest $(TEST_DIR)/security -v --cov=$(SRC_DIR)/security

test-backends: $(VENV_DIR)
	$(PYTHON_VENV) -m pytest $(TEST_DIR)/backends -v --cov=$(SRC_DIR)/backends

test-graphiti: $(VENV_DIR)
	@echo "Testing Graphiti integration..."
	$(PYTHON_VENV) -c "from raganything.backends.graphiti_direct import GraphitiDirectBackend; print('✅ Graphiti direct backend imports successfully')"
	$(PYTHON_VENV) -c "from graphiti_core import Graphiti; print('✅ graphiti-core available')"
	@if [ -f "test_comprehensive_integration.py" ]; then \
		echo "🧪 Running comprehensive integration tests..."; \
		PYTHONPATH=. $(PYTHON_VENV) test_comprehensive_integration.py; \
	elif [ -f "test_graphiti_integration.py" ]; then \
		echo "🧪 Running basic integration tests..."; \
		$(PYTHON_VENV) test_graphiti_integration.py; \
	else \
		echo "⚠️  No Graphiti tests found"; \
	fi

test-integration: $(VENV_DIR)
	$(PYTHON_VENV) -m pytest $(TEST_DIR)/integration -v

test-performance: $(VENV_DIR)
	$(PYTHON_VENV) -m pytest $(TEST_DIR)/performance -v -m "not slow"

test-all: $(VENV_DIR)
	$(PYTHON_VENV) $(TEST_DIR)/test_runner.py --suite=all --coverage-threshold=90
	@echo "Comprehensive test suite completed!"

coverage: $(VENV_DIR)
	$(PYTHON_VENV) -m coverage run -m pytest $(TEST_DIR)
	$(PYTHON_VENV) -m coverage report
	$(PYTHON_VENV) -m coverage html
	@echo "Coverage report generated in test_reports/coverage_html/"

# Code quality targets
lint: $(VENV_DIR)
	$(PYTHON_VENV) -m flake8 $(SRC_DIR) $(TEST_DIR)
	$(PYTHON_VENV) -m pylint $(SRC_DIR)
	@echo "Linting completed!"

format: $(VENV_DIR)
	$(PYTHON_VENV) -m black $(SRC_DIR) $(TEST_DIR)
	$(PYTHON_VENV) -m isort $(SRC_DIR) $(TEST_DIR)
	@echo "Code formatting completed!"

type-check: $(VENV_DIR)
	$(PYTHON_VENV) -m mypy $(SRC_DIR)
	@echo "Type checking completed!"

security-scan: $(VENV_DIR)
	$(PYTHON_VENV) -m bandit -r $(SRC_DIR)
	$(PYTHON_VENV) -m safety check
	@echo "Security scanning completed!"

# Documentation targets
docs: $(VENV_DIR)
	@if [ -d "$(DOCS_DIR)" ]; then \
		cd $(DOCS_DIR) && make html; \
	else \
		echo "Documentation directory not found"; \
	fi

docs-serve: docs
	@if [ -d "$(DOCS_DIR)/_build/html" ]; then \
		cd $(DOCS_DIR)/_build/html && $(PYTHON) -m http.server 8000; \
	else \
		echo "Documentation not built. Run 'make docs' first"; \
	fi

# Docker targets
docker:
	docker build -t raganything:latest .
	@echo "Docker image built successfully!"

docker-run:
	docker run -p 8000:8000 -v $(PWD):/app raganything:latest
	@echo "Docker container running on http://localhost:8000"

# Development servers
serve: $(VENV_DIR)
	@echo "Starting FastAPI development server..."
	PYTHONPATH=. $(PYTHON_VENV) -m uvicorn raganything.api.main:GraphitiRAGApp --reload --host 0.0.0.0 --port 8000

serve-graphiti: $(VENV_DIR)
	@echo "Starting FastAPI server with Graphiti backend..."
	RAG_BACKEND_TYPE=graphiti PYTHONPATH=. $(PYTHON_VENV) -m uvicorn raganything.api.main:GraphitiRAGApp --reload --host 0.0.0.0 --port 8000

start-db:
	@echo "Starting database services..."
	@echo "Starting FalkorDB (Redis-based)..."
	@if command -v redis-server > /dev/null; then \
		redis-server --daemonize yes --port 6379; \
		echo "✅ FalkorDB/Redis started on port 6379"; \
	else \
		echo "❌ Redis not found. Install with: sudo apt-get install redis-server"; \
	fi
	@echo "For Neo4j, please start it manually or use Docker:"
	@echo "  docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest"

stop-db:
	@echo "Stopping database services..."
	@if pgrep redis-server > /dev/null; then \
		pkill redis-server; \
		echo "✅ Redis/FalkorDB stopped"; \
	else \
		echo "Redis/FalkorDB was not running"; \
	fi
	@echo "To stop Neo4j Docker container: docker stop neo4j && docker rm neo4j"

# Cleanup targets
clean:
	rm -rf $(BUILD_DIR)
	rm -rf $(DIST_DIR)
	rm -rf test_reports
	rm -rf .coverage
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	@echo "Clean up completed!"

clean-all: clean
	rm -rf $(VENV_DIR)
	@echo "Complete cleanup finished!"

# Quality assurance target
qa: format lint type-check security-scan test-all
	@echo "Quality assurance checks completed!"

# CI/CD simulation
ci: install qa
	@echo "CI pipeline simulation completed successfully!"

# Development workflow
dev-setup: install
	pre-commit install
	@echo "Development setup completed!"

# Performance benchmarks
benchmark: $(VENV_DIR)
	$(PYTHON_VENV) -m pytest $(TEST_DIR)/performance -v --benchmark-only
	@echo "Performance benchmarks completed!"

# Generate requirements files
freeze: $(VENV_DIR)
	$(PIP) freeze > requirements-frozen.txt
	@echo "Requirements frozen to requirements-frozen.txt"

# Database/Redis management (if needed)
start-redis:
	@if command -v redis-server > /dev/null; then \
		redis-server --daemonize yes; \
		echo "Redis started"; \
	else \
		echo "Redis not installed. Install with: sudo apt-get install redis-server"; \
	fi

stop-redis:
	@if pgrep redis-server > /dev/null; then \
		pkill redis-server; \
		echo "Redis stopped"; \
	else \
		echo "Redis is not running"; \
	fi

# Monitoring and logging
logs:
	@if [ -d "logs" ]; then \
		tail -f logs/*.log; \
	else \
		echo "No log directory found"; \
	fi

# Environment validation
validate-env: $(VENV_DIR)
	$(PYTHON_VENV) -c "import raganything; print('✅ RAG-Anything imports successfully')"
	$(PYTHON_VENV) -c "import redis; print('✅ Redis client available')"
	$(PYTHON_VENV) -c "import pytest; print('✅ Pytest available')"
	@echo "Environment validation completed!"

# Release preparation
prepare-release: clean qa
	$(PYTHON_VENV) setup.py sdist bdist_wheel
	@echo "Release artifacts prepared in $(DIST_DIR)/"

# Database migrations (if using databases)
migrate:
	@echo "No database migrations configured yet"

# API documentation generation
api-docs: $(VENV_DIR)
	$(PYTHON_VENV) -c "from python-api.app.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > api-schema.json
	@echo "API documentation generated!"

# Backup important files
backup:
	@mkdir -p backups/$(shell date +%Y%m%d_%H%M%S)
	@tar -czf backups/$(shell date +%Y%m%d_%H%M%S)/backup.tar.gz \
		--exclude=venv \
		--exclude=__pycache__ \
		--exclude=.git \
		--exclude=test_reports \
		--exclude=*.pyc \
		.
	@echo "Backup created in backups/"