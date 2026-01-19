# QGIS Gaussian Splats Plugin

A QGIS plugin for loading and visualizing 3D Gaussian Splats from URL, similar to ArcGIS Pro 3.6.

## Features

- Load Gaussian Splats from URL (`.splat` and `.ply` formats)
- Visualize splats in 2D map view as colored point clouds
- Visualize splats in QGIS 3D View
- Configure georeferencing (CRS, origin, scale)
- Data-driven styling based on splat colors

## Requirements

- QGIS 3.28 or later
- Python 3.9+
- NumPy (usually included with QGIS)

## Installation

### Method 1: Symlink (Recommended for Development)

**Windows (Run as Administrator):**

```cmd
mklink /D "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\gaussiansplats" "c:\dev\github.com\bertt\qgis_gaussiansplats"
```

**Linux/macOS:**

```bash
ln -s /path/to/qgis_gaussiansplats ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/gaussiansplats
```

### Method 2: Copy Files

Copy this entire folder to your QGIS plugins directory:

- **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\gaussiansplats`
- **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/gaussiansplats`
- **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/gaussiansplats`

### Enable the Plugin

1. Open QGIS
2. Go to **Plugins** → **Manage and Install Plugins...**
3. Go to **Installed** tab
4. Check the box next to **Gaussian Splats**
5. Click **Close**

## Usage

### Loading Gaussian Splats from URL

1. Click the **Gaussian Splats** button in the toolbar, or go to **Plugins** → **Gaussian Splats** → **Load Gaussian Splats from URL**

2. In the dialog:
   - Enter a URL to a `.splat` or `.ply` file
   - Or select from the example URLs dropdown

3. Configure georeferencing (optional):
   - **CRS**: Coordinate Reference System (default: EPSG:4326)
   - **Origin**: X, Y, Z offset to apply to all points
   - **Scale**: Scale factor for positions

4. Options:
   - **Add to 3D View**: Enable 3D rendering (if QGIS 3D is available)
   - **Zoom to layer**: Automatically zoom to the loaded data

5. Click **Load**

### Viewing in 3D

1. After loading a Gaussian Splat layer, go to **View** → **3D Map Views** → **New 3D Map View**
2. The splat layer should be visible as a 3D point cloud
3. Use the 3D navigation controls to explore

## Example URLs

Todo 

## Testing the Plugin

### Quick Test

1. Install and enable the plugin (see Installation above)
2. Restart QGIS if needed
3. Click the Gaussian Splats toolbar button
4. Select "plush.splat" from the Examples dropdown
5. Click **Load**
6. Wait for download and parsing to complete
7. The splat should appear as a colored point cloud in the map view

### Testing 3D View

1. Load a splat file as above
2. Go to **View** → **3D Map Views** → **New 3D Map View**
3. In the 3D view settings, ensure the layer is enabled
4. Navigate around the 3D scene

### Verify Layer Properties

After loading, right-click the layer and check:
- **Properties** → **Source**: Should show PointZ geometry
- **Properties** → **Symbology**: Should show data-driven color styling
- **Attribute Table**: Should have columns for red, green, blue, alpha, scale_x, scale_y, scale_z

## File Formats

### .splat Format

Binary format with 32 bytes per splat:
- 12 bytes: Position (3 × float32: x, y, z)
- 12 bytes: Scale (3 × float32: sx, sy, sz)
- 4 bytes: Color (4 × uint8: r, g, b, a)
- 4 bytes: Rotation (4 × uint8: quaternion components)

### .ply Format

Standard PLY format with Gaussian Splat properties:
- `x, y, z`: Position
- `scale_0, scale_1, scale_2`: Scale (log-space)
- `f_dc_0, f_dc_1, f_dc_2`: Spherical harmonics coefficients for color
- `opacity`: Opacity (logit-space)
- `rot_0, rot_1, rot_2, rot_3`: Rotation quaternion

## Troubleshooting

### Plugin doesn't appear in QGIS

1. Check the plugin is in the correct directory
2. Ensure the folder is named `gaussiansplats` (lowercase)
3. Check QGIS Python console for errors: **Plugins** → **Python Console**, then type `import gaussiansplats`

### Download fails

1. Check your internet connection
2. Verify the URL is correct and accessible
3. Some URLs may require CORS headers - try a different source

### 3D view not working

1. Ensure QGIS was built with 3D support
2. Check **View** → **3D Map Views** is available
3. The 3D renderer may not be available on all platforms

### Performance issues with large files

- Large splat files (>1M points) may take time to load and render
- Consider using a subset or lower resolution version
- QGIS performance depends on your GPU capabilities

## Development

See [AGENTS.md](AGENTS.md) for development guidelines.

### Project Structure

```
qgis_gaussiansplats/
├── __init__.py           # Plugin entry point
├── metadata.txt          # Plugin metadata
├── gaussian_splats.py    # Main plugin class
├── dialog.py             # URL loading dialog
├── splat_loader.py       # Download and parse splat files
├── layer_creator.py      # Create QGIS layers
├── icons/
│   └── gaussian_splat.svg
├── AGENTS.md             # AI agent guidelines
└── README.md             # This file
```

## License

MIT License

## Acknowledgments

- [antimatter15/splat](https://github.com/antimatter15/splat) - WebGL Gaussian Splat viewer and file format reference
- [3D Gaussian Splatting](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/) - Original research paper
