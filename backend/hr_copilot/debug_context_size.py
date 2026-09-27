#!/usr/bin/env python3
"""Debug script to measure and log what's being sent to Qwen"""

import json
import logging
import sys
import os
from datetime import datetime

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from hr_copilot.services.llm import get_structured_intent, generate_natural_answer
from hr_copilot.services.providers import get_llm_provider


class ContextSizeLogger:
    """Intercepts LLM calls to measure context size"""
    
    def __init__(self, original_provider):
        self.original = original_provider
        self.measurements = []
    
    def structured_output(self, messages, **kwargs):
        """Intercept structured output calls to measure size"""
        measurement = self._measure_messages("structured_output", messages, **kwargs)
        self.measurements.append(measurement)
        
        print(f"\n=== STRUCTURED OUTPUT CALL ===")
        print(f"Total Characters: {measurement['total_chars']}")
        print(f"Total Tokens (est): {measurement['total_tokens_est']}")
        print(f"System Prompt Length: {measurement['system_length']}")
        print(f"User Messages Length: {measurement['user_length']}")
        print(f"Schema Size: {measurement['schema_size']}")
        print(f"Options: {measurement['options']}")
        
        if measurement['total_tokens_est'] > 8000:
            print(f"WARNING: Estimated tokens ({measurement['total_tokens_est']}) exceed typical context limits!")
            
        # Still call the original to see the actual error
        try:
            return self.original.structured_output(messages, **kwargs)
        except Exception as e:
            print(f"LLM Error: {e}")
            measurement['error'] = str(e)
            raise
    
    def chat(self, messages, **kwargs):
        """Intercept chat calls to measure size"""
        measurement = self._measure_messages("chat", messages, **kwargs)
        self.measurements.append(measurement)
        
        print(f"\n=== CHAT CALL ===")
        print(f"Total Characters: {measurement['total_chars']}")
        print(f"Total Tokens (est): {measurement['total_tokens_est']}")
        print(f"System Prompt Length: {measurement['system_length']}")
        print(f"User Messages Length: {measurement['user_length']}")
        print(f"Options: {measurement['options']}")
        
        if measurement['total_tokens_est'] > 8000:
            print(f"WARNING: Estimated tokens ({measurement['total_tokens_est']}) exceed typical context limits!")
        
        try:
            return self.original.chat(messages, **kwargs)
        except Exception as e:
            print(f"LLM Error: {e}")
            measurement['error'] = str(e)
            raise
    
    def _measure_messages(self, call_type, messages, **kwargs):
        """Measure the size of messages being sent"""
        measurement = {
            'timestamp': datetime.now().isoformat(),
            'call_type': call_type,
            'total_chars': 0,
            'total_tokens_est': 0,
            'system_length': 0,
            'user_length': 0,
            'message_count': len(messages),
            'schema_size': 0,
            'options': kwargs.get('options', {}),
        }
        
        for msg in messages:
            content = msg.get('content', '')
            char_count = len(content)
            measurement['total_chars'] += char_count
            
            if msg.get('role') == 'system':
                measurement['system_length'] += char_count
            elif msg.get('role') == 'user':
                measurement['user_length'] += char_count
        
        # Rough token estimation (chars / 4)
        measurement['total_tokens_est'] = measurement['total_chars'] // 4
        
        # Measure schema if present
        schema = kwargs.get('schema')
        if schema and schema != 'json':
            schema_str = json.dumps(schema) if isinstance(schema, dict) else str(schema)
            measurement['schema_size'] = len(schema_str)
        
        return measurement
    
    def __getattr__(self, name):
        """Delegate other methods to original provider"""
        return getattr(self.original, name)


def test_query_context_sizes():
    """Test the 5 specified queries to measure their context sizes"""
    
    queries = [
        "Who was absent today?",
        "When did Akshat Awasthi last take leave?", 
        "Mark Akshat Bansal as absent for 24th September",
        "What about yesterday?",
        "Put Rahul on leave tomorrow"
    ]
    
    print("=== CONTEXT SIZE ANALYSIS ===")
    print(f"Testing {len(queries)} queries...")
    
    # Get original provider and wrap it
    original_provider = get_llm_provider()
    if not original_provider:
        print("ERROR: No LLM provider configured!")
        return
    
    logger = ContextSizeLogger(original_provider)
    
    # Monkey patch the provider
    import hr_copilot.services.llm
    import hr_copilot.services.providers
    
    original_get_provider = hr_copilot.services.providers.get_llm_provider
    hr_copilot.services.providers.get_llm_provider = lambda: logger
    hr_copilot.services.llm.get_llm_provider = lambda: logger
    
    try:
        for i, query in enumerate(queries, 1):
            print(f"\n{'='*60}")
            print(f"QUERY {i}: {query}")
            print('='*60)
            
            try:
                # Test intent extraction
                print(f"\n--- Intent Extraction ---")
                intent = get_structured_intent(query)
                print(f"Intent extracted: {intent.get('intent', 'unknown')}")
                
                # Test response generation with minimal data
                print(f"\n--- Response Generation ---")
                test_data = [{"test": "minimal_data", "value": 1}]
                answer = generate_natural_answer(query, intent, test_data)
                print(f"Answer generated: {answer[:100]}...")
                
            except Exception as e:
                print(f"ERROR processing query: {e}")
        
        # Report summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print('='*60)
        
        for i, measurement in enumerate(logger.measurements):
            print(f"\nCall {i+1} ({measurement['call_type']}):")
            print(f"  Total chars: {measurement['total_chars']}")
            print(f"  Est. tokens: {measurement['total_tokens_est']}")
            print(f"  System: {measurement['system_length']} chars")
            print(f"  User: {measurement['user_length']} chars") 
            if measurement.get('error'):
                print(f"  ERROR: {measurement['error']}")
        
        # Find the largest context
        max_measurement = max(logger.measurements, key=lambda x: x['total_chars'])
        print(f"\nLARGEST CONTEXT:")
        print(f"  {max_measurement['total_chars']} chars ({max_measurement['total_tokens_est']} est. tokens)")
        print(f"  Call type: {max_measurement['call_type']}")
        
    finally:
        # Restore original provider
        hr_copilot.services.providers.get_llm_provider = original_get_provider
        hr_copilot.services.llm.get_llm_provider = original_get_provider


if __name__ == '__main__':
    test_query_context_sizes()