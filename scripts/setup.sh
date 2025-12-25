#!/bin/bash
# Setup script for manga video pipeline

echo "Setting up Manga Video Pipeline..."

# Create necessary directories
mkdir -p data/temp data/output data/logs credentials

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
python -m playwright install chromium

# Initialize database
python -c "from src.database.models import init_db; init_db()"

echo "Setup completed! You can now run the pipeline."
echo ""
echo "To run the pipeline: python -m src.cli run-pipeline"
echo "To start the dashboard: python -m src.cli start-server"