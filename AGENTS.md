# AGENTS.md - QGIS Gaussian Splats Plugin

This document provides guidelines for AI coding agents working on this QGIS plugin
for Gaussian Splatting visualization.

## Project Overview

This is a QGIS Python plugin for visualizing 3D Gaussian Splats (.ply/.splat/.spz files).
QGIS plugins follow PyQGIS conventions and integrate with the QGIS application framework.

## Build/Development Commands

### Plugin Installation (Development)

```bash
# Create symlink to QGIS plugins directory (Windows)
mklink /D "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\gaussiansplats" "c:\dev\github.com\bertt\qgis_gaussiansplats\src"

# Linux/macOS
ln -s /path/to/qgis_gaussiansplats ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/gaussiansplats
```

### Compile Resources

```bash
# Compile Qt resources (if using .qrc files)
pyrcc5 resources.qrc -o resources_rc.py

# Compile UI files (if using Qt Designer)
pyuic5 -o ui_dialog.py dialog.ui
```

### Linting and Type Checking

```bash
# Run flake8 linting
flake8 . --max-line-length=120 --ignore=E501,W503

# Run pylint with QGIS-specific config
pylint --extension-pkg-whitelist=PyQt5 *.py

# Type checking with mypy
mypy . --ignore-missing-imports

# Format with black
black . --line-length=120
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_plugin.py -v

# Run a single test function
pytest tests/test_plugin.py::TestGaussianSplats::test_load_ply -v

# Run tests with coverage
pytest tests/ --cov=. --cov-report=html

# Run tests in QGIS environment (if needed)
python -m pytest tests/ --qgis
```

### Package for Distribution

```bash
# Create ZIP for QGIS plugin manager
zip -r gaussiansplats.zip . -x "*.git*" -x "*__pycache__*" -x "*.pytest_cache*" -x "tests/*"
```

## Code Style Guidelines

### Python Version

- Target Python 3.9+ (QGIS 3.28 LTS and newer)
- Use type hints for all function signatures

### Imports

Order imports as follows, separated by blank lines:
1. Standard library imports
2. PyQt5 imports
3. QGIS imports (qgis.core, qgis.gui, qgis.utils)
4. Third-party imports (numpy, etc.)
5. Local plugin imports

```python
import os
from pathlib import Path
from typing import Optional, List, Dict

from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QMessageBox

from qgis.core import QgsProject, QgsVectorLayer, QgsPointCloudLayer
from qgis.gui import QgisInterface

import numpy as np

from .dialog import GaussianSplatsDialog
from .utils import parse_ply_file
```

### Formatting

- Line length: 120 characters maximum
- Use 4 spaces for indentation (no tabs)
- Use double quotes for strings
- Add trailing commas in multi-line collections
- One blank line between methods, two between classes

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `GaussianSplatsPlugin` |
| Functions/Methods | snake_case | `load_splat_file()` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_POINT_SIZE` |
| Private methods | Leading underscore | `_parse_header()` |
| Instance variables | snake_case | `self.iface` |
| Qt signals | camelCase | `dataLoaded` |

### Type Hints

Always use type hints for function parameters and return values:

```python
def load_splat_file(self, file_path: Path) -> Optional[QgsPointCloudLayer]:
    """Load a Gaussian splat file and return a point cloud layer."""
    ...

def get_splat_colors(self, points: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """Extract RGBA colors from splat data."""
    ...
```

### Error Handling

- Use specific exception types, not bare `except:`
- Log errors using QGIS message log
- Show user-friendly messages for recoverable errors

```python
from qgis.core import QgsMessageLog, Qgis

try:
    layer = self._load_point_cloud(file_path)
except FileNotFoundError:
    QgsMessageLog.logMessage(
        f"File not found: {file_path}",
        "GaussianSplats",
        level=Qgis.Warning
    )
    self.iface.messageBar().pushWarning("Gaussian Splats", "File not found")
    return None
except ValueError as e:
    QgsMessageLog.logMessage(
        f"Invalid file format: {e}",
        "GaussianSplats",
        level=Qgis.Critical
    )
    raise
```

### Documentation

- Use docstrings for all public classes and methods
- Follow Google-style docstring format
- Include parameter types and return types in docstrings

```python
def parse_ply_header(self, file_path: Path) -> Dict[str, Any]:
    """Parse the header of a PLY file containing Gaussian splat data.

    Args:
        file_path: Path to the PLY file to parse.

    Returns:
        Dictionary containing header information with keys:
        - vertex_count: Number of vertices
        - properties: List of property definitions
        - format: File format (ascii/binary)

    Raises:
        ValueError: If the file is not a valid PLY file.
    """
    ...
```

### QGIS-Specific Patterns

#### Plugin Class Structure

```python
class GaussianSplatsPlugin:
    """Main plugin class implementing QGIS plugin interface."""

    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface
        self.plugin_dir = Path(__file__).parent
        self.actions: List[QAction] = []
        self.toolbar = None

    def initGui(self) -> None:
        """Initialize the plugin GUI (called by QGIS)."""
        ...

    def unload(self) -> None:
        """Cleanup when plugin is unloaded (called by QGIS)."""
        ...
```

#### Settings Storage

```python
# Use QSettings with plugin-specific group
settings = QSettings()
settings.beginGroup("GaussianSplats")
last_dir = settings.value("lastDirectory", "")
settings.setValue("lastDirectory", str(file_path.parent))
settings.endGroup()
```

### File Structure

```
qgis_gaussiansplats/src
├── __init__.py           # Plugin entry point (classFactory)
├── metadata.txt          # Plugin metadata for QGIS
├── plugin.py             # Main plugin class
├── dialog.py             # Dialog windows
├── ui_dialog.py          # Compiled UI (generated)
├── resources_rc.py       # Compiled resources (generated)
├── icons/                # Plugin icons
├── utils/                # Utility modules
│   ├── __init__.py
│   ├── ply_parser.py
│   └── splat_renderer.py
└── tests/                # Test files
    ├── __init__.py
    ├── conftest.py
    └── test_plugin.py
```

### Required Files

#### metadata.txt

```ini
[general]
name=Gaussian Splats
description=Visualize 3D Gaussian Splats in QGIS
version=0.1.0
qgisMinimumVersion=3.28
author=Your Name
email=your@email.com
```

#### __init__.py

```python
def classFactory(iface):
    from .plugin import GaussianSplatsPlugin
    return GaussianSplatsPlugin(iface)
```
