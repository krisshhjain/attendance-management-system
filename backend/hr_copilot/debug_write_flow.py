#!/usr/bin/env python3
"""Debug the write action flow to see where it's failing."""

import os
import sys

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from hr_copilot.services.pipeline import analyze_question, derive_scope
from hr_copilot.services.conversation import load_context, apply_context
from django.contrib.auth import get_user_model

User = get_user_model()

def debug_write_action_flow():
    """Debug the exact flow for write actions."""
    
    print("=== DEBUGGING WRITE ACTION FLOW ===")
    
    query = "Make Akshat Bansal Absent for 24th September 2026"
    session_id = "debug_session"
    
    # Get superuser
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        print("ERROR: No superuser found")
        return
    
    print(f"Query: {query}")
    print(f"User: {user.username} (superuser: {user.is_superuser})")
    
    try:
        # Step 1: Load context
        print("\nStep 1: Loading context...")
        context = load_context(user, None)
        print(f"Context: {context}")
        
        # Step 2: Analyze question
        print("\nStep 2: Analyzing question...")
        intent = analyze_question(query, context, session_id=session_id)
        print(f"Raw intent: {intent}")
        
        # Step 3: Apply context
        print("\nStep 3: Applying context...")
        intent = apply_context(query, intent, context)
        print(f"Final intent: {intent}")
        
        # Step 4: Check write action conditions
        print("\nStep 4: Checking write action conditions...")
        action_type = intent.get('action_type')
        requires_approval = intent.get('requires_approval')
        is_write = action_type == 'write' and requires_approval
        
        print(f"  action_type: {action_type}")
        print(f"  requires_approval: {requires_approval}")
        print(f"  is_write: {is_write}")
        
        if is_write:
            print("\n✓ SUCCESS: This should trigger the write action approval flow")
            print("✓ The request should NOT reach the read operations path")
            print("✓ Line 136 in views.py should NOT be executed")
        else:
            print("\n✗ PROBLEM: Write action not properly detected")
            print("✗ This will cause the request to fall through to read operations")
            print("✗ Line 136 will be executed and may fail")
        
        # Step 5: Derive scope
        print("\nStep 5: Deriving scope...")
        scope = derive_scope(user)
        print(f"Scope: {scope}")
        
        return is_write, intent
        
    except Exception as e:
        print(f"ERROR in flow: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, None

if __name__ == '__main__':
    is_write, intent = debug_write_action_flow()
    
    print("\n" + "="*50)
    print("CONCLUSION")
    print("="*50)
    
    if is_write:
        print("✓ Write action properly detected")
        print("✓ Should return approval card early")
        print("✓ Should NOT call generate_natural_answer")
        print("\nIf you're still seeing the response service error,")
        print("the issue might be in the approval action view or")
        print("a different code path.")
    else:
        print("✗ Write action NOT detected properly")
        print("✗ Will fall through to read operations")
        print("✗ Will call generate_natural_answer and fail")
        print("\nNeed to fix the write action detection logic.")