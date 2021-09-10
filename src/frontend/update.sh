#!/bin/bash

cd "$(dirname "$0")"

python ../backend/scrape/dtu_scrape.py
python ../backend/process/rate_courses.py
python ../backend/process/stats.py

./deploy.sh "Update course database"

