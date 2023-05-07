#!/bin/bash

# Pull the latest commit from git
git pull

# Activate the Python virtual environment
source venv/bin/activate

# Install the requirements
pip install -r requirements.txt

# Define a function to run the command in an infinite loop
function run_command() {
    while true
    do
        python craig.py
    done
}

# Call the function
run_command
