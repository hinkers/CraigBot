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

        # Start Craig
        python app.py

        # Deactive python virtual environment
        deactivate
    done
}

# Call the function
run_command
