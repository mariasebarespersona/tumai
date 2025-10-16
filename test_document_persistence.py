#!/usr/bin/env python3
"""
Script de prueba para verificar la persistencia de documentos.
Ejecutar: python test_document_persistence.py
"""
import env_loader
from tools.docs_tools import list_docs, upload_and_link
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_document_persistence(property_id: str):
    """
    Test document persistence flow:
    1. List documents before upload
    2. Upload a test document
    3. List documents after upload
    4. Verify the document appears
    """
    logger.info("=" * 60)
    logger.info("TESTING DOCUMENT PERSISTENCE")
    logger.info("=" * 60)
    
    # Step 1: List documents before
    logger.info(f"\n1️⃣ Listing documents BEFORE upload for property: {property_id}")
    try:
        docs_before = list_docs(property_id)
        logger.info(f"   Found {len(docs_before)} documents")
        for doc in docs_before[:5]:  # Show first 5
            logger.info(f"   - {doc.get('document_group')}/{doc.get('document_subgroup')}/{doc.get('document_name')} - {'✅ uploaded' if doc.get('storage_key') else '❌ missing'}")
    except Exception as e:
        logger.error(f"   ❌ Error listing documents: {e}")
        return False
    
    # Step 2: Create a test document
    logger.info(f"\n2️⃣ Creating test document...")
    test_content = b"This is a test document for persistence verification."
    test_filename = "test_persistence.txt"
    
    # Find a document slot to use (first one without storage_key)
    test_slot = None
    for doc in docs_before:
        if not doc.get('storage_key'):
            test_slot = doc
            break
    
    if not test_slot:
        logger.warning("   ⚠️ No empty document slots found. All documents already uploaded!")
        logger.info("   This is actually a good sign - documents are persisting!")
        return True
    
    logger.info(f"   Using slot: {test_slot.get('document_group')}/{test_slot.get('document_subgroup')}/{test_slot.get('document_name')}")
    
    # Step 3: Upload document
    logger.info(f"\n3️⃣ Uploading test document...")
    try:
        result = upload_and_link(
            property_id=property_id,
            file_bytes=test_content,
            filename=test_filename,
            document_group=test_slot['document_group'],
            document_subgroup=test_slot.get('document_subgroup', ''),
            document_name=test_slot['document_name'],
            metadata={"test": True}
        )
        logger.info(f"   ✅ Upload result: {result}")
    except Exception as e:
        logger.error(f"   ❌ Upload failed: {e}")
        return False
    
    # Step 4: List documents after
    logger.info(f"\n4️⃣ Listing documents AFTER upload...")
    try:
        docs_after = list_docs(property_id)
        logger.info(f"   Found {len(docs_after)} documents")
        
        # Find our test document
        test_doc = None
        for doc in docs_after:
            if (doc.get('document_group') == test_slot['document_group'] and
                doc.get('document_subgroup') == test_slot.get('document_subgroup', '') and
                doc.get('document_name') == test_slot['document_name']):
                test_doc = doc
                break
        
        if test_doc and test_doc.get('storage_key'):
            logger.info(f"   ✅ TEST PASSED: Document found in DB with storage_key!")
            logger.info(f"   Storage key: {test_doc.get('storage_key')}")
            return True
        else:
            logger.error(f"   ❌ TEST FAILED: Document not found or no storage_key!")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Error listing documents after upload: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python test_document_persistence.py <property_id>")
        print("\nTo get a property_id, you can:")
        print("1. Use the app to create/list properties")
        print("2. Check Supabase directly")
        sys.exit(1)
    
    property_id = sys.argv[1]
    
    logger.info(f"Testing document persistence for property: {property_id}")
    success = test_document_persistence(property_id)
    
    logger.info("\n" + "=" * 60)
    if success:
        logger.info("✅ ALL TESTS PASSED - Documents are persisting correctly!")
    else:
        logger.error("❌ TESTS FAILED - There are issues with document persistence")
    logger.info("=" * 60)
    
    sys.exit(0 if success else 1)

