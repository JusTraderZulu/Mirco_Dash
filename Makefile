# TEPM System Makefile

.PHONY: help install test run clean lint format

# Default target
help:
	@echo "TEPM System - Available commands:"
	@echo "  install    Install dependencies"
	@echo "  test       Run tests"
	@echo "  run        Run the application"
	@echo "  clean      Clean build artifacts"
	@echo "  lint       Run linters"
	@echo "  format     Format code"

# Install dependencies
install:
	pip install -r requirements.txt

# Run tests
test:
	pytest -v tests/

# Run tests with coverage
test-coverage:
	pytest --cov=src tests/

# Run the application (CLI mode)
run:
	python -m src.cli.tepm session start --symbols BTC-USD --env paper

# Run the application (direct mode)
run-app:
	python -m src.app --symbols BTC-USD --env paper

# Start the API server
run-api:
	uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8000

# Clean build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf logs/
	rm -rf data/

# Run linters
lint:
	flake8 src/ tests/ --max-line-length=100 --ignore=E203,W503
	black --check src/ tests/
	isort --check-only src/ tests/

# Format code
format:
	black src/ tests/
	isort src/ tests/

# Initialize development environment
dev-setup: install
	@echo "Creating .env file..."
	@cp .env.example .env 2>/dev/null || echo "No .env.example found"
	@echo "Setting up data directories..."
	@mkdir -p data/snapshots logs
	@echo "Development environment ready!"

# Quick test run (specific tests mentioned in requirements)
test-quick:
	pytest tests/test_ofi.py tests/test_portfolio_fsm.py -v

# Check if application can start
check-startup:
	@echo "Testing application startup..."
	@timeout 5 python -c "from src.app import TEPMApp; print('Import successful')" || echo "Import failed"
	@echo "Testing CLI..."
	@python -m src.cli.tepm --help | head -5 || echo "CLI failed"
	@echo "Testing API server import..."
	@python -c "from src.api.server import server; print('API import successful')" || echo "API import failed"
