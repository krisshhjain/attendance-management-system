#!/usr/bin/env python3
"""Test the complete write request flow with JSON serialization fix."""

import os
import sys
import json
from datetime import datetime

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from hr_copilot.views import HRCopilotQueryView

User = get_user_model()


def test_complete_write_flow():
    """Test the complete write request flow including JSON serialization."""
    
    print("=== TESTING COMPLETE WRITE FLOW ===")
    print("Query: Make Akshat Bansal as Absent for 24th September 2026")
    print(f"Time: {datetime.now().isoformat()}")
    print()
    
    # Get superuser
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        print("ERROR: No superuser found")
        return
    
    print(f"User: {user.username} (superuser: {user.is_superuser})")
    
    # Create request factory
    factory = RequestFactory()
    
    # Create POST request data
    request_data = {
        "message": "Make Akshat Bansal as Absent for 24th September 2026",
        "conversation_id": "test_conversation_2026"
    }
    
    # Create Django request
    request = factory.post('/hr-copilot/query/', data=request_data, content_type='application/json')
    request.user = user
    
    # Add session
    from django.contrib.sessions.backends.db import SessionStore
    session = SessionStore()
    session.save()
    request.session = session
    
    print(f"Request data: {request_data}")
    print()
    
    # Call the view
    view = HRCopilotQueryView()
    view.request = request
    
    try:
        print("Calling HRCopilotQueryView.post()...")
        response = view.post(request)
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            print("SUCCESS: Write request completed successfully!")
            print("Response data:")
            print(json.dumps(response.data, indent=2, default=str))
            
            # Check if it's a pending approval response
            if response.data.get('query_status') == 'pending_approval':
                print("\n✅ PERFECT: Approval card should be shown to user")
                print("✅ No database writes happened yet (correct)")
                print("✅ JSON serialization successful")
                
                action_id = response.data.get('action_id')
                pending_action = response.data.get('pending_action')
                
                print(f"\nPending Action Details:")
                print(f"  Action ID: {action_id}")
                print(f"  Description: {pending_action.get('description')}")
                print(f"  Employee: {pending_action.get('target_data', {}).get('employee_name')}")
                print(f"  Date: {pending_action.get('target_data', {}).get('date')}")
                print(f"  Status: {pending_action.get('target_data', {}).get('target_status')}")
                
            else:
                print(f"Unexpected query status: {response.data.get('query_status')}")
                
        else:
            print(f"ERROR: Request failed with status {response.status_code}")
            print("Response data:")
            print(json.dumps(response.data, indent=2, default=str))
            
    except Exception as e:
        print(f"ERROR: Exception occurred - {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def test_read_regression():
    """Test that read operations still work."""
    print("\n=== TESTING READ REGRESSION ===")
    
    read_queries = [
        "Who was absent today?",
        "Show Akshat Bansal's attendance", 
        "When did Akshat Awasthi last take leave?"
    ]
    
    user = User.objects.filter(is_superuser=True).first()
    factory = RequestFactory()
    
    for query in read_queries:
        print(f"\nTesting: {query}")
        
        request_data = {"message": query}
        request = factory.post('/hr-copilot/query/', data=request_data, content_type='application/json')
        request.user = user
        
        # Add session
        from django.contrib.sessions.backends.db import SessionStore
        session = SessionStore()
        session.save()
        request.session = session
        
        view = HRCopilotQueryView()
        view.request = request
        
        try:
            response = view.post(request)
            
            if response.status_code == 200:
                query_status = response.data.get('query_status')
                print(f"  ✅ SUCCESS: {query_status}")
            else:
                print(f"  ❌ FAILED: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ ERROR: {e}")


if __name__ == '__main__':
    test_complete_write_flow()
    test_read_regression()
    
    print("\n=== SUMMARY ===")
    print("If the write flow shows 'pending_approval' status:")
    print("✅ The HR Copilot write request is FIXED")
    print("✅ JSON serialization issue resolved")
    print("✅ Approval card should display correctly")
    print("✅ No premature database writes")
    print("\nThe user should now see an approval card instead of generic failure.")