"""
Gaussian Splats Plugin for QGIS

Load and visualize 3D Gaussian Splats from URL in 2D and 3D views.
"""

import os
from pathlib import Path
from typing import Optional, List

from PyQt5.QtCore import Qt, QSettings, QUrl
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QMessageBox

from qgis.core import QgsProject, QgsApplication
from qgis.gui import QgisInterface

from .dialog import GaussianSplatsDialog


class GaussianSplatsPlugin:
    """Main plugin class for Gaussian Splats visualization."""

    def __init__(self, iface: QgisInterface) -> None:
        """Initialize the plugin.

        Args:
            iface: QGIS interface instance.
        """
        self.iface = iface
        self.plugin_dir = Path(__file__).parent
        self.actions: List[QAction] = []
        self.menu = "&Gaussian Splats"
        self.toolbar = None
        self.dialog: Optional[GaussianSplatsDialog] = None

    def initGui(self) -> None:
        """Initialize the plugin GUI - called by QGIS when plugin is loaded."""
        # Create toolbar
        self.toolbar = self.iface.addToolBar("Gaussian Splats")
        self.toolbar.setObjectName("GaussianSplatsToolbar")

        # Create action for loading splats from URL
        icon_path = self.plugin_dir / "icons" / "gaussian_splat.svg"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            icon = QgsApplication.getThemeIcon("/mActionAddLayer.svg")

        self.action_load = QAction(icon, "Load Gaussian Splats from URL", self.iface.mainWindow())
        self.action_load.setStatusTip("Load Gaussian Splat data from a URL")
        self.action_load.triggered.connect(self.show_load_dialog)

        # Add to menu and toolbar
        self.iface.addPluginToMenu(self.menu, self.action_load)
        self.toolbar.addAction(self.action_load)
        self.actions.append(self.action_load)

    def unload(self) -> None:
        """Cleanup when plugin is unloaded - called by QGIS."""
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

        if self.toolbar:
            del self.toolbar

        if self.dialog:
            self.dialog.close()
            self.dialog = None

    def show_load_dialog(self) -> None:
        """Show the dialog to load Gaussian Splats from URL."""
        if self.dialog is None:
            self.dialog = GaussianSplatsDialog(self.iface, self.iface.mainWindow())

        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
