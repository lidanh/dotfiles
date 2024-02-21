#!/bin/bash

# Check if a folder was specified
if [ "$1" ]; then
    # Start Jupyter Notebook in the specified folder
    /opt/homebrew/bin/jupyter notebook --no-browser --notebook-dir="$1"
else
    # Start Jupyter Notebook in the ~/Projects folder
    /opt/homebrew/bin/jupyter notebook --no-browser --notebook-dir=~/Projects
fi