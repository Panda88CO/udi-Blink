#!/usr/bin/env python3
"""
UDI Blink Node Server
Compatibility entry point for PG3 / PG3x installations referencing BlinkController.py
"""
import os
import sys

if __name__ == "__main__":
    controller_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "udiBlinkController.py")
    with open(controller_file, "rb") as f:
        code = compile(f.read(), controller_file, "exec")
        exec(code, {"__name__": "__main__", "__file__": controller_file})

