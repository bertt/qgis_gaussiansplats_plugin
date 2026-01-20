"""Dialog for loading Gaussian Splats from URL."""

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QSettings, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QMessageBox,
    QGroupBox,
    QDoubleSpinBox,
    QCheckBox,
)

from qgis.core import (
    QgsMessageLog,
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsCoordinateTransform,
)
from qgis.gui import QgisInterface, QgsProjectionSelectionWidget

from .splat_loader import SplatLoaderThread
from .layer_creator import create_splat_layer


class GaussianSplatsDialog(QDialog):
    """Dialog for loading Gaussian Splats from a URL."""

    def __init__(self, iface: QgisInterface, parent=None) -> None:
        """Initialize the dialog.

        Args:
            iface: QGIS interface instance.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.iface = iface
        self.loader_thread: Optional[SplatLoaderThread] = None

        self.setWindowTitle("Load Gaussian Splats from URL")
        self.setMinimumWidth(500)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # URL input section
        url_group = QGroupBox("Data Source")
        url_layout = QVBoxLayout(url_group)

        # URL input
        url_input_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter URL to .splat, .ply, or .spz file...")
        url_input_layout.addWidget(url_label)
        url_input_layout.addWidget(self.url_input)
        url_layout.addLayout(url_input_layout)

        layout.addWidget(url_group)

        # Georeferencing section
        geo_group = QGroupBox("Georeferencing")
        geo_layout = QVBoxLayout(geo_group)

        # CRS selection
        crs_layout = QHBoxLayout()
        crs_label = QLabel("CRS:")
        self.crs_selector = QgsProjectionSelectionWidget()
        self.crs_selector.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        crs_layout.addWidget(crs_label)
        crs_layout.addWidget(self.crs_selector)
        geo_layout.addLayout(crs_layout)

        # Origin coordinates
        origin_layout = QHBoxLayout()
        origin_label = QLabel("Origin:")
        
        self.origin_x = QDoubleSpinBox()
        self.origin_x.setRange(-180, 180)
        self.origin_x.setDecimals(6)
        self.origin_x.setValue(0)
        self.origin_x.setPrefix("X: ")
        
        self.origin_y = QDoubleSpinBox()
        self.origin_y.setRange(-90, 90)
        self.origin_y.setDecimals(6)
        self.origin_y.setValue(0)
        self.origin_y.setPrefix("Y: ")
        
        self.origin_z = QDoubleSpinBox()
        self.origin_z.setRange(-10000, 100000)
        self.origin_z.setDecimals(2)
        self.origin_z.setValue(0)
        self.origin_z.setPrefix("Z: ")

        origin_layout.addWidget(origin_label)
        origin_layout.addWidget(self.origin_x)
        origin_layout.addWidget(self.origin_y)
        origin_layout.addWidget(self.origin_z)
        geo_layout.addLayout(origin_layout)

        # Scale factor
        scale_layout = QHBoxLayout()
        scale_label = QLabel("Scale:")
        self.scale_factor = QDoubleSpinBox()
        self.scale_factor.setRange(0.0001, 10000)
        self.scale_factor.setDecimals(4)
        self.scale_factor.setValue(1.0)
        self.scale_factor.setSingleStep(0.1)
        scale_layout.addWidget(scale_label)
        scale_layout.addWidget(self.scale_factor)
        scale_layout.addStretch()
        geo_layout.addLayout(scale_layout)

        layout.addWidget(geo_group)

        # Options section
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.add_to_3d_view = QCheckBox("Add to 3D View (if available)")
        self.add_to_3d_view.setChecked(True)
        options_layout.addWidget(self.add_to_3d_view)

        self.zoom_to_layer = QCheckBox("Zoom to layer after loading")
        self.zoom_to_layer.setChecked(True)
        options_layout.addWidget(self.zoom_to_layer)

        layout.addWidget(options_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        self.load_button = QPushButton("Load")
        self.load_button.clicked.connect(self.load_splat)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_loading)
        self.cancel_button.setEnabled(False)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)

        button_layout.addStretch()
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)

    def load_settings(self) -> None:
        """Load saved settings."""
        settings = QSettings()
        settings.beginGroup("GaussianSplats")
        last_url = settings.value("lastUrl", "")
        if last_url:
            self.url_input.setText(last_url)
        settings.endGroup()

    def save_settings(self) -> None:
        """Save current settings."""
        settings = QSettings()
        settings.beginGroup("GaussianSplats")
        settings.setValue("lastUrl", self.url_input.text())
        settings.endGroup()

    def load_splat(self) -> None:
        """Start loading the Gaussian Splat from URL."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL.")
            return

        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "Error", "Please enter a valid HTTP/HTTPS URL.")
            return

        self.save_settings()
        self.set_loading_state(True)
        self.status_label.setText("Downloading...")

        # Get parameters
        crs = self.crs_selector.crs()
        origin = (self.origin_x.value(), self.origin_y.value(), self.origin_z.value())
        scale = self.scale_factor.value()

        # Start loading in background thread
        self.loader_thread = SplatLoaderThread(url, crs, origin, scale)
        self.loader_thread.progress.connect(self.on_progress)
        self.loader_thread.finished.connect(self.on_load_finished)
        self.loader_thread.error.connect(self.on_load_error)
        self.loader_thread.start()

    def cancel_loading(self) -> None:
        """Cancel the current loading operation."""
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.cancel()
            self.loader_thread.wait()
        self.set_loading_state(False)
        self.status_label.setText("Cancelled")

    def set_loading_state(self, loading: bool) -> None:
        """Update UI for loading state."""
        self.progress_bar.setVisible(loading)
        self.load_button.setEnabled(not loading)
        self.cancel_button.setEnabled(loading)
        self.url_input.setEnabled(not loading)
        if loading:
            self.progress_bar.setValue(0)

    def on_progress(self, value: int, message: str) -> None:
        """Handle progress updates."""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def on_load_finished(self, layer_data: dict) -> None:
        """Handle successful load completion."""
        self.set_loading_state(False)

        try:
            # Create the layer
            layer = create_splat_layer(
                layer_data,
                self.iface,
                add_to_3d=self.add_to_3d_view.isChecked(),
            )

            if layer and layer.isValid():
                self.status_label.setText(f"Loaded {layer_data['point_count']:,} points")

                if self.zoom_to_layer.isChecked():
                    # Get layer extent
                    extent = layer.extent()
                    
                    # Transform extent if map canvas CRS differs from layer CRS
                    canvas = self.iface.mapCanvas()
                    layer_crs = layer.crs()
                    canvas_crs = canvas.mapSettings().destinationCrs()
                    
                    QgsMessageLog.logMessage(
                        f"Zoom debug - Layer CRS: {layer_crs.authid()}, Canvas CRS: {canvas_crs.authid()}",
                        "GaussianSplats",
                        level=Qgis.Info,
                    )
                    QgsMessageLog.logMessage(
                        f"Zoom debug - Layer extent before transform: {extent.toString()}",
                        "GaussianSplats",
                        level=Qgis.Info,
                    )
                    
                    if layer_crs != canvas_crs:
                        # Transform extent to canvas CRS
                        transform = QgsCoordinateTransform(layer_crs, canvas_crs, QgsProject.instance())
                        extent = transform.transformBoundingBox(extent)
                        QgsMessageLog.logMessage(
                            f"Zoom debug - Layer extent after transform to {canvas_crs.authid()}: {extent.toString()}",
                            "GaussianSplats",
                            level=Qgis.Info,
                        )
                    
                    # Set extent with some padding
                    canvas.setExtent(extent)
                    canvas.refresh()
                    
                    QgsMessageLog.logMessage(
                        f"Zoomed to extent: {extent.toString()}",
                        "GaussianSplats",
                        level=Qgis.Info,
                    )

                QgsMessageLog.logMessage(
                    f"Successfully loaded Gaussian Splat with {layer_data['point_count']:,} points",
                    "GaussianSplats",
                    level=Qgis.Info,
                )
            else:
                self.status_label.setText("Failed to create layer")
                QMessageBox.warning(self, "Error", "Failed to create layer from splat data.")

        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            QgsMessageLog.logMessage(
                f"Error creating layer: {str(e)}",
                "GaussianSplats",
                level=Qgis.Critical,
            )

    def on_load_error(self, error_message: str) -> None:
        """Handle load error."""
        self.set_loading_state(False)
        self.status_label.setText(f"Error: {error_message}")
        QMessageBox.critical(self, "Error", f"Failed to load Gaussian Splat:\n{error_message}")
        QgsMessageLog.logMessage(
            f"Error loading Gaussian Splat: {error_message}",
            "GaussianSplats",
            level=Qgis.Critical,
        )

    def closeEvent(self, event) -> None:
        """Handle dialog close."""
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.cancel()
            self.loader_thread.wait()
        super().closeEvent(event)
