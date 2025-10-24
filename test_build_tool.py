#!/usr/bin/env python3
"""Test the build_summary_ppt_tool directly"""
import env_loader
import traceback
from tools.property_tools import search_properties

# Find Casa Demo 11
results = search_properties("Casa Demo 11", limit=1)
if not results:
    print("❌ No se encontró Casa Demo 11")
    exit(1)

prop = results[0]
prop_id = prop.get("id")
prop_name = prop.get("name")
address = prop.get("address", "")

print(f"✅ Propiedad: {prop_name}")
print(f"   ID: {prop_id}")
print(f"   Dirección: {address}")

# Test the tool directly
print(f"\n🧪 Testing build_summary_ppt_tool...\n")

try:
    from tools.registry import build_summary_ppt_tool
    
    result = build_summary_ppt_tool.invoke({
        "property_id": prop_id,
        "property_name": prop_name,
        "address": address,
        "format": "pdf"
    })
    
    print(f"\n✅ Tool executed successfully!")
    print(f"   Result keys: {result.keys()}")
    
    if "signed_url" in result:
        print(f"   ✅ Signed URL: {result['signed_url'][:80]}...")
        print(f"   📄 Filename: {result['filename']}")
        print(f"   📦 Size: {result.get('size_bytes', 'unknown')} bytes")
    elif "bytes_b64" in result:
        print(f"   ⚠️  Fallback mode (bytes_b64)")
        print(f"   📄 Filename: {result['filename']}")
        if "error" in result:
            print(f"   ❌ Error: {result['error']}")
    else:
        print(f"   ⚠️  Unexpected result format")
        print(f"   {result}")
    
except Exception as e:
    print(f"\n❌ ERROR:")
    print(f"   Type: {type(e).__name__}")
    print(f"   Message: {str(e)}")
    print(f"\n📋 Traceback:")
    traceback.print_exc()

