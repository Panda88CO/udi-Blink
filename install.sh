#!/usr/bin/env bash

export AIOHTTP_NO_EXTENSIONS=1

if command -v python3 >/dev/null 2>&1; then
    python3 -m pip install -r requirements.txt --user
elif command -v pip3 >/dev/null 2>&1; then
    pip3 install -r requirements.txt --user
elif command -v pip >/dev/null 2>&1; then
    pip install -r requirements.txt --user
else
    echo "ERROR: Neither python3, pip3, nor pip was found!"
    exit 1
fi