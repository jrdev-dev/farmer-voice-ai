#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Starting Render Build Process..."

# Install dependencies
pip install -r backend/requirements.txt

# Collect static files
python backend/manage.py collectstatic --no-input

# Run database migrations
python backend/manage.py migrate

echo "Build Process Completed Successfully!"
