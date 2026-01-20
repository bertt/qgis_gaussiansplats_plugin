"""Spherical Harmonics utilities for Gaussian Splat rendering."""

import numpy as np
from typing import Tuple


# Spherical harmonics constants
SH_C0 = 0.28209479177387814  # 1 / (2 * sqrt(pi))
SH_C1 = 0.4886025119029199   # sqrt(3) / (2 * sqrt(pi))
SH_C2_0 = 1.0925484305920792  # sqrt(15) / (2 * sqrt(pi))
SH_C2_1 = -1.0925484305920792
SH_C2_2 = 0.31539156525252005  # sqrt(5) / (4 * sqrt(pi))
SH_C2_3 = -1.0925484305920792
SH_C2_4 = 0.5462742152960396   # sqrt(15) / (4 * sqrt(pi))

SH_C3_0 = -0.5900435899266435
SH_C3_1 = 2.890611442640554
SH_C3_2 = -0.4570457994644658
SH_C3_3 = 0.3731763325901154
SH_C3_4 = -0.4570457994644658
SH_C3_5 = 1.445305721320277
SH_C3_6 = -0.5900435899266435


def eval_sh_degree_0(sh_coeffs: np.ndarray) -> np.ndarray:
    """Evaluate spherical harmonics degree 0 (DC component).
    
    Args:
        sh_coeffs: Array of SH coefficients [3] (RGB for degree 0)
        
    Returns:
        RGB color values as numpy array [3]
    """
    return SH_C0 * sh_coeffs


