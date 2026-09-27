#!/usr/bin/env python3
"""Test write action planning to find where it's failing."""

import os
import sys
import traceback

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from hr_copilot.services.write_actions import write_action_planner
from hr_copilot.services.write_executor import pending_action_manager
from django.contrib.auth import get_user_model

User = get_user_model()

def test_write_action_planning():
    """Test the specific steps that might be failing in write action planning."""
    
    print("TESTING WRITE ACTION PLANNING")
    print("=" * 40)
    
    # Get superuser
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        print("ERROR: No superuser found")
        return
    
    # Create the intent that we know is working
    intent = {
        'intent': 'attendance_update',
        'source': 'attendance', 
        'action_type': 'write',
        'requires_approval': True,
        'entities': {
            'target_status': 'LEAVE',
            'date_range': {'start': '2026-09-24', 'end': '2026-09-24'},
            'employee_id': 14,
            'temporal_scope': {'type': 'date', 'start_date': '2026-09-24', 'end_date': '2026-09-24', 'source': 'llm_resolved'}
        },
        'original_query': 'Make Akshat Bansal Absent for 24th September 2026'
    }
    
    session_id = "test_write_session"
    
    try:
        print("Step 1: Planning write action...")
        pending_action = write_action_planner.plan_write_action(intent, user, session_id)
        
        print("SUCCESS: Write action planned")
        print("Action details:")
        print(f"  Action ID: {pending_action.get('action_id')}")
        print(f"  Action type: {pending_action.get('action_type')}")
        print(f"  Description: {pending_action.get('description')}")
        
        try:
            print("\nStep 2: Storing pending action...")
            action_id = pending_action_manager.store_pending_action(session_id, pending_action)
            
            print("SUCCESS: Pending action stored")
            print(f"Stored action ID: {action_id}")
            
            print("\nCONCLUSION: Write action planning is working correctly")
            print("The issue must be elsewhere in the views.py flow")
            
            return True
            
        except Exception as e:
            print(f"ERROR in step 2 (storing): {type(e).__name__}: {e}")
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"ERROR in step 1 (planning): {type(e).__name__}: {e}")
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_write_action_planning()
    
    if success:
        print("\nWrite action planning works - the issue is in views.py exception handling")
    else:
        print("\nWrite action planning fails - this is why it falls through to read path")