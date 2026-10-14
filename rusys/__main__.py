# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Allow `python -m rusys` to launch the CLI."""
from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
