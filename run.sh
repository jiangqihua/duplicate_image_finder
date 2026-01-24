#!/bin/bash

# Run script for Duplicate Image Finder

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found!"
    echo "Please run ./setup.sh first to set up the environment."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Run the application
python main.py

# Deactivate when done
deactivate
