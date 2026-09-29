#!/usr/bin/env python3
"""Test the 5 specified queries with compact context system"""

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

from hr_copilot.services.llm import get_structured_intent, generate_natural_answer
from hr_copilot.services.session_memory import session_memory
from hr_copilot.services.pipeline import analyze_question
from hr_copilot.services.providers import get_llm_provider


def measure_context_size(messages):
    """Measure the total context size being sent to Qwen"""
    total_chars = sum(len(msg.get('content', '')) for msg in messages)
    total_tokens_est = total_chars // 4  # Rough estimation
    
    system_chars = sum(len(msg.get('content', '')) for msg in messages if msg.get('role') == 'system')
    user_chars = sum(len(msg.get('content', '')) for msg in messages if msg.get('role') == 'user')
    
    return {
        'total_chars': total_chars,
        'total_tokens_est': total_tokens_est,
        'system_chars': system_chars,
        'user_chars': user_chars,
        'message_count': len(messages)
    }


def test_compact_context():
    """Test the 5 queries with our compact context system"""
    
    queries = [
        "Who was absent today?",
        "When did Akshat Awasthi last take leave?", 
        "Mark Akshat Bansal as absent for 24th September",
        "What about yesterday?",
        "Put Rahul on leave tomorrow"
    ]
    
    print("=== COMPACT CONTEXT TEST ===")
    print(f"Testing {len(queries)} queries with bounded session memory...")
    print(f"Date: {datetime.now().isoformat()}")
    
    # Check if provider is available
    provider = get_llm_provider()
    if not provider:
        print("ERROR: No LLM provider configured!")
        return
    
    session_id = "test_session_2026_09_27"
    
    # Clear any existing session state
    session_memory.clear_session(session_id)
    
    results = []
    
    for i, query in enumerate(queries, 1):
        print(f"\n{'='*60}")
        print(f"QUERY {i}: {query}")
        print('='*60)
        
        try:
            print(f"\n--- Session State Before Query ---")
            state_before = session_memory.get_session_state(session_id)
            print(f"State: {state_before.to_dict()}")
            
            print(f"\n--- Intent Extraction ---")
            
            # Monkey patch to measure context size
            original_structured_output = provider.structured_output
            context_measurements = []
            
            def measuring_structured_output(messages, **kwargs):
                measurement = measure_context_size(messages)
                context_measurements.append(measurement)
                print(f"Context size: {measurement['total_chars']} chars (~{measurement['total_tokens_est']} tokens)")
                print(f"  System: {measurement['system_chars']} chars")
                print(f"  User: {measurement['user_chars']} chars")
                return original_structured_output(messages, **kwargs)
            
            provider.structured_output = measuring_structured_output
            
            try:
                intent = get_structured_intent(query, session_id=session_id)
                print(f"Intent extracted: {intent.get('intent', 'unknown')}")
                print(f"Action type: {intent.get('action_type', 'unknown')}")
                print(f"Requires approval: {intent.get('requires_approval', False)}")
                
                if intent.get('entities'):
                    print(f"Entities: {list(intent['entities'].keys())}")
                
            except Exception as e:
                print(f"ERROR extracting intent: {e}")
                intent = None
            
            finally:
                provider.structured_output = original_structured_output
            
            print(f"\n--- Session State After Query ---")
            state_after = session_memory.get_session_state(session_id)
            print(f"State: {state_after.to_dict()}")
            
            # Test response generation with minimal test data
            if intent:
                print(f"\n--- Response Generation Test ---")
                test_data = [{"name": "Test Employee", "status": "PRESENT", "value": 1}]
                
                # Monkey patch again for response generation
                response_measurements = []
                
                def measuring_structured_output_response(messages, **kwargs):
                    measurement = measure_context_size(messages)
                    response_measurements.append(measurement)
                    print(f"Response context size: {measurement['total_chars']} chars (~{measurement['total_tokens_est']} tokens)")
                    return original_structured_output(messages, **kwargs)
                
                provider.structured_output = measuring_structured_output_response
                
                try:
                    answer = generate_natural_answer(query, intent, test_data, session_id=session_id)
                    print(f"Answer generated: {answer[:100]}...")
                except Exception as e:
                    print(f"ERROR generating answer: {e}")
                    answer = None
                finally:
                    provider.structured_output = original_structured_output
                
                # Record results
                results.append({
                    'query': query,
                    'intent_success': True,
                    'intent_measurements': context_measurements,
                    'response_success': answer is not None,
                    'response_measurements': response_measurements,
                    'session_state': state_after.to_dict()
                })
            else:
                results.append({
                    'query': query,
                    'intent_success': False,
                    'intent_measurements': context_measurements,
                    'response_success': False,
                    'response_measurements': [],
                    'session_state': state_after.to_dict()
                })
        
        except Exception as e:
            print(f"CRITICAL ERROR processing query: {e}")
            results.append({
                'query': query,
                'intent_success': False,
                'error': str(e),
                'intent_measurements': [],
                'response_success': False,
                'response_measurements': [],
                'session_state': {}
            })
    
    # Generate summary report
    print(f"\n{'='*80}")
    print("COMPACT CONTEXT TEST SUMMARY")
    print('='*80)
    
    all_measurements = []
    successful_queries = 0
    avg_chars = 0
    
    for result in results:
        if result.get('intent_success'):
            successful_queries += 1
        all_measurements.extend(result.get('intent_measurements', []))
        all_measurements.extend(result.get('response_measurements', []))
    
    if all_measurements:
        max_chars = max(m['total_chars'] for m in all_measurements)
        max_tokens = max(m['total_tokens_est'] for m in all_measurements)
        avg_chars = sum(m['total_chars'] for m in all_measurements) / len(all_measurements)
        avg_tokens = sum(m['total_tokens_est'] for m in all_measurements) / len(all_measurements)
        
        print(f"\nContext Size Analysis:")
        print(f"  Maximum: {max_chars} chars (~{max_tokens} tokens)")
        print(f"  Average: {avg_chars:.0f} chars (~{avg_tokens:.0f} tokens)")
        print(f"  Total LLM calls: {len(all_measurements)}")
        
        # Check if we're under typical context limits
        if max_tokens <= 4000:
            print(f"  ✓ All contexts under 4K token limit")
        elif max_tokens <= 8000:
            print(f"  ⚠ Contexts under 8K token limit (safe for most models)")
        else:
            print(f"  ✗ Some contexts exceed 8K tokens (may cause issues)")
    
    print(f"\nQuery Success Rate: {successful_queries}/{len(queries)} ({successful_queries/len(queries)*100:.1f}%)")
    
    # Show context evolution
    print(f"\nSession Memory Evolution:")
    for i, result in enumerate(results, 1):
        state = result.get('session_state', {})
        if state:
            compact_state = {k: v for k, v in state.items() if v is not None}
            print(f"  After Query {i}: {compact_state}")
        else:
            print(f"  After Query {i}: (no state)")
    
    # Calculate approximate context reduction
    print(f"\nContext Reduction Estimate:")
    print(f"  Before: Large system prompts with full examples (~2000+ chars)")
    print(f"  After: Compact prompts with session context (~{avg_chars:.0f} chars average)")
    if avg_chars > 0:
        reduction_pct = max(0, (2000 - avg_chars) / 2000 * 100)
        print(f"  Estimated reduction: ~{reduction_pct:.0f}%")


if __name__ == '__main__':
    test_compact_context()
