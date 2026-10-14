# Contributing to Rusys

First off, thank you for considering contributing to **Rusys**! 🎉

Rusys is a 3rd-party extension of the Pro Tool project — a from-scratch Python/PySide6 rebuild of the Rufus USB boot-media utility. Every contribution helps make it better.

---

## 📜 Code of Conduct

Be respectful, constructive, and professional. We're all here to build great software together.

---

## 🐛 Reporting Bugs

1. **Search existing issues** first to avoid duplicates.
2. Open a new issue with:
   - A clear, descriptive title
   - Steps to reproduce the problem
   - Expected vs. actual behavior
   - Your OS, Python version, and Rusys version (`rusys --version`)
   - Any relevant log output or screenshots

---

## 💡 Requesting Features

1. Check if the feature has already been requested.
2. Open a feature request issue with:
   - A clear description of the proposed feature
   - The use case / problem it solves
   - Any alternatives you've considered

---

## 🔧 Development Setup

### Prerequisites
- Python ≥ 3.10
- pip

### Getting Started

```bash
# Fork and clone the repository
git clone https://github.com/<your-username>/Rusys.git
cd Rusys

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Run the GUI
python -m rusys --gui
```

---

## 📝 Making Changes

### Branch Naming
- `fix/<short-description>` — Bug fixes
- `feature/<short-description>` — New features
- `docs/<short-description>` — Documentation changes

### Commit Messages
Follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope): short description

feat(downloader): add CDN cookie session support
fix(catalog): fix Windows download crash
docs(readme): update installation instructions
```

### Code Style
- Follow **PEP 8** with a line length of 100 characters.
- Use **type hints** for all function signatures.
- Every source file must carry the Pro Tool header:

```python
# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later
```

### Pull Request Process

1. **Fork** the repository and create your branch from `main`.
2. **Make your changes** with clear, atomic commits.
3. **Test your changes** thoroughly.
4. **Update documentation** if you've changed behavior.
5. **Open a Pull Request** with a clear description.

---

## 🏗️ Architecture Overview

```
rusys/
├── core/          # Business logic (no Qt imports)
│   ├── downloader.py    # HTTP download engine with CDN cookie support
│   ├── flasher.py       # Image flashing engine
│   ├── devices.py       # USB device enumeration
│   ├── checksum.py      # SHA-256 verification
│   ├── settings.py      # Persistent configuration
│   └── privileges.py    # pkexec/udev privilege management
├── data/          # OS catalog & download data
│   └── os_catalog.py    # OS download catalogue (Windows/Linux/Unix/Recovery)
└── ui/            # PySide6 GUI (depends on core/)
    ├── main_window.py   # Main application window
    ├── about_dialog.py  # About dialog
    └── catalog_widget.py # OS catalog browser
```

**Key principle:** `core/` must never import from `ui/`.

---

## 🔒 Security

If you discover a security vulnerability, please report it **privately**. See [SECURITY.md](SECURITY.md) for details.

---

## 📜 License

By contributing to Rusys, you agree that your contributions will be licensed under the **GPL-3.0-or-later** license, the same license that covers the project.

---

Thank you for contributing! 🙏
