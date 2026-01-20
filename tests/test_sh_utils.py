"""Tests for spherical harmonics utilities."""

import sys
import numpy as np
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sh_utils import (
    eval_sh,
    eval_sh_degree_0,
    eval_sh_degree_1,
    eval_sh_degree_2,
    eval_sh_degree_3,
    sh_coeffs_to_rgb,
    get_sh_coeffs_count,
    SH_C0,
)


def test_get_sh_coeffs_count():
    """Test SH coefficient count calculation."""
    assert get_sh_coeffs_count(0) == 3, "Degree 0 should have 3 coefficients (RGB)"
    assert get_sh_coeffs_count(1) == 12, "Degree 1 should have 12 coefficients"
    assert get_sh_coeffs_count(2) == 27, "Degree 2 should have 27 coefficients"
    assert get_sh_coeffs_count(3) == 48, "Degree 3 should have 48 coefficients"
    print("✓ test_get_sh_coeffs_count passed")


def test_eval_sh_degree_0():
    """Test degree 0 (DC component) evaluation."""
    # Test with simple DC coefficients
    sh_coeffs = np.array([1.0, 0.5, 0.0], dtype=np.float32)  # RGB
    result = eval_sh_degree_0(sh_coeffs)
    
    # Result should be SH_C0 * coefficients
    expected = SH_C0 * sh_coeffs
    assert np.allclose(result, expected), f"Expected {expected}, got {result}"
    print("✓ test_eval_sh_degree_0 passed")


def test_eval_sh_degree_1():
    """Test degree 1 evaluation."""
    # Create test coefficients (12 total: 3 RGB × 4 basis functions)
    sh_coeffs = np.array([
        1.0, 0.5, 0.0,  # DC (degree 0)
        0.1, 0.2, 0.3,  # -x component
        0.4, 0.5, 0.6,  # y component
        0.7, 0.8, 0.9,  # -z component
    ], dtype=np.float32)
    
    # Test with forward direction (0, 0, 1)
    direction = np.array([0.0, 0.0, 1.0])
    result = eval_sh_degree_1(sh_coeffs, direction)
    
    # Result should be a 3-element array (RGB)
    assert result.shape == (3,), f"Expected shape (3,), got {result.shape}"
    assert np.all(result >= -2.0) and np.all(result <= 2.0), "Values should be in reasonable range"
    print("✓ test_eval_sh_degree_1 passed")


def test_eval_sh_with_clipping():
    """Test that eval_sh properly clips values to [0, 1]."""
    # Create coefficients that would produce out-of-range values
    sh_coeffs = np.array([10.0, -10.0, 5.0], dtype=np.float32)  # DC only
    direction = np.array([0.0, 0.0, 1.0])
    
    result = eval_sh(sh_coeffs, direction, sh_degree=0)
    
    # Check that all values are clipped to [0, 1]
    assert np.all(result >= 0.0) and np.all(result <= 1.0), f"Values should be clipped to [0, 1], got {result}"
    print("✓ test_eval_sh_with_clipping passed")


def test_sh_coeffs_to_rgb():
    """Test conversion of SH coefficients to RGB."""
    # Test with DC component only
    sh_coeffs = np.array([1.0, 0.5, 0.0], dtype=np.float32)
    r, g, b = sh_coeffs_to_rgb(sh_coeffs, sh_degree=0)
    
    # Check that values are in [0, 255] range
    assert 0 <= r <= 255, f"Red value {r} out of range"
    assert 0 <= g <= 255, f"Green value {g} out of range"
    assert 0 <= b <= 255, f"Blue value {b} out of range"
    print("✓ test_sh_coeffs_to_rgb passed")


def test_direction_normalization():
    """Test that directions are properly normalized."""
    # Create unnormalized direction
    direction = np.array([2.0, 2.0, 2.0])
    sh_coeffs = np.array([1.0, 0.5, 0.0], dtype=np.float32)
    
    # eval_sh should normalize the direction internally
    result = eval_sh(sh_coeffs, direction, sh_degree=0)
    
    # Should not raise an error and should produce valid results
    assert result.shape == (3,), "Should return 3-element RGB array"
    assert np.all(result >= 0.0) and np.all(result <= 1.0), "Values should be in [0, 1]"
    print("✓ test_direction_normalization passed")


def test_multiple_degrees():
    """Test evaluation with different SH degrees."""
    directions = [
        np.array([1.0, 0.0, 0.0]),  # right
        np.array([0.0, 1.0, 0.0]),  # up
        np.array([0.0, 0.0, 1.0]),  # forward
        np.array([-1.0, 0.0, 0.0]), # left
    ]
    
    # Create degree 3 coefficients (48 total) with fixed seed for determinism
    np.random.seed(42)
    sh_coeffs = np.random.randn(48).astype(np.float32) * 0.5
    
    for direction in directions:
        for degree in [0, 1, 2, 3]:
            result = eval_sh(sh_coeffs[:get_sh_coeffs_count(degree)], direction, sh_degree=degree)
            assert result.shape == (3,), f"Degree {degree} should return RGB"
            assert np.all(result >= 0.0) and np.all(result <= 1.0), f"Degree {degree} values should be in [0, 1]"
    
    print("✓ test_multiple_degrees passed")


def run_all_tests():
    """Run all tests."""
    print("\nRunning spherical harmonics tests...\n")
    
    test_get_sh_coeffs_count()
    test_eval_sh_degree_0()
    test_eval_sh_degree_1()
    test_eval_sh_with_clipping()
    test_sh_coeffs_to_rgb()
    test_direction_normalization()
    test_multiple_degrees()
    
    print("\n✅ All tests passed!\n")


if __name__ == "__main__":
    run_all_tests()
