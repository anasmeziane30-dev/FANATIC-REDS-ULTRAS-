#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install ffmpeg for voice support
apt-get update && apt-get install -y ffmpeg

# Install python requirements
pip install -r requirements.txt
