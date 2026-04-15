#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Run any database migrations or initializations
python init_db.py
