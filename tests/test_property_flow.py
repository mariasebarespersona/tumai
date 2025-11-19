"""
Integration tests for Property management flow.

Tests the complete flow:
1. Create property
2. List properties
3. Switch property
4. Delete property
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from tools.property_tools import (
    add_property,
    list_properties,
    find_property,
    get_property,
    delete_property
)


class TestPropertyFlow:
    """Test property creation and management flow."""
    
    def test_add_property_returns_dict(self):
        """Test that add_property returns a property dict with id."""
        # Create a test property
        result = add_property(
            name="Test Property Flow",
            address="123 Test St"
        )
        
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "id" in result, "Property should have an id"
        assert "name" in result, "Property should have a name"
        assert result["name"] == "Test Property Flow"
        
        # Cleanup: delete the test property
        try:
            delete_property(result["id"])
        except:
            pass  # Ignore cleanup errors
    
    def test_list_properties_returns_list(self):
        """Test that list_properties returns a list."""
        result = list_properties()
        
        assert isinstance(result, list), f"Expected list, got {type(result)}"
    
    def test_find_property_by_name(self):
        """Test finding a property by name."""
        # Create a test property
        test_prop = add_property(
            name="Test Find Property",
            address="456 Find St"
        )
        
        try:
            # Find it by name
            result = find_property("Test Find Property")
            
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            assert "matches" in result, "Result should have matches"
            
            if result.get("matches"):
                assert len(result["matches"]) > 0, "Should find at least one match"
                found = result["matches"][0]
                assert found["name"] == "Test Find Property"
        finally:
            # Cleanup
            try:
                delete_property(test_prop["id"])
            except:
                pass
    
    def test_get_property_by_id(self):
        """Test getting a specific property by ID."""
        # Create a test property
        test_prop = add_property(
            name="Test Get Property",
            address="789 Get St"
        )
        
        try:
            # Get it by ID
            result = get_property(test_prop["id"])
            
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            assert result["id"] == test_prop["id"]
            assert result["name"] == "Test Get Property"
        finally:
            # Cleanup
            try:
                delete_property(test_prop["id"])
            except:
                pass
    
    def test_delete_property(self):
        """Test deleting a property."""
        # Create a test property
        test_prop = add_property(
            name="Test Delete Property",
            address="999 Delete St"
        )
        
        # Delete it
        result = delete_property(test_prop["id"])
        
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "success" in result or "deleted" in str(result).lower()
        
        # Verify it's deleted by trying to get it
        deleted_prop = get_property(test_prop["id"])
        assert deleted_prop is None or deleted_prop.get("id") != test_prop["id"]


class TestPropertyValidation:
    """Test property validation logic."""
    
    def test_property_requires_name(self):
        """Test that property creation requires a name."""
        # This test assumes add_property validates inputs
        with pytest.raises(Exception):
            add_property(name="", address="Test")
    
    def test_property_name_uniqueness(self):
        """Test that property names should be unique (if enforced)."""
        # Create first property
        prop1 = add_property(name="Unique Test Prop", address="111 Test")
        
        try:
            # Try to create duplicate (this may or may not fail depending on DB constraints)
            prop2 = add_property(name="Unique Test Prop", address="222 Test")
            
            # If duplicates are allowed, clean up both
            try:
                delete_property(prop2["id"])
            except:
                pass
        finally:
            # Cleanup
            try:
                delete_property(prop1["id"])
            except:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

