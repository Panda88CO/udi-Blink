#!/usr/bin/env bash

# Disable C extensions on platforms without C compiler/headers (e.g. FreeBSD on Polisy/eisy)
export AIOHTTP_NO_EXTENSIONS=1
export FROZENLIST_NO_EXTENSIONS=1
export MULTIDICT_NO_EXTENSIONS=1
export YARL_NO_EXTENSIONS=1
export PATH="$HOME/.local/bin:$PATH"

# Determine pip command
PIP_CMD=""
if command -v python3 >/dev/null 2>&1; then
    PIP_CMD="python3 -m pip"
elif command -v pip3 >/dev/null 2>&1; then
    PIP_CMD="pip3"
elif command -v pip >/dev/null 2>&1; then
    PIP_CMD="pip"
else
    echo "ERROR: Neither python3, pip3, nor pip was found!"
    exit 1
fi

# Pre-install aiohttp in pure-Python mode to avoid C extension build failure on FreeBSD
$PIP_CMD install aiohttp --no-binary=aiohttp --user

# Install all other dependencies
$PIP_CMD install -r requirements.txt --user