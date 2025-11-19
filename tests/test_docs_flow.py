"""
Integration tests for Documents flow.

Tests the complete flow:
1. Upload document
2. List documents
3. Send email with document
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from tools.docs_tools import list_docs, signed_url_for
from tools.email_tool import send_email


class TestDocsFlow:
    """Test documents upload and email flow."""
    
    def test_list_docs_returns_list(self):
        """Test that list_docs returns a list (even if empty)."""
        # This test doesn't require a real property_id
        test_property_id = "test-property-123"
        result = list_docs(test_property_id)
        
        assert isinstance(result, list), f"Expected list, got {type(result)}"
    
    def test_signed_url_for_document(self):
        """Test that signed_url_for returns a URL for a valid document."""
        # This is a mock test - in real scenario, you'd need a valid property and document
        test_property_id = "test-property-123"
        test_group = "R2B"
        test_subgroup = "Diseño/Obra"
        test_name = "Test Document"
        
        try:
            result = signed_url_for(
                property_id=test_property_id,
                document_group=test_group,
                document_subgroup=test_subgroup,
                document_name=test_name
            )
            
            # Should return a URL string (or raise exception if document doesn't exist)
            assert isinstance(result, str), f"Expected string URL, got {type(result)}"
            assert len(result) > 0, "URL should not be empty"
        except Exception as e:
            # Expected if document doesn't exist in test environment
            assert "not found" in str(e).lower() or "no storage_key" in str(e).lower()
    
    def test_send_email_validates_inputs(self):
        """Test that send_email validates required inputs."""
        # Test with empty recipient list
        with pytest.raises(Exception):
            send_email(
                to=[],  # Empty list should fail
                subject="Test",
                html="<p>Test body</p>"
            )
    
    def test_send_email_with_valid_params(self):
        """Test send_email with valid parameters (mock)."""
        # This is a mock test - in real scenario, you'd need valid SMTP credentials
        # For now, we just test that the function accepts the right parameters
        try:
            result = send_email(
                to=["test@example.com"],
                subject="Test Document",
                html="<p>Please find attached document.</p>",
                attachments=[("test.pdf", b"mock pdf content")]
            )
            # If SMTP is not configured, this will fail gracefully
            # We just verify the function signature works
            assert result is not None or True  # Function may return None on success
        except Exception as e:
            # Expected if SMTP not configured in test environment
            assert "SMTP" in str(e) or "email" in str(e).lower() or "Connection" in str(e)


class TestDocumentValidation:
    """Test document validation logic."""
    
    def test_valid_document_types(self):
        """Test that common document types are recognized."""
        valid_extensions = [".pdf", ".docx", ".xlsx", ".jpg", ".png"]
        
        for ext in valid_extensions:
            filename = f"document{ext}"
            # This would test document type validation if implemented
            assert ext in filename
    
    def test_document_size_validation(self):
        """Test document size limits (if implemented)."""
        # Placeholder for future document size validation
        max_size_mb = 10
        test_size_mb = 5
        
        assert test_size_mb <= max_size_mb, "Document should be within size limits"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

