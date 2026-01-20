"""Layer creator - creates QGIS layers from parsed Gaussian Splat data."""

import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsField,
    QgsFields,
    QgsWkbTypes,
    QgsVectorFileWriter,
    QgsCoordinateTransformContext,
    QgsMarkerSymbol,
    QgsProperty,
    QgsSingleSymbolRenderer,
    QgsRuleBasedRenderer,
    QgsMessageLog,
    Qgis,
)
from qgis.gui import QgisInterface

from PyQt5.QtCore import QVariant
from PyQt5.QtGui import QColor


def create_splat_layer(
    layer_data: Dict[str, Any],
    iface: QgisInterface,
    add_to_3d: bool = True,
) -> Optional[QgsVectorLayer]:
    """Create a QGIS vector layer from Gaussian Splat data.

    The layer is created as a point layer with attributes for color and scale,
    styled to render points with appropriate colors and sizes.

    Args:
        layer_data: Dictionary containing parsed splat data with keys:
            - positions: numpy array of (x, y, z) coordinates
            - colors: numpy array of (r, g, b, a) values (0-255)
            - scales: numpy array of scale factors
            - point_count: number of points
            - crs: QgsCoordinateReferenceSystem
            - name: layer name
        iface: QGIS interface instance.
        add_to_3d: Whether to configure the layer for 3D viewing.

    Returns:
        The created QgsVectorLayer, or None if creation failed.
    """
    try:
        positions = layer_data["positions"]
        colors = layer_data["colors"]
        scales = layer_data["scales"]
        point_count = layer_data["point_count"]
        crs = layer_data["crs"]
        name = layer_data.get("name", "Gaussian Splat")
        sh_coeffs = layer_data.get("sh_coeffs")
        sh_degree = layer_data.get("sh_degree", 0)

        QgsMessageLog.logMessage(
            f"Creating layer with {point_count:,} points (SH degree: {sh_degree})",
            "GaussianSplats",
            level=Qgis.Info,
        )

        # Create a memory layer
        layer_uri = f"PointZ?crs={crs.authid()}"
        layer = QgsVectorLayer(layer_uri, name, "memory")

        if not layer.isValid():
            QgsMessageLog.logMessage(
                "Failed to create memory layer",
                "GaussianSplats",
                level=Qgis.Critical,
            )
            return None

        # Add attribute fields
        provider = layer.dataProvider()
        fields = QgsFields()
        fields.append(QgsField("red", QVariant.Int))
        fields.append(QgsField("green", QVariant.Int))
        fields.append(QgsField("blue", QVariant.Int))
        fields.append(QgsField("alpha", QVariant.Int))
        fields.append(QgsField("scale_x", QVariant.Double))
        fields.append(QgsField("scale_y", QVariant.Double))
        fields.append(QgsField("scale_z", QVariant.Double))
        fields.append(QgsField("color_hex", QVariant.String))
        fields.append(QgsField("sh_degree", QVariant.Int))
        
        # Add SH coefficient fields if available
        if sh_coeffs is not None:
            from .sh_utils import get_sh_coeffs_count
            sh_count = get_sh_coeffs_count(sh_degree)
            for i in range(sh_count):
                fields.append(QgsField(f"sh_{i}", QVariant.Double))
        
        provider.addAttributes(fields)
        layer.updateFields()

        # Add features in batches for performance
        batch_size = 10000
        features = []

        for i in range(point_count):
            x, y, z = positions[i]
            r, g, b, a = colors[i]
            sx, sy, sz = scales[i]

            # Create point geometry with Z
            point = QgsGeometry.fromPointXY(QgsPointXY(x, y))
            # Set Z value
            point.get().addZValue()
            point.get().setZ(z)

            # Create feature
            feature = QgsFeature()
            feature.setGeometry(point)
            
            # Build attributes list
            attrs = [
                int(r),
                int(g),
                int(b),
                int(a),
                float(sx),
                float(sy),
                float(sz),
                f"#{r:02x}{g:02x}{b:02x}",
                int(sh_degree),
            ]
            
            # Add SH coefficients if available
            if sh_coeffs is not None:
                sh_values = sh_coeffs[i].tolist()
                attrs.extend([float(v) for v in sh_values])
            
            feature.setAttributes(attrs)
            features.append(feature)

            # Add in batches
            if len(features) >= batch_size:
                provider.addFeatures(features)
                features = []

        # Add remaining features
        if features:
            provider.addFeatures(features)

        layer.updateExtents()

        # Apply styling
        _apply_splat_styling(layer, sh_degree, sh_coeffs is not None)

        # Configure for 3D if requested
        if add_to_3d:
            _configure_3d_renderer(layer, sh_degree, sh_coeffs is not None)

        # Add to project
        QgsProject.instance().addMapLayer(layer)

        QgsMessageLog.logMessage(
            f"Layer '{name}' created successfully",
            "GaussianSplats",
            level=Qgis.Info,
        )

        return layer

    except Exception as e:
        QgsMessageLog.logMessage(
            f"Error creating layer: {str(e)}",
            "GaussianSplats",
            level=Qgis.Critical,
        )
        return None


