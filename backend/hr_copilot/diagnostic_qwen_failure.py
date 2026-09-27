#!/usr/bin/env python3
"""Comprehensive diagnostic to trace the exact Qwen intent service failure."""

import os
import sys
import json
import traceback
from datetime import datetime

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from hr_copilot.services.llm import get_structured_intent
from hr_copilot.services.providers import get_llm_provider, LLMProviderError


def test_provider_directly():
    """Test the LLM provider directly without the full intent pipeline."""
    print("=== TESTING LLM PROVIDER DIRECTLY ===")
    
    try:
        print("1. Getting LLM provider...")
        provider = get_llm_provider()
        
        if provider is None:
            print("  ERROR: get_llm_provider() returned None")
            print("  Check HR_COPILOT_LLM_PROVIDER and HR_COPILOT_LLM_URL environment variables")
            return False
        
        print(f"  SUCCESS: Provider available - {type(provider).__name__}")
        print(f"    Model: {provider.model}")
        print(f"    Base URL: {provider.base_url}")
        print(f"    Timeout: {provider.timeout_seconds} seconds")
        
        # Test provider health
        print("\n2. Testing provider health...")
        health = provider.health()
        print(f"  Health: {health.as_dict()}")
        
        if not health.available:
            print(f"  ERROR: Provider not available - {health.detail}")
            return False
        
        # Test simple chat request
        print("\n3. Testing simple chat request...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello"}
        ]
        
        try:
            response = provider.chat(messages, options={"num_predict": 10})
            print(f"  SUCCESS: Chat response - {response[:100]}...")
        except Exception as e:
            print(f"  ERROR: Chat failed - {type(e).__name__}: {e}")
            return False
        
        # Test structured output (the failing method)
        print("\n4. Testing structured output...")
        intent_messages = [
            {
                "role": "system", 
                "content": "Extract HR intent as JSON. Return: {\"intent\": \"attendance_update\", \"employee_name\": \"Test User\"}"
            },
            {"role": "user", "content": "Make Test User absent today"}
        ]
        
        try:
            schema = {"type": "object", "properties": {"intent": {"type": "string"}, "employee_name": {"type": "string"}}}
            structured_response = provider.structured_output(intent_messages, schema=schema, options={"num_predict": 64, "temperature": 0})
            print(f"  SUCCESS: Structured output - {structured_response}")
            return True
        except Exception as e:
            print(f"  ERROR: Structured output failed - {type(e).__name__}: {e}")
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"  ERROR: Provider test failed - {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


def test_read_vs_write_intents():
    """Test read vs write intent processing to identify differences."""
    print("\n=== COMPARING READ VS WRITE INTENT PROCESSING ===")
    
    test_cases = [
        {
            "type": "read",
            "query": "Show me today's attendance summary", 
            "expected_working": True
        },
        {
            "type": "write", 
            "query": "Make Akshat Bansal Absent for 24th September 2026",
            "expected_working": False  # This is the failing case
        }
    ]
    
    for case in test_cases:
        print(f"\nTesting {case['type'].upper()} intent: {case['query']}")
        print("-" * 60)
        
        try:
            result = get_structured_intent(case['query'], session_id=f"test_{case['type']}")
            
            print(f"  SUCCESS: Intent processed")
            print(f"    Intent: {result.get('intent')}")
            print(f"    Source: {result.get('source')}")
            print(f"    Action type: {result.get('action_type')}")
            print(f"    Requires approval: {result.get('requires_approval')}")
            
            if case['expected_working']:
                print(f"  ✓ EXPECTED: {case['type']} intent worked as expected")
            else:
                print(f"  ? UNEXPECTED: {case['type']} intent worked (was expected to fail)")
                
        except Exception as e:
            print(f"  ERROR: Intent processing failed - {type(e).__name__}: {e}")
            
            if case['expected_working']:
                print(f"  ✗ UNEXPECTED: {case['type']} intent failed (was expected to work)")
            else:
                print(f"  ✓ EXPECTED: {case['type']} intent failed as reported")
            
            # Print detailed error for the failing write case
            if case['type'] == 'write':
                print("\n  DETAILED ERROR TRACE:")
                traceback.print_exc()


def test_intent_schema():
    """Test the intent schema used for structured output."""
    print("\n=== TESTING INTENT SCHEMA ===")
    
    from hr_copilot.services.llm import INTENT_SCHEMA
    
    print("Current INTENT_SCHEMA:")
    print(json.dumps(INTENT_SCHEMA, indent=2))
    
    # Test if schema is valid
    try:
        import jsonschema
        jsonschema.Draft7Validator.check_schema(INTENT_SCHEMA)
        print("\n  SUCCESS: Schema is valid JSON Schema")
    except ImportError:
        print("\n  WARNING: jsonschema not available, cannot validate schema")
    except Exception as e:
        print(f"\n  ERROR: Schema validation failed - {e}")


def test_environment_config():
    """Test environment configuration that might affect the provider."""
    print("\n=== TESTING ENVIRONMENT CONFIGURATION ===")
    
    env_vars = [
        "HR_COPILOT_LLM_PROVIDER",
        "HR_COPILOT_LLM_URL", 
        "HR_COPILOT_LLM_MODEL",
        "HR_COPILOT_LLM_TIMEOUT_SECONDS",
        "HR_COPILOT_LLM_TEMPERATURE"
    ]
    
    print("Environment variables:")
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            print(f"  {var} = {value}")
        else:
            print(f"  {var} = (not set)")
    
    # Check defaults
    print("\nProvider defaults:")
    print(f"  DEFAULT_OLLAMA_URL = http://127.0.0.1:11434")
    print(f"  DEFAULT_MODEL = qwen3-8b-q4km-local")


def main():
    """Run comprehensive diagnostic."""
    print("HR COPILOT QWEN INTENT SERVICE DIAGNOSTIC")
    print("=" * 60)
    print(f"Time: {datetime.now().isoformat()}")
    print()
    
    # Test environment
    test_environment_config()
    
    # Test provider directly
    provider_ok = test_provider_directly()
    
    # Test schema
    test_intent_schema()
    
    # Test read vs write
    test_read_vs_write_intents()
    
    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    if provider_ok:
        print("✓ LLM Provider is working correctly")
        print("✓ Ollama connection successful")
        print("✓ Structured output method functional")
        print()
        print("CONCLUSION: The issue is likely in:")
        print("1. Intent schema validation")
        print("2. Intent normalization layer")
        print("3. Specific request differences between read/write")
        print("4. Session/context handling differences")
    else:
        print("✗ LLM Provider has fundamental issues")
        print("✗ Need to fix provider/Ollama integration first")
    
    print("\nNext steps:")
    print("1. Check Django logs for the actual exception details")
    print("2. Compare working read path vs failing write path")
    print("3. Add detailed error logging to identify exact failure point")


if __name__ == '__main__':
    main()