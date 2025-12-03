#!/bin/bash

# Define a function to run the command in an infinite loop
function run_command() {
    while true
    do
        # Pull the latest commit from git
        git pull

        # Activate the Python virtual environment
        source venv/bin/activate

        # Install the requirements
        pip-review --auto

        # Kill any existing celery worker processes
        pkill -f 'celery worker'

        # Start the Celery worker process with nice
        celery -A audio.tasks worker --concurrency=1 &

        # Start Craig
        python app.py

        # Deactivate python virtual environment
        deactivate
    done
}

# Call the function
run_command