def _apply_splat_styling(layer: QgsVectorLayer, sh_degree: int = 0, has_sh: bool = False) -> None:
    """Apply data-driven styling to the splat layer.

    Args:
        layer: The vector layer to style.
        sh_degree: Spherical harmonics degree (0-3).
        has_sh: Whether the layer has spherical harmonics data.
    """
    # Try to use custom SH renderer if SH data is available and degree > 0
    if has_sh and sh_degree > 0:
        try:
            from .sh_renderer import GaussianSplatRenderer
            
            # Create base symbol
            symbol = QgsMarkerSymbol.createSimple({
                "name": "circle",
                "size": "2",
                "size_unit": "Point",
                "outline_style": "no",
            })
            
            # Create and configure SH renderer
            renderer = GaussianSplatRenderer(symbol)
            renderer.setUseSH(True)
            layer.setRenderer(renderer)
            layer.triggerRepaint()
            
            QgsMessageLog.logMessage(
                f"Applied spherical harmonics renderer (degree {sh_degree})",
                "GaussianSplats",
                level=Qgis.Info,
            )
            return
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Failed to apply SH renderer, falling back to standard renderer: {e}",
                "GaussianSplats",
                level=Qgis.Warning,
            )
    
    # Fall back to standard data-driven renderer
    # Create a marker symbol with data-driven color
    symbol = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "2",
        "size_unit": "Point",
        "outline_style": "no",
    })

    # Set data-driven color from attributes
    # Use an expression to build color from RGB attributes
    color_expression = "color_rgba(\"red\", \"green\", \"blue\", \"alpha\")"
    symbol.symbolLayer(0).setDataDefinedProperty(
        symbol.symbolLayer(0).PropertyFillColor,
        QgsProperty.fromExpression(color_expression),
    )

    # Set data-driven size based on scale (clamped for visibility)
    size_expression = "clamp(1, (\"scale_x\" + \"scale_y\") / 2 * 10, 10)"
    symbol.symbolLayer(0).setDataDefinedProperty(
        symbol.symbolLayer(0).PropertySize,
        QgsProperty.fromExpression(size_expression),
    )

    # Apply renderer
    renderer = QgsSingleSymbolRenderer(symbol)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def _configure_3d_renderer(layer: QgsVectorLayer, sh_degree: int = 0, has_sh: bool = False) -> None:
    """Configure 3D rendering for the layer.

    This sets up the layer to be visible in QGIS 3D map views.

    Args:
        layer: The vector layer to configure.
        sh_degree: Spherical harmonics degree (0-3).
        has_sh: Whether the layer has spherical harmonics data.
    """
    try:
        # Import 3D-specific classes (may not be available in all QGIS builds)
        from qgis._3d import (
            QgsVectorLayer3DRenderer,
            QgsPoint3DSymbol,
            QgsPhongMaterialSettings,
        )

        # Create 3D symbol
        symbol_3d = QgsPoint3DSymbol()
        symbol_3d.setShape(QgsPoint3DSymbol.Sphere)

        # Configure material with data-driven color
        material = QgsPhongMaterialSettings()
        material.setDiffuse(QColor(128, 128, 128))  # Default gray
        symbol_3d.setMaterial(material)

        # Set symbol size
        symbol_3d.setRadius(0.5)

        # Create and set 3D renderer
        renderer_3d = QgsVectorLayer3DRenderer()
        renderer_3d.setSymbol(symbol_3d)
        renderer_3d.setLayer(layer)
        layer.setRenderer3D(renderer_3d)

        QgsMessageLog.logMessage(
            "3D renderer configured successfully",
            "GaussianSplats",
            level=Qgis.Info,
        )

    except ImportError:
        QgsMessageLog.logMessage(
            "3D rendering not available - qgis._3d module not found",
            "GaussianSplats",
            level=Qgis.Warning,
        )
    except Exception as e:
        QgsMessageLog.logMessage(
            f"Failed to configure 3D renderer: {str(e)}",
            "GaussianSplats",
            level=Qgis.Warning,
        )
