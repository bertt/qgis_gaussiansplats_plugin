"""Splat file loader - downloads and parses Gaussian Splat files."""

import gzip
import struct
from io import BytesIO
from typing import Dict, Any, Tuple, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

import numpy as np

from PyQt5.QtCore import QThread, pyqtSignal

from qgis.core import QgsCoordinateReferenceSystem


# SPZ format constants
SPZ_MAGIC = 0x5053474E  # 'NGSP' in little endian


class SplatLoaderThread(QThread):
    """Background thread for downloading and parsing Gaussian Splat files."""

    progress = pyqtSignal(int, str)  # progress percentage, message
    finished = pyqtSignal(dict)  # layer data dictionary
    error = pyqtSignal(str)  # error message

    def __init__(
        self,
        url: str,
        crs: QgsCoordinateReferenceSystem,
        origin: Tuple[float, float, float],
        scale: float,
        parent=None,
    ) -> None:
        """Initialize the loader thread.

        Args:
            url: URL to download the splat file from.
            crs: Coordinate reference system for the layer.
            origin: Origin coordinates (x, y, z) to offset the splat positions.
            scale: Scale factor to apply to positions.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.url = url
        self.crs = crs
        self.origin = origin
        self.scale = scale
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel the loading operation."""
        self._cancelled = True

    def run(self) -> None:
        """Execute the loading operation."""
        try:
            # Download the file
            self.progress.emit(0, "Connecting...")
            data = self._download_file()

            if self._cancelled:
                return

            # Parse based on file extension
            self.progress.emit(50, "Parsing splat data...")
            url_lower = self.url.lower()
            if url_lower.endswith(".ply"):
                layer_data = self._parse_ply(data)
            elif url_lower.endswith(".spz"):
                layer_data = self._parse_spz(data)
            else:
                # Assume .splat format
                layer_data = self._parse_splat(data)

            if self._cancelled:
                return

            self.progress.emit(100, "Complete")
            self.finished.emit(layer_data)

        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def _download_file(self) -> bytes:
        """Download the file from URL.

        Returns:
            Raw file bytes.

        Raises:
            Exception: If download fails.
        """
        try:
            request = Request(
                self.url,
                headers={"User-Agent": "QGIS-GaussianSplats/0.1"},
            )
            response = urlopen(request, timeout=60)

            # Get content length if available
            content_length = response.headers.get("Content-Length")
            total_size = int(content_length) if content_length else None

            # Download with progress
            data = BytesIO()
            downloaded = 0
            chunk_size = 65536  # 64KB chunks

            while True:
                if self._cancelled:
                    return b""

                chunk = response.read(chunk_size)
                if not chunk:
                    break

                data.write(chunk)
                downloaded += len(chunk)

                if total_size:
                    progress = int((downloaded / total_size) * 50)
                    size_mb = downloaded / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    self.progress.emit(progress, f"Downloading... {size_mb:.1f}/{total_mb:.1f} MB")

            return data.getvalue()

        except HTTPError as e:
            raise Exception(f"HTTP Error {e.code}: {e.reason}")
        except URLError as e:
            raise Exception(f"URL Error: {e.reason}")
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")

    def _parse_splat(self, data: bytes) -> Dict[str, Any]:
        """Parse .splat binary format.

        The .splat format stores each splat as 32 bytes:
        - 12 bytes: position (3 x float32)
        - 12 bytes: scale (3 x float32)
        - 4 bytes: color (4 x uint8: RGBA)
        - 4 bytes: rotation quaternion (4 x uint8, normalized)

        Args:
            data: Raw file bytes.

        Returns:
            Dictionary containing parsed layer data.
        """
        SPLAT_SIZE = 32
        num_splats = len(data) // SPLAT_SIZE

        if num_splats == 0:
            raise Exception("No splats found in file")

        self.progress.emit(55, f"Parsing {num_splats:,} splats...")

        # Pre-allocate arrays
        positions = np.zeros((num_splats, 3), dtype=np.float64)
        colors = np.zeros((num_splats, 4), dtype=np.uint8)
        scales = np.zeros((num_splats, 3), dtype=np.float32)
        rotations = np.zeros((num_splats, 4), dtype=np.float32)

        # Parse all splats
        for i in range(num_splats):
            if self._cancelled:
                return {}

            if i % 10000 == 0:
                progress = 55 + int((i / num_splats) * 40)
                self.progress.emit(progress, f"Parsing splat {i:,}/{num_splats:,}")

            offset = i * SPLAT_SIZE

            # Position (3 x float32)
            pos = struct.unpack_from("<3f", data, offset)
            positions[i] = [
                pos[0] * self.scale + self.origin[0],
                pos[1] * self.scale + self.origin[1],
                pos[2] * self.scale + self.origin[2],
            ]

            # Scale (3 x float32)
            scales[i] = struct.unpack_from("<3f", data, offset + 12)

            # Color (4 x uint8: RGBA)
            colors[i] = struct.unpack_from("<4B", data, offset + 24)

            # Rotation (4 x uint8, need to convert back to float)
            rot_bytes = struct.unpack_from("<4B", data, offset + 28)
            rotations[i] = [(b - 128) / 128.0 for b in rot_bytes]

        return {
            "positions": positions,
            "colors": colors,
            "scales": scales,
            "rotations": rotations,
            "point_count": num_splats,
            "crs": self.crs,
            "name": self.url.split("/")[-1].replace(".splat", "").replace(".ply", "").replace(".spz", ""),
        }

    def _parse_ply(self, data: bytes) -> Dict[str, Any]:
        """Parse PLY format Gaussian Splat file.

        Args:
            data: Raw file bytes.

        Returns:
            Dictionary containing parsed layer data.

        Raises:
            Exception: If PLY parsing fails.
        """
        # Parse PLY header
        header_end = data.find(b"end_header\n")
        if header_end == -1:
            raise Exception("Invalid PLY file: no header found")

        header = data[: header_end + 11].decode("ascii")
        binary_data = data[header_end + 11 :]

        # Parse header
        vertex_count = 0
        properties = []
        is_binary = False
        is_little_endian = True

        for line in header.split("\n"):
            line = line.strip()
            if line.startswith("element vertex"):
                vertex_count = int(line.split()[-1])
            elif line.startswith("property"):
                parts = line.split()
                prop_type = parts[1]
                prop_name = parts[2]
                properties.append((prop_name, prop_type))
            elif line.startswith("format"):
                if "binary_little_endian" in line:
                    is_binary = True
                    is_little_endian = True
                elif "binary_big_endian" in line:
                    is_binary = True
                    is_little_endian = False
                elif "ascii" in line:
                    is_binary = False

        if vertex_count == 0:
            raise Exception("Invalid PLY file: no vertices found")

        self.progress.emit(55, f"Parsing {vertex_count:,} vertices...")

        # Build property index
        prop_index = {name: i for i, (name, _) in enumerate(properties)}

        # Calculate struct format
        type_map = {
            "float": "f",
            "double": "d",
            "int": "i",
            "uint": "I",
            "short": "h",
            "ushort": "H",
            "char": "b",
            "uchar": "B",
        }

        endian = "<" if is_little_endian else ">"
        struct_format = endian + "".join(type_map.get(t, "f") for _, t in properties)
        struct_size = struct.calcsize(struct_format)

        # Pre-allocate arrays
        positions = np.zeros((vertex_count, 3), dtype=np.float64)
        colors = np.zeros((vertex_count, 4), dtype=np.uint8)
        scales = np.zeros((vertex_count, 3), dtype=np.float32)
        rotations = np.zeros((vertex_count, 4), dtype=np.float32)

        # Spherical harmonics constant for color conversion
        SH_C0 = 0.28209479177387814

        # Check which properties exist
        has_sh = "f_dc_0" in prop_index
        has_scale = "scale_0" in prop_index
        has_opacity = "opacity" in prop_index
        has_rot = "rot_0" in prop_index
        has_rgb = "red" in prop_index

        for i in range(vertex_count):
            if self._cancelled:
                return {}

            if i % 10000 == 0:
                progress = 55 + int((i / vertex_count) * 40)
                self.progress.emit(progress, f"Parsing vertex {i:,}/{vertex_count:,}")

            if is_binary:
                offset = i * struct_size
                values = struct.unpack_from(struct_format, binary_data, offset)
            else:
                # ASCII parsing would go here
                raise Exception("ASCII PLY format not yet supported")

            # Position
            x = values[prop_index.get("x", 0)]
            y = values[prop_index.get("y", 1)]
            z = values[prop_index.get("z", 2)]
            positions[i] = [
                x * self.scale + self.origin[0],
                y * self.scale + self.origin[1],
                z * self.scale + self.origin[2],
            ]

            # Color from spherical harmonics or direct RGB
            if has_sh:
                r = 0.5 + SH_C0 * values[prop_index["f_dc_0"]]
                g = 0.5 + SH_C0 * values[prop_index["f_dc_1"]]
                b = 0.5 + SH_C0 * values[prop_index["f_dc_2"]]
                colors[i, 0] = int(np.clip(r * 255, 0, 255))
                colors[i, 1] = int(np.clip(g * 255, 0, 255))
                colors[i, 2] = int(np.clip(b * 255, 0, 255))
            elif has_rgb:
                colors[i, 0] = int(values[prop_index["red"]])
                colors[i, 1] = int(values[prop_index["green"]])
                colors[i, 2] = int(values[prop_index["blue"]])
            else:
                colors[i, 0:3] = [128, 128, 128]  # Default gray

            # Opacity
            if has_opacity:
                opacity = 1.0 / (1.0 + np.exp(-values[prop_index["opacity"]]))
                colors[i, 3] = int(np.clip(opacity * 255, 0, 255))
            else:
                colors[i, 3] = 255

            # Scale
            if has_scale:
                scales[i] = [
                    np.exp(values[prop_index["scale_0"]]),
                    np.exp(values[prop_index["scale_1"]]),
                    np.exp(values[prop_index["scale_2"]]),
                ]
            else:
                scales[i] = [1.0, 1.0, 1.0]

            # Rotation
            if has_rot:
                rot = np.array([
                    values[prop_index["rot_0"]],
                    values[prop_index["rot_1"]],
                    values[prop_index["rot_2"]],
                    values[prop_index["rot_3"]],
                ])
                rotations[i] = rot / np.linalg.norm(rot)
            else:
                rotations[i] = [1.0, 0.0, 0.0, 0.0]

        return {
            "positions": positions,
            "colors": colors,
            "scales": scales,
            "rotations": rotations,
            "point_count": vertex_count,
            "crs": self.crs,
            "name": self.url.split("/")[-1].replace(".splat", "").replace(".ply", "").replace(".spz", ""),
        }

    def _parse_spz(self, data: bytes) -> Dict[str, Any]:
        """Parse SPZ format Gaussian Splat file.

        SPZ is a compressed format by Niantic Labs. The file is gzipped and contains:
        - 16-byte header
        - Positions (24-bit fixed point per component)
        - Alphas (uint8)
        - Colors (RGB uint8)
        - Scales (log-encoded uint8)
        - Rotations (quaternion components)
        - Optional spherical harmonics

        Args:
            data: Raw file bytes (gzipped).

        Returns:
            Dictionary containing parsed layer data.

        Raises:
            Exception: If SPZ parsing fails.
        """
        # Decompress gzip data
        try:
            decompressed = gzip.decompress(data)
        except Exception as e:
            raise Exception(f"Failed to decompress SPZ file: {e}")

        # Parse header (16 bytes)
        if len(decompressed) < 16:
            raise Exception("Invalid SPZ file: too small for header")

        header = struct.unpack("<IIIBBBB", decompressed[:16])
        magic = header[0]
        version = header[1]
        num_points = header[2]
        sh_degree = header[3]
        fractional_bits = header[4]
        flags = header[5]
        # reserved = header[6]

        if magic != SPZ_MAGIC:
            raise Exception(f"Invalid SPZ file: bad magic number (got 0x{magic:08X}, expected 0x{SPZ_MAGIC:08X})")

        if version not in (2, 3):
            raise Exception(f"Unsupported SPZ version: {version}")

        if num_points == 0:
            raise Exception("SPZ file contains no points")

        self.progress.emit(55, f"Parsing {num_points:,} splats (SPZ v{version})...")

        # Calculate sizes for each section
        positions_size = num_points * 9  # 3 components * 3 bytes each (24-bit)
        alphas_size = num_points
        colors_size = num_points * 3  # RGB

        if version == 3:
            scales_size = num_points * 3
            rotations_size = num_points * 4  # 32 bits for smallest-three encoding
        else:  # version 2
            scales_size = num_points * 3
            rotations_size = num_points * 3  # xyz components only

        # Calculate spherical harmonics size
        sh_coeffs_per_point = 0
        if sh_degree == 1:
            sh_coeffs_per_point = 9
        elif sh_degree == 2:
            sh_coeffs_per_point = 24
        elif sh_degree == 3:
            sh_coeffs_per_point = 45
        sh_size = num_points * sh_coeffs_per_point

        # Verify we have enough data
        expected_size = 16 + positions_size + alphas_size + colors_size + scales_size + rotations_size + sh_size
        if len(decompressed) < expected_size:
            raise Exception(f"Invalid SPZ file: insufficient data (got {len(decompressed)}, expected {expected_size})")

        # Pre-allocate arrays
        positions = np.zeros((num_points, 3), dtype=np.float64)
        colors = np.zeros((num_points, 4), dtype=np.uint8)
        scales = np.zeros((num_points, 3), dtype=np.float32)
        rotations = np.zeros((num_points, 4), dtype=np.float32)

        # Parse positions (24-bit fixed point per component)
        offset = 16
        scale_factor = 1.0 / (1 << fractional_bits)

        for i in range(num_points):
            if self._cancelled:
                return {}

            if i % 50000 == 0:
                progress = 55 + int((i / num_points) * 20)
                self.progress.emit(progress, f"Parsing positions {i:,}/{num_points:,}")

            for j in range(3):  # x, y, z
                # Read 3 bytes as 24-bit signed integer
                b0 = decompressed[offset]
                b1 = decompressed[offset + 1]
                b2 = decompressed[offset + 2]
                offset += 3

                # Combine bytes into 24-bit value (little-endian)
                val = b0 | (b1 << 8) | (b2 << 16)

                # Sign extend from 24-bit to 32-bit
                if val & 0x800000:
                    val = val - 0x1000000

                # Convert from fixed point to float and apply transforms
                coord = val * scale_factor
                positions[i, j] = coord * self.scale + self.origin[j]

        # Parse alphas
        self.progress.emit(75, "Parsing alphas...")
        for i in range(num_points):
            colors[i, 3] = decompressed[offset]
            offset += 1

        # Parse colors (RGB)
        self.progress.emit(80, "Parsing colors...")
        for i in range(num_points):
            colors[i, 0] = decompressed[offset]  # R
            colors[i, 1] = decompressed[offset + 1]  # G
            colors[i, 2] = decompressed[offset + 2]  # B
            offset += 3

        # Parse scales (log-encoded uint8)
        self.progress.emit(85, "Parsing scales...")
        for i in range(num_points):
            for j in range(3):
                log_scale = struct.unpack("b", bytes([decompressed[offset]]))[0]  # signed byte
                scales[i, j] = np.exp(log_scale / 16.0)  # Decode log scale
                offset += 1

        # Parse rotations
        self.progress.emit(90, "Parsing rotations...")
        if version == 3:
            # Version 3: smallest-three encoding (32 bits total)
            for i in range(num_points):
                # Read 4 bytes
                rot_data = struct.unpack("<I", decompressed[offset:offset + 4])[0]
                offset += 4

                # Extract largest component index (2 bits) and three 10-bit signed values
                largest_idx = rot_data & 0x3
                c0 = ((rot_data >> 2) & 0x3FF)
                c1 = ((rot_data >> 12) & 0x3FF)
                c2 = ((rot_data >> 22) & 0x3FF)

                # Sign extend 10-bit values
                if c0 & 0x200:
                    c0 = c0 - 0x400
                if c1 & 0x200:
                    c1 = c1 - 0x400
                if c2 & 0x200:
                    c2 = c2 - 0x400

                # Convert to float (-1 to 1 range)
                scale = 1.0 / 511.0
                c0_f = c0 * scale
                c1_f = c1 * scale
                c2_f = c2 * scale

                # Reconstruct quaternion
                sum_sq = c0_f * c0_f + c1_f * c1_f + c2_f * c2_f
                largest = np.sqrt(max(0.0, 1.0 - sum_sq))

                if largest_idx == 0:
                    rotations[i] = [largest, c0_f, c1_f, c2_f]
                elif largest_idx == 1:
                    rotations[i] = [c0_f, largest, c1_f, c2_f]
                elif largest_idx == 2:
                    rotations[i] = [c0_f, c1_f, largest, c2_f]
                else:
                    rotations[i] = [c0_f, c1_f, c2_f, largest]
        else:
            # Version 2: xyz components as signed bytes, w is derived
            for i in range(num_points):
                qx = struct.unpack("b", bytes([decompressed[offset]]))[0] / 127.0
                qy = struct.unpack("b", bytes([decompressed[offset + 1]]))[0] / 127.0
                qz = struct.unpack("b", bytes([decompressed[offset + 2]]))[0] / 127.0
                offset += 3

                # Derive w from normalized quaternion constraint
                sum_sq = qx * qx + qy * qy + qz * qz
                qw = np.sqrt(max(0.0, 1.0 - sum_sq))

                rotations[i] = [qw, qx, qy, qz]

        self.progress.emit(95, "Finalizing...")

        return {
            "positions": positions,
            "colors": colors,
            "scales": scales,
            "rotations": rotations,
            "point_count": num_points,
            "crs": self.crs,
            "name": self.url.split("/")[-1].replace(".splat", "").replace(".ply", "").replace(".spz", ""),
        }
