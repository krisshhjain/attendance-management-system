"""
HR COPILOT WORKING FLOW DOCUMENTATION
=====================================

This document explains the complete working flow of the HR Copilot system,
from natural language input to verified HR data response.

ARCHITECTURE OVERVIEW:
User Query → Semantic Interpretation → Backend Validation → Database Query → Natural Response

"""

import os
import django

# Setup Django to demonstrate the flow
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def demonstrate_hr_copilot_flow():
    print("=" * 70)
    print("HR COPILOT COMPLETE WORKING FLOW DEMONSTRATION")
    print("=" * 70)
    print()
    
    # Example user query
    user_query = "When did Akshat Awasthi last took leave"
    print(f"👤 USER INPUT: '{user_query}'")
    print()
    
    # STEP 1: React UI → Django API Endpoint
    print("🌐 STEP 1: FRONTEND TO BACKEND")
    print("   React UI → POST /api/hr-copilot/query/")
    print("   Headers: Authorization Bearer token")
    print("   Body: {'message': 'When did Akshat Awasthi last took leave', 'conversation_id': 'abc123'}")
    print()
    
    # STEP 2: Django View Processing
    print("🔧 STEP 2: DJANGO VIEW PROCESSING (views.py)")
    print("   → Authentication check (requires System Admin)")
    print("   → Input validation (message length, format)")
    print("   → Create audit record")
    print("   → Load conversation context")
    print()
    
    # STEP 3: Semantic Interpretation
    print("🧠 STEP 3: SEMANTIC INTERPRETATION (semantic_interpreter.py)")
    print("   → Security validation (reject SQL injection, code generation)")
    print("   → Call local Qwen3-8B model via Ollama")
    print("   → Convert natural language to structured intent")
    
    # Demonstrate this step
    from hr_copilot.services.semantic_interpreter import semantic_interpreter
    try:
        intent = semantic_interpreter.interpret_query(user_query)
        print(f"   ✅ LLM Result:")
        print(f"      Intent: {intent['intent']}")
        print(f"      Source: {intent['source']}")
        print(f"      Entities: {intent['entities']}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()
    
    # STEP 4: LLM Provider Chain
    print("🤖 STEP 4: LLM PROVIDER CHAIN (providers.py → llm.py)")
    print("   → get_llm_provider() checks environment variables")
    print("   → LocalOllamaQwenProvider connects to http://127.0.0.1:11434")
    print("   → Structured output request with JSON schema")
    print("   → Qwen3-8B processes: 'Extract HR intent from: When did Akshat...'")
    print("   → Returns: {intent: 'leave_lookup', source: 'leave', entities: {employee_name: 'Akshat Awasthi'}}")
    print()
    
    # STEP 5: Entity Resolution & Validation
    print("🔍 STEP 5: ENTITY RESOLUTION & VALIDATION (semantic_interpreter.py)")
    print("   → Resolve 'Akshat Awasthi' against PostgreSQL employees table")
    print("   → Check for ambiguous matches (multiple employees with same name)")
    print("   → Apply temporal defaults (use latest available data if no date specified)")
    print("   → Validate entities against database constraints")
    
    from hr_copilot.services.employee_resolver import employee_resolver
    resolution = employee_resolver.resolve_employee(name="Akshat Awasthi")
    print(f"   ✅ Employee Resolution: {resolution.as_dict()}")
    print()
    
    # STEP 6: Authorization & Scope Check
    print("🔒 STEP 6: AUTHORIZATION & SCOPE CHECK (pipeline.py)")
    print("   → derive_scope(user) checks user permissions")
    print("   → Super Admin: unrestricted access")
    print("   → Regular users: limited to assigned sections/subsections")
    print("   → Verify employee is within user's scope")
    
    from hr_copilot.services.pipeline import derive_scope
    from accounts.models import User
    test_user = User.objects.filter(is_superuser=True).first()
    if test_user:
        scope = derive_scope(test_user)
        print(f"   ✅ User Scope: {scope}")
    print()
    
    # STEP 7: Query Planning
    print("📋 STEP 7: QUERY PLANNING (pipeline.py)")
    print("   → plan_query(intent, scope) creates execution plan")
    print("   → Determines SQL template based on intent")
    print("   → Applies filters from entities")
    print("   → Sets result limits and aggregation type")
    
    if test_user and 'intent' in locals():
        from hr_copilot.services.pipeline import plan_query
        try:
            plan = plan_query(intent, scope)
            print(f"   ✅ Query Plan:")
            print(f"      Source: {plan['source']}")
            print(f"      Intent: {plan['intent']}")
            print(f"      Filters: {plan['filters']}")
        except Exception as e:
            print(f"   ❌ Planning Error: {e}")
    print()
    
    # STEP 8: SQL Generation
    print("🗄️  STEP 8: SQL GENERATION (pipeline.py)")
    print("   → build_sql(plan) creates parameterized SQL")
    print("   → Uses approved templates only (security)")
    print("   → Binds all user input as parameters (no SQL injection)")
    print("   → Applies user scope restrictions in WHERE clauses")
    
    if 'plan' in locals():
        from hr_copilot.services.pipeline import build_sql
        try:
            sql, params = build_sql(plan)
            print(f"   ✅ Generated SQL:")
            print(f"      SQL: {sql[:100]}...")
            print(f"      Params: {params}")
        except Exception as e:
            print(f"   ❌ SQL Error: {e}")
    print()
    
    # STEP 9: Database Execution
    print("💾 STEP 9: DATABASE EXECUTION (pipeline.py)")
    print("   → validate_sql() ensures read-only, safe query")
    print("   → execute_query() runs in read-only transaction")
    print("   → 5-second timeout for performance")
    print("   → Returns columns and rows")
    
    if 'sql' in locals() and 'params' in locals():
        from hr_copilot.services.pipeline import execute_query, validate_sql
        try:
            validate_sql(sql)
            columns, rows = execute_query(sql, params)
            print(f"   ✅ Query Results:")
            print(f"      Columns: {columns}")
            print(f"      Rows: {len(rows)} records")
            if rows:
                print(f"      Sample: {dict(zip(columns, rows[0]))}")
        except Exception as e:
            print(f"   ❌ Execution Error: {e}")
    print()
    
    # STEP 10: Response Generation
    print("📝 STEP 10: RESPONSE GENERATION (llm.py)")
    print("   → generate_natural_answer() uses Qwen3-8B for natural phrasing")
    print("   → ONLY uses verified data from database (no hallucination)")
    print("   → Fallback to deterministic templates if LLM unavailable")
    print("   → Grounding validation ensures factual accuracy")
    
    if 'intent' in locals() and 'rows' in locals():
        from hr_copilot.services.llm import generate_natural_answer
        try:
            # Convert rows to proper format for response generation
            data = []
            if 'columns' in locals() and rows:
                data = [dict(zip(columns, row)) for row in rows]
            
            natural_response = generate_natural_answer(user_query, intent, data)
            if natural_response:
                print(f"   ✅ Natural Response: '{natural_response}'")
            else:
                print("   ⚡ Fallback to deterministic response")
        except Exception as e:
            print(f"   ❌ Response Error: {e}")
    print()
    
    # STEP 11: Audit & Context Saving
    print("📊 STEP 11: AUDIT & CONTEXT SAVING")
    print("   → Save query audit with execution details")
    print("   → Update conversation context for follow-ups")
    print("   → Store current employee/section for 'What about yesterday?' queries")
    print()
    
    # STEP 12: API Response
    print("🔙 STEP 12: API RESPONSE TO FRONTEND")
    print("   → JSON response with answer, intent, scope, data")
    print("   → Status code 200 for success, 4xx/5xx for errors")
    print("   → Frontend displays natural language answer to user")
    print()
    
    print("=" * 70)
    print("SECURITY BOUNDARIES")
    print("=" * 70)
    print("🛡️  LLM HANDLES:")
    print("   - Natural language understanding")
    print("   - Intent classification")
    print("   - Entity extraction")
    print("   - Response phrasing")
    print()
    print("🔒 BACKEND HANDLES:")
    print("   - SQL generation and execution")
    print("   - Authorization and scope enforcement") 
    print("   - Database access and validation")
    print("   - Data verification and truth")
    print("   - Security and injection prevention")
    print()
    
    print("=" * 70)
    print("KEY INNOVATIONS")
    print("=" * 70)
    print("🎯 SEMANTIC UNDERSTANDING:")
    print("   - 'Who was absent?' = 'Who didn't come?' = 'Anyone missing?'")
    print("   - All map to same intent: absence_lookup")
    print()
    print("🧠 SMART DEFAULTS:")
    print("   - Vague queries use latest available data")
    print("   - No 'today' if no data exists for today")
    print()
    print("💬 CONVERSATION CONTEXT:")
    print("   - 'Show Rahul' → 'What about yesterday?' (inherits Rahul)")
    print("   - Follow-up questions maintain context")
    print()
    print("🔍 DYNAMIC RESOLUTION:")
    print("   - 'HR' → 'Human Resources' (fuzzy department matching)")
    print("   - 'Rahul' → Resolve against database, detect ambiguity")
    print()

if __name__ == "__main__":
    demonstrate_hr_copilot_flow()