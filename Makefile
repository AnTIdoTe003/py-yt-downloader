# YouTube Downloader - Makefile

.PHONY: help install test clean

help: ## Show this help message
	@echo "YouTube Downloader - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Install dependencies
	@echo "Installing dependencies..."
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	@echo "Installing development dependencies..."
	pip install -r requirements.txt
	pip install black flake8 pytest

test: ## Run tests
	@echo "Running tests..."
	python test_downloader.py

format: ## Format code with black
	@echo "Formatting code..."
	black youtube_downloader.py test_downloader.py

lint: ## Lint code with flake8
	@echo "Linting code..."
	flake8 youtube_downloader.py test_downloader.py

clean: ## Clean up generated files
	@echo "Cleaning up..."
	rm -rf __pycache__ *.pyc *.pyo .pytest_cache downloads/

setup: install ## Full setup (install dependencies)
	@echo "Setup complete! You can now use the YouTube downloader."

download: ## Download a video (usage: make download URL="https://youtube.com/watch?v=...")
	@if [ -z "$(URL)" ]; then \
		echo "Error: Please provide a URL. Usage: make download URL='https://youtube.com/watch?v=...'"; \
		exit 1; \
	fi
	@echo "Downloading video from: $(URL)"
	python youtube_downloader.py "$(URL)"

info: ## Get video information (usage: make info URL="https://youtube.com/watch?v=...")
	@if [ -z "$(URL)" ]; then \
		echo "Error: Please provide a URL. Usage: make info URL='https://youtube.com/watch?v=...'"; \
		exit 1; \
	fi
	@echo "Getting video information for: $(URL)"
	python youtube_downloader.py "$(URL)" -i

list-formats: ## List available formats (usage: make list-formats URL="https://youtube.com/watch?v=...")
	@if [ -z "$(URL)" ]; then \
		echo "Error: Please provide a URL. Usage: make list-formats URL='https://youtube.com/watch?v=...'"; \
		exit 1; \
	fi
	@echo "Listing formats for: $(URL)"
	python youtube_downloader.py "$(URL)" -l