def eval_sh_degree_1(sh_coeffs: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Evaluate spherical harmonics up to degree 1.
    
    Args:
        sh_coeffs: Array of SH coefficients [12] (3 RGB × 4 coeffs)
        direction: Normalized viewing direction [3] (x, y, z)
        
    Returns:
        RGB color values as numpy array [3]
    """
    x, y, z = direction
    
    # Degree 0 (DC component) - coefficients 0-2 (RGB)
    result = SH_C0 * sh_coeffs[0:3]
    
    # Degree 1 - coefficients 3-11 (3 RGB × 3 coeffs)
    # f_rest_0, f_rest_1, f_rest_2 correspond to -x, y, -z directions
    result += SH_C1 * (-x * sh_coeffs[3:6])  # -x component
    result += SH_C1 * (y * sh_coeffs[6:9])   # y component
    result += SH_C1 * (-z * sh_coeffs[9:12]) # -z component
    
    return result


def eval_sh_degree_2(sh_coeffs: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Evaluate spherical harmonics up to degree 2.
    
    Args:
        sh_coeffs: Array of SH coefficients [27] (3 RGB × 9 coeffs)
        direction: Normalized viewing direction [3] (x, y, z)
        
    Returns:
        RGB color values as numpy array [3]
    """
    x, y, z = direction
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    
    # Start with degree 0 and 1
    result = eval_sh_degree_1(sh_coeffs[0:12], direction)
    
    # Degree 2 - coefficients 12-26 (3 RGB × 5 coeffs)
    result += SH_C2_0 * xy * sh_coeffs[12:15]
    result += SH_C2_1 * yz * sh_coeffs[15:18]
    result += SH_C2_2 * (2.0 * zz - xx - yy) * sh_coeffs[18:21]
    result += SH_C2_3 * xz * sh_coeffs[21:24]
    result += SH_C2_4 * (xx - yy) * sh_coeffs[24:27]
    
    return result


def eval_sh_degree_3(sh_coeffs: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Evaluate spherical harmonics up to degree 3.
    
    Args:
        sh_coeffs: Array of SH coefficients [48] (3 RGB × 16 coeffs)
        direction: Normalized viewing direction [3] (x, y, z)
        
    Returns:
        RGB color values as numpy array [3]
    """
    x, y, z = direction
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    
    # Start with degree 0, 1, and 2
    result = eval_sh_degree_2(sh_coeffs[0:27], direction)
    
    # Degree 3 - coefficients 27-47 (3 RGB × 7 coeffs)
    result += SH_C3_0 * y * (3.0 * xx - yy) * sh_coeffs[27:30]
    result += SH_C3_1 * xy * z * sh_coeffs[30:33]
    result += SH_C3_2 * y * (4.0 * zz - xx - yy) * sh_coeffs[33:36]
    result += SH_C3_3 * z * (2.0 * zz - 3.0 * xx - 3.0 * yy) * sh_coeffs[36:39]
    result += SH_C3_4 * x * (4.0 * zz - xx - yy) * sh_coeffs[39:42]
    result += SH_C3_5 * z * (xx - yy) * sh_coeffs[42:45]
    result += SH_C3_6 * x * (xx - 3.0 * yy) * sh_coeffs[45:48]
    
    return result


def eval_sh(sh_coeffs: np.ndarray, direction: np.ndarray, sh_degree: int = 3) -> np.ndarray:
    """Evaluate spherical harmonics for a given viewing direction.
    
    Args:
        sh_coeffs: Array of SH coefficients (length depends on degree)
        direction: Normalized viewing direction [3] (x, y, z)
        sh_degree: Degree of spherical harmonics (0-3)
        
    Returns:
        RGB color values as numpy array [3], values in range [0, 1]
    """
    # Normalize direction
    direction = np.array(direction)
    norm = np.linalg.norm(direction)
    if norm > 0:
        direction = direction / norm
    
    # Evaluate based on degree (prioritize explicit parameter over array length)
    if sh_degree == 0:
        result = eval_sh_degree_0(sh_coeffs[0:3])
    elif sh_degree == 1:
        result = eval_sh_degree_1(sh_coeffs[0:12], direction)
    elif sh_degree == 2:
        result = eval_sh_degree_2(sh_coeffs[0:27], direction)
    elif sh_degree == 3:
        result = eval_sh_degree_3(sh_coeffs[0:48], direction)
    else:
        # Fall back to inferring from array length if degree is invalid
        if len(sh_coeffs) <= 3:
            result = eval_sh_degree_0(sh_coeffs[0:3])
        elif len(sh_coeffs) <= 12:
            result = eval_sh_degree_1(sh_coeffs[0:12], direction)
        elif len(sh_coeffs) <= 27:
            result = eval_sh_degree_2(sh_coeffs[0:27], direction)
        else:
            result = eval_sh_degree_3(sh_coeffs[0:48], direction)
    
    # Add 0.5 offset and clamp to [0, 1]
    result = 0.5 + result
    result = np.clip(result, 0.0, 1.0)
    
    return result


def sh_coeffs_to_rgb(sh_coeffs: np.ndarray, sh_degree: int = 0) -> Tuple[int, int, int]:
    """Convert spherical harmonics coefficients to RGB using a default viewing direction.
    
    For degree 0 (DC component only), this is view-independent.
    For higher degrees, uses the default forward direction (0, 0, 1).
    
    Args:
        sh_coeffs: Array of SH coefficients
        sh_degree: Degree of spherical harmonics (0-3)
        
    Returns:
        Tuple of (r, g, b) values in range [0, 255]
    """
    # Use forward direction as default
    default_direction = np.array([0.0, 0.0, 1.0])
    
    # Evaluate SH
    rgb = eval_sh(sh_coeffs, default_direction, sh_degree)
    
    # Convert to 0-255 range
    r = int(np.clip(rgb[0] * 255, 0, 255))
    g = int(np.clip(rgb[1] * 255, 0, 255))
    b = int(np.clip(rgb[2] * 255, 0, 255))
    
    return (r, g, b)


def get_sh_coeffs_count(sh_degree: int) -> int:
    """Get the number of SH coefficients for a given degree.
    
    Args:
        sh_degree: Degree of spherical harmonics (0-3)
        
    Returns:
        Number of RGB coefficients (3 × number of basis functions)
    """
    basis_functions = (sh_degree + 1) ** 2
    return basis_functions * 3  # RGB channels
