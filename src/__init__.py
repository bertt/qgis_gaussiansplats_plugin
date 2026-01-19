"""QGIS Gaussian Splats Plugin - Entry Point"""


def classFactory(iface):
    """Load GaussianSplatsPlugin class from file plugin.py.

    Args:
        iface: A QGIS interface instance.

    Returns:
        GaussianSplatsPlugin instance.
    """
    from .gaussian_splats import GaussianSplatsPlugin
    return GaussianSplatsPlugin(iface)
