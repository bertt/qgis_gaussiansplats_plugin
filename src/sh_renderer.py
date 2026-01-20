"""Custom renderer for Gaussian Splats with spherical harmonics support."""

import math
from typing import Optional

import numpy as np

from qgis.core import (
    QgsFeature,
    QgsFeatureRenderer,
    QgsSymbol,
    QgsMarkerSymbol,
    QgsProperty,
    QgsRenderContext,
    QgsExpression,
    QgsExpressionContext,
    QgsFields,
    QgsSymbolRenderContext,
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtXml import QDomDocument, QDomElement

from .sh_utils import eval_sh


class GaussianSplatRenderer(QgsFeatureRenderer):
    """Custom renderer for Gaussian Splats with view-dependent spherical harmonics.
    
    This renderer evaluates spherical harmonics based on the camera/view direction
    to produce view-dependent colors.
    """

    def __init__(self, symbol: Optional[QgsSymbol] = None):
        """Initialize the renderer.
        
        Args:
            symbol: Base symbol to use for rendering.
        """
        super().__init__("GaussianSplatRenderer")
        
        if symbol is None:
            # Create default symbol
            symbol = QgsMarkerSymbol.createSimple({
                "name": "circle",
                "size": "2",
                "size_unit": "Point",
                "outline_style": "no",
            })
        
        self._symbol = symbol
        self._view_direction = np.array([0.0, 0.0, 1.0])  # Default: looking down Z axis
        self._use_sh = True
        
    def clone(self) -> "GaussianSplatRenderer":
        """Create a copy of this renderer."""
        renderer = GaussianSplatRenderer(self._symbol.clone() if self._symbol else None)
        renderer._view_direction = self._view_direction.copy()
        renderer._use_sh = self._use_sh
        return renderer
    
    def type(self) -> str:
        """Return the renderer type identifier."""
        return "GaussianSplatRenderer"
    
    def symbolForFeature(self, feature: QgsFeature, context: QgsRenderContext) -> Optional[QgsSymbol]:
        """Get the symbol to use for rendering a specific feature.
        
        Args:
            feature: The feature to render.
            context: The render context.
            
        Returns:
            Symbol to use for rendering, or None.
        """
        if not self._symbol:
            return None
        
        # Clone the symbol for modification
        symbol = self._symbol.clone()
        
        # Get SH degree from attributes
        sh_degree_idx = feature.fieldNameIndex("sh_degree")
        if sh_degree_idx < 0:
            # No SH data, use regular color
            return symbol
        
        sh_degree = feature.attribute(sh_degree_idx)
        
        if not self._use_sh or sh_degree == 0:
            # Use stored RGB color
            r_idx = feature.fieldNameIndex("red")
            g_idx = feature.fieldNameIndex("green")
            b_idx = feature.fieldNameIndex("blue")
            a_idx = feature.fieldNameIndex("alpha")
            
            if r_idx >= 0 and g_idx >= 0 and b_idx >= 0:
                r = feature.attribute(r_idx)
                g = feature.attribute(g_idx)
                b = feature.attribute(b_idx)
                a = feature.attribute(a_idx) if a_idx >= 0 else 255
                
                color = QColor(int(r), int(g), int(b), int(a))
                symbol.setColor(color)
        else:
            # Evaluate spherical harmonics
            from .sh_utils import get_sh_coeffs_count
            
            sh_count = get_sh_coeffs_count(sh_degree)
            sh_coeffs = np.zeros(sh_count, dtype=np.float32)
            
            # Extract SH coefficients from attributes
            for i in range(sh_count):
                sh_idx = feature.fieldNameIndex(f"sh_{i}")
                if sh_idx >= 0:
                    sh_coeffs[i] = feature.attribute(sh_idx)
            
            # Evaluate SH for the current view direction
            rgb = eval_sh(sh_coeffs, self._view_direction, sh_degree)
            
            # Get alpha
            a_idx = feature.fieldNameIndex("alpha")
            a = feature.attribute(a_idx) if a_idx >= 0 else 255
            
            # Convert to QColor
            r = int(rgb[0] * 255)
            g = int(rgb[1] * 255)
            b = int(rgb[2] * 255)
            color = QColor(r, g, b, int(a))
            symbol.setColor(color)
        
        # Set data-driven size based on scale
        size_expression = "clamp(1, (\"scale_x\" + \"scale_y\") / 2 * 10, 10)"
        symbol.symbolLayer(0).setDataDefinedProperty(
            symbol.symbolLayer(0).PropertySize,
            QgsProperty.fromExpression(size_expression),
        )
        
        return symbol
    
    def startRender(self, context: QgsRenderContext, fields: QgsFields) -> None:
        """Prepare the renderer for rendering.
        
        Args:
            context: The render context.
            fields: The layer's fields.
        """
        if self._symbol:
            self._symbol.startRender(context, fields)
        
        # Update view direction based on map rotation if available
        # In 2D map view, we use a fixed direction for now
        # This could be extended to use the map rotation angle
        
    def stopRender(self, context: QgsRenderContext) -> None:
        """Clean up after rendering.
        
        Args:
            context: The render context.
        """
        if self._symbol:
            self._symbol.stopRender(context)
    
    def usedAttributes(self, context: QgsRenderContext) -> set:
        """Return the set of attributes required by this renderer.
        
        Args:
            context: The render context.
            
        Returns:
            Set of attribute names.
        """
        attrs = {"red", "green", "blue", "alpha", "sh_degree", "scale_x", "scale_y", "scale_z"}
        
        # Add all possible SH coefficient attributes
        for i in range(48):  # Max for degree 3
            attrs.add(f"sh_{i}")
        
        if self._symbol:
            attrs.update(self._symbol.usedAttributes(context))
        
        return attrs
    
    def capabilities(self) -> int:
        """Return renderer capabilities."""
        return QgsFeatureRenderer.SymbolLevels
    
    def symbols(self, context: QgsRenderContext) -> list:
        """Return list of symbols used by the renderer.
        
        Args:
            context: The render context.
            
        Returns:
            List of symbols.
        """
        if self._symbol:
            return [self._symbol]
        return []
    
    def save(self, doc: QDomDocument, context: QgsRenderContext) -> QDomElement:
        """Save renderer configuration to XML.
        
        Args:
            doc: The XML document.
            context: The render context.
            
        Returns:
            The XML element.
        """
        elem = doc.createElement("renderer-v2")
        elem.setAttribute("type", self.type())
        elem.setAttribute("use_sh", "1" if self._use_sh else "0")
        elem.setAttribute("view_dir_x", str(self._view_direction[0]))
        elem.setAttribute("view_dir_y", str(self._view_direction[1]))
        elem.setAttribute("view_dir_z", str(self._view_direction[2]))
        
        if self._symbol:
            symbol_elem = QgsSymbol.symbolToElement(self._symbol, doc, context)
            elem.appendChild(symbol_elem)
        
        return elem
    
    @staticmethod
    def create(element: QDomElement, context: QgsRenderContext) -> "GaussianSplatRenderer":
        """Create renderer from XML configuration.
        
        Args:
            element: The XML element.
            context: The render context.
            
        Returns:
            The renderer.
        """
        renderer = GaussianSplatRenderer()
        
        # Load settings
        use_sh = element.attribute("use_sh", "1") == "1"
        renderer._use_sh = use_sh
        
        view_x = float(element.attribute("view_dir_x", "0.0"))
        view_y = float(element.attribute("view_dir_y", "0.0"))
        view_z = float(element.attribute("view_dir_z", "1.0"))
        renderer._view_direction = np.array([view_x, view_y, view_z])
        
        # Load symbol
        symbol_elem = element.firstChildElement("symbol")
        if not symbol_elem.isNull():
            renderer._symbol = QgsSymbol.symbolFromElement(symbol_elem, context)
        
        return renderer
    
    def setViewDirection(self, direction: np.ndarray) -> None:
        """Set the viewing direction for spherical harmonics evaluation.
        
        Args:
            direction: Viewing direction as [x, y, z].
        """
        # Normalize the direction
        norm = np.linalg.norm(direction)
        if norm > 0:
            self._view_direction = direction / norm
        else:
            self._view_direction = np.array([0.0, 0.0, 1.0])
    
    def setUseSH(self, use_sh: bool) -> None:
        """Enable or disable spherical harmonics rendering.
        
        Args:
            use_sh: True to use SH, False to use stored RGB colors.
        """
        self._use_sh = use_sh
