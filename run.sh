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
        pip install -r requirements.txt

        # Check if the celery worker process is running
        pgrep -f 'celery -A audio.tasks worker' > /dev/null

        # If the check returns non-zero, the process is not running, so start it
        if [ $? -ne 0 ]; then
            celery -A audio.tasks worker &
        fi

        # Start Craig
        python app.py

        # Deactive python virtual environment
        deactivate
    done
}

# Call the function
run_command
