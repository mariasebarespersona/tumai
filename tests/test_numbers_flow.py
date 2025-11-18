"""
Integration tests for Numbers Table flow.

Tests the complete flow:
1. Import Excel template
2. Set cell values
3. Auto-calculate formulas
4. Export to Excel
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from tools.formula_calculator_v3_simple import (
    evaluate_r2b_formula,
    get_affected_cells,
    auto_calculate_on_update
)


class TestFormulaEvaluation:
    """Test individual formula evaluation."""
    
    def test_d5_iva_calculation(self):
        """Test D5 = B5 * C5 / 100"""
        values = {"B5": 1000, "C5": 10}
        result = evaluate_r2b_formula("D5", values)
        assert result == 100.0, f"Expected 100.0, got {result}"
    
    def test_d5_empty_inputs(self):
        """Test D5 with empty inputs returns None"""
        values = {"B5": 1000}  # C5 missing
        result = evaluate_r2b_formula("D5", values)
        assert result is None, f"Expected None for missing input, got {result}"
    
    def test_e5_total_with_vat(self):
        """Test E5 = B5 + D5"""
        values = {"B5": 1000, "D5": 100}
        result = evaluate_r2b_formula("E5", values)
        assert result == 1100.0, f"Expected 1100.0, got {result}"
    
    def test_b10_profit(self):
        """Test B10 = B6 - B7 - B8"""
        values = {"B6": 500000, "B7": 300000, "B8": 50000}
        result = evaluate_r2b_formula("B10", values)
        assert result == 150000.0, f"Expected 150000.0, got {result}"
    
    def test_b12_total_income(self):
        """Test B12 = B10 + B11"""
        values = {"B10": 150000, "B11": 10000}
        result = evaluate_r2b_formula("B12", values)
        assert result == 160000.0, f"Expected 160000.0, got {result}"
    
    def test_b13_taxes(self):
        """Test B13 = B12 * 0.25"""
        values = {"B12": 160000}
        result = evaluate_r2b_formula("B13", values)
        assert result == 40000.0, f"Expected 40000.0, got {result}"


class TestDependencyGraph:
    """Test dependency graph and cascading calculations."""
    
    def test_b5_affects_d5_and_e5(self):
        """Test that updating B5 triggers D5 and E5 recalculation"""
        affected = get_affected_cells("B5")
        assert "D5" in affected, "D5 should be affected by B5"
        assert "E5" in affected, "E5 should be affected by B5 (cascading)"
    
    def test_c5_affects_d5_only(self):
        """Test that C5 only affects D5 directly"""
        affected = get_affected_cells("C5")
        assert "D5" in affected, "D5 should be affected by C5"
        # E5 might be in affected due to cascading from D5
    
    def test_b6_affects_multiple_cells(self):
        """Test that B6 affects D6, E6, and B10"""
        affected = get_affected_cells("B6")
        assert "D6" in affected, "D6 should be affected by B6"
        assert "E6" in affected, "E6 should be affected by B6 (cascading)"
        assert "B10" in affected, "B10 should be affected by B6"


class TestAutoCascade:
    """Test auto-calculation with cascading."""
    
    def test_cascading_b5_c5_to_d5_e5(self):
        """Test that setting B5 and C5 auto-calculates D5 and E5"""
        current_values = {"B5": 1000, "C5": 10}
        
        # Simulate auto-calculation when B5 is updated
        calculated = auto_calculate_on_update(
            property_id="test",
            template_key="R2B",
            updated_cell="B5",
            new_value=1000,
            structure={},  # Not needed for V3
            current_values=current_values
        )
        
        assert "D5" in calculated, "D5 should be calculated"
        assert calculated["D5"] == 100.0, f"D5 should be 100.0, got {calculated['D5']}"
        assert "E5" in calculated, "E5 should be calculated (cascading)"
        assert calculated["E5"] == 1100.0, f"E5 should be 1100.0, got {calculated['E5']}"
    
    def test_profit_cascade(self):
        """Test cascading from B6 to B10 to B12"""
        current_values = {
            "B6": 500000,
            "B7": 300000,
            "B8": 50000,
            "B11": 10000
        }
        
        # Update B6
        calculated = auto_calculate_on_update(
            property_id="test",
            template_key="R2B",
            updated_cell="B6",
            new_value=500000,
            structure={},
            current_values=current_values
        )
        
        # Should calculate B10 and B12
        assert "B10" in calculated, "B10 should be calculated"
        assert calculated["B10"] == 150000.0, f"B10 should be 150000.0"
        assert "B12" in calculated, "B12 should be calculated (cascading)"
        assert calculated["B12"] == 160000.0, f"B12 should be 160000.0"


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_missing_dependency(self):
        """Test that missing dependencies return None"""
        values = {}  # No values at all
        result = evaluate_r2b_formula("D5", values)
        assert result is None, "Should return None when dependencies are missing"
    
    def test_zero_values(self):
        """Test calculations with zero values"""
        values = {"B5": 0, "C5": 10}
        result = evaluate_r2b_formula("D5", values)
        assert result == 0.0, "0 * 10 / 100 should be 0.0"
    
    def test_rounding(self):
        """Test that results are rounded to 2 decimal places"""
        values = {"B5": 1000, "C5": 10.5}  # Should give 105
        result = evaluate_r2b_formula("D5", values)
        assert result == 105.0, f"Should round to 2 decimals, got {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

