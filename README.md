# GRBL Visualizer

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.4+-green.svg)
![License](https://img.shields.io/badge/license-GPL--3.0-orange.svg)

> Interactive dual-view GRBL G-Code visualizer and analyzer for CNC machines under Linux/KDE

## Features

- **Dual-view interface**: Side-by-side G-Code editor and 2D/3D canvas visualization
- **Bidirectional sync**: Click a line in the editor to highlight the corresponding path on the canvas, and vice versa
- **GRBL version selection**: Support for GRBL 1.1, 1.1H, and 1.1j with per-version command validation
- **Workpiece size analysis**: Automatic bounding box calculation and workpiece dimension display
- **Coordinate origin display**: Visual indicator for the work coordinate origin
- **Warnings and hints**: Version compatibility warnings, missing origin detection, feed rate checks
- **Optimization hints**: Detects redundant rapids, repeated tool changes, and other inefficiencies

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language  | Python 3.10+ |
| GUI       | PyQt6 |
| Numerics  | numpy |
| Plotting  | matplotlib |
| Testing   | pytest |

## Quick Start

```bash
git clone https://github.com/dasarne/grbl-visualizer.git
cd grbl-visualizer
pip install -r requirements.txt
python -m src.main
```

## Architecture Overview

The project is organized into focused modules:

```
src/
├── gcode/      # G-Code parsing, tokenization, GRBL command definitions
├── geometry/   # Coordinate transforms, bounding box, tool-path building
├── analyzer/   # Version compatibility warnings and optimization hints
└── ui/         # PyQt6 dual-view main window, editor panel, canvas panel
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design document.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for environment setup, testing, and code style guidelines.

> **Note:** This project uses an AI-assisted development workflow where GitHub Copilot coding agent implements features described in structured issues, guided by skills and architecture documents.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes following the code style guidelines in DEVELOPMENT.md
4. Run tests: `pytest tests/`
5. Submit a pull request using the PR template
