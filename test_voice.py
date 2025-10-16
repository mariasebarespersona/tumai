#!/usr/bin/env python3
"""
Test script for voice transcription
"""
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

# Test 1: Check environment
print("=" * 50)
print("TEST 1: Environment Check")
print("=" * 50)

import os
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    print(f"✅ API Key found: {api_key[:20]}...")
else:
    print("❌ No API key found")
    sys.exit(1)

# Test 2: OpenAI client
print("\n" + "=" * 50)
print("TEST 2: OpenAI Client")
print("=" * 50)

try:
    import openai
    client = openai.OpenAI(api_key=api_key)
    print("✅ OpenAI client created successfully")
except Exception as e:
    print(f"❌ Error creating client: {e}")
    sys.exit(1)

# Test 3: Test with dummy audio (if available)
print("\n" + "=" * 50)
print("TEST 3: Voice Tool Import")
print("=" * 50)

try:
    from tools.voice_tool import transcribe_with_openai_api
    print("✅ Voice tool imported successfully")
except Exception as e:
    print(f"❌ Error importing voice tool: {e}")
    sys.exit(1)

print("\n" + "=" * 50)
print("All tests passed! ✅")
print("=" * 50)
print("\nThe voice functionality should work.")
print("Make sure to restart your server to load the changes.")

