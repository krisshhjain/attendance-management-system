#!/usr/bin/env python3
"""Test the specific write intent failure with detailed error logging."""

import os
import sys
import json
import traceback

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from hr_copilot.services.llm import get_structured_intent


def test_write_intent_with_tracing():
    """Test the specific failing write intent with detailed tracing."""
    
    print("TESTING WRITE INTENT: Make Akshat Bansal Absent for 24th September 2026")
    print("=" * 70)
    
    query = "Make Akshat Bansal Absent for 24th September 2026"
    session_id = "debug_write_test"
    
    try:
        print("Step 1: Calling get_structured_intent...")
        result = get_structured_intent(query, session_id=session_id)
        
        print("SUCCESS: Write intent processed successfully!")
        print("Result:")
        print(json.dumps(result, indent=2, default=str))
        
        print("\nThis means the write intent is actually WORKING now!")
        print("The issue may have been fixed by the recent changes.")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Write intent failed with {type(e).__name__}: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        
        # Try to identify the specific failure point
        if "local Qwen intent service is unavailable" in str(e):
            print("\nFAILURE ANALYSIS:")
            print("- Error is coming from hr_copilot/services/llm.py lines 80 or 114")
            print("- This means either:")
            print("  1. get_llm_provider() is throwing LLMProviderError (line 80)")
            print("  2. provider.structured_output() is throwing LLMProviderError (line 114)")
            print("- But our previous tests show the provider is working perfectly!")
            print("- This suggests a timing/concurrency issue or context-specific failure")
        
        return False


def test_provider_isolation():
    """Test the provider in isolation to confirm it's working."""
    
    print("\nTESTING PROVIDER IN ISOLATION")
    print("=" * 40)
    
    try:
        from hr_copilot.services.providers import get_llm_provider
        
        provider = get_llm_provider()
        print(f"Provider: {provider}")
        
        if provider:
            # Test the exact structured output call that's failing
            messages = [
                {
                    "role": "system", 
                    "content": "Extract HR semantic intent as JSON. Focus on WHAT the user wants, not backend implementation.\nIntents: attendance_lookup, attendance_update, employee_lookup, leave_lookup, leave_create, absence_lookup\nExtract: intent, employee_name, temporal_expression, target_status (for updates)\nWrite operations: 'mark as', 'set to', 'make', 'put on', 'create', 'update', 'change'\nRead operations: 'who was', 'show', 'list', 'when did', 'how many'\nStatus values: 'absent', 'present', 'incomplete'"
                },
                {"role": "user", "content": "Make Akshat Bansal Absent for 24th September 2026"}
            ]
            
            from hr_copilot.services.llm import INTENT_SCHEMA
            
            result = provider.structured_output(
                messages, 
                schema=INTENT_SCHEMA, 
                options={"num_predict": 64, "temperature": 0}
            )
            
            print("SUCCESS: Provider structured_output works directly")
            print("Result:", json.dumps(result, indent=2))
            
        else:
            print("ERROR: Provider is None")
            
    except Exception as e:
        print(f"ERROR: Provider test failed - {type(e).__name__}: {e}")
        traceback.print_exc()


if __name__ == '__main__':
    # Test the provider directly first
    test_provider_isolation()
    
    print("\n" + "="*70)
    
    # Test the full write intent path
    success = test_write_intent_with_tracing()
    
    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    
    if success:
        print("The write intent is WORKING! The issue may have been resolved.")
        print("Try the actual HR Copilot request again in the frontend.")
    else:
        print("The write intent is still failing.")
        print("Need to add more detailed logging to identify the exact failure point.")