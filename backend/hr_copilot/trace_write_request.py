#!/usr/bin/env python3
"""Trace the complete write request path to identify the failure point."""

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

from django.contrib.auth import get_user_model
from hr_copilot.services.pipeline import analyze_question, derive_scope
from hr_copilot.services.conversation import load_context, apply_context
from hr_copilot.services.write_actions import write_action_planner
from hr_copilot.services.write_executor import pending_action_manager

User = get_user_model()


def trace_write_request():
    """Trace the complete write request path step by step."""
    
    print("=== TRACING WRITE REQUEST PATH ===")
    print("Query: Make Akshat Bansal as Absent for 24th September 2026")
    print()
    
    # Test query
    question = "Make Akshat Bansal as Absent for 24th September 2026"
    session_id = "trace_session_2026"
    conversation_id = None
    
    # Step 1: Get or create a test user (System Admin)
    print("Step 1: User Authentication & Authorization")
    try:
        # Try to get an existing superuser
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            print("  ERROR: No superuser found in database")
            return
        
        print(f"  SUCCESS: Using user {user.username} (superuser: {user.is_superuser})")
    except Exception as e:
        print(f"  ERROR: User lookup failed - {e}")
        return
    
    # Step 2: Load context
    print("\nStep 2: Load Context")
    try:
        context = load_context(user, conversation_id)
        print(f"  SUCCESS: Context loaded - {context}")
    except Exception as e:
        print(f"  ERROR: Context loading failed - {e}")
        traceback.print_exc()
        return
    
    # Step 3: Analyze question (Qwen + normalization)
    print("\nStep 3: Analyze Question (Qwen + Normalization)")
    try:
        intent = analyze_question(question, context, session_id=session_id)
        print(f"  SUCCESS: Intent analyzed")
        print(f"    Intent: {intent.get('intent')}")
        print(f"    Source: {intent.get('source')}")
        print(f"    Action type: {intent.get('action_type')}")
        print(f"    Requires approval: {intent.get('requires_approval')}")
        print(f"    Entities: {intent.get('entities', {})}")
    except Exception as e:
        print(f"  ERROR: Question analysis failed - {e}")
        traceback.print_exc()
        return
    
    # Step 4: Apply context
    print("\nStep 4: Apply Context")
    try:
        intent = apply_context(question, intent, context)
        print(f"  SUCCESS: Context applied")
    except Exception as e:
        print(f"  ERROR: Context application failed - {e}")
        traceback.print_exc()
        return
    
    # Step 5: Derive scope
    print("\nStep 5: Derive User Scope")
    try:
        scope = derive_scope(user)
        print(f"  SUCCESS: Scope derived")
        print(f"    Unrestricted: {scope.get('unrestricted')}")
        print(f"    Sections: {scope.get('sections')}")
        print(f"    Subsections: {scope.get('subsections')}")
    except Exception as e:
        print(f"  ERROR: Scope derivation failed - {e}")
        traceback.print_exc()
        return
    
    # Step 6: Check if write action
    print("\nStep 6: Write Action Check")
    is_write = intent.get('action_type') == 'write' and intent.get('requires_approval')
    print(f"  Is write action: {is_write}")
    print(f"  Action type: {intent.get('action_type')}")
    print(f"  Requires approval: {intent.get('requires_approval')}")
    
    if not is_write:
        print("  ERROR: Intent not recognized as write action requiring approval")
        return
    
    # Step 7: Plan write action
    print("\nStep 7: Plan Write Action")
    try:
        # Add original query for fallback processing
        intent['original_query'] = question
        
        pending_action = write_action_planner.plan_write_action(intent, user, session_id)
        print(f"  SUCCESS: Write action planned")
        print(f"    Action ID: {pending_action.get('action_id')}")
        print(f"    Action type: {pending_action.get('action_type')}")
        print(f"    Description: {pending_action.get('description')}")
        print(f"    Target data: {pending_action.get('target_data')}")
    except Exception as e:
        print(f"  ERROR: Write action planning failed - {e}")
        traceback.print_exc()
        return
    
    # Step 8: Store pending action
    print("\nStep 8: Store Pending Action")
    try:
        action_id = pending_action_manager.store_pending_action(session_id, pending_action)
        print(f"  SUCCESS: Pending action stored with ID: {action_id}")
    except Exception as e:
        print(f"  ERROR: Pending action storage failed - {e}")
        traceback.print_exc()
        return
    
    print("\n=== TRACE COMPLETED SUCCESSFULLY ===")
    print("All steps passed. The write request should work.")
    print("If the frontend still shows generic failure, the issue is in:")
    print("1. Frontend communication")
    print("2. Response serialization")
    print("3. Session/authentication in the actual request")


def test_qwen_direct():
    """Test Qwen model output directly."""
    print("\n=== TESTING QWEN MODEL DIRECTLY ===")
    
    try:
        from hr_copilot.services.llm import get_structured_intent
        
        query = "Make Akshat Bansal as Absent for 24th September 2026"
        print(f"Query: {query}")
        
        result = get_structured_intent(query, session_id="direct_test")
        print("Qwen output:")
        print(json.dumps(result, indent=2, default=str))
        
    except Exception as e:
        print(f"ERROR: Qwen direct test failed - {e}")
        traceback.print_exc()


if __name__ == '__main__':
    try:
        trace_write_request()
        test_qwen_direct()
    except KeyboardInterrupt:
        print("\nTrace interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error in trace: {e}")
        traceback.print_exc()