"""Debug script to trace HR Copilot query processing issue."""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from hr_copilot.services.semantic_interpreter import semantic_interpreter
from hr_copilot.services.pipeline import plan_query, derive_scope, build_sql, execute_query
from accounts.models import User

def debug_hr_query():
    print('=== Debugging HR Copilot "No matching records" Issue ===')
    
    # Test query from the user
    query = 'Give me information regarding attendance and leave from Section C'
    print(f'Query: "{query}"')
    print()
    
    try:
        # Step 1: Test semantic interpretation
        print('1. Testing Semantic Interpretation...')
        intent = semantic_interpreter.interpret_query(query)
        print('   ✓ Intent:', intent['intent'])
        print('   ✓ Source:', intent['source']) 
        print('   ✓ Entities:', intent['entities'])
        print()
        
        # Step 2: Get test user with proper permissions
        print('2. Getting Test User...')
        test_user = User.objects.filter(is_superuser=True).first()
        if not test_user:
            print('   ! No superuser found, using first user')
            test_user = User.objects.first()
        print(f'   ✓ User: {test_user.email}')
        print()
        
        # Step 3: Check user scope
        print('3. Checking User Scope...')
        scope = derive_scope(test_user)
        print('   ✓ Scope:', scope)
        print()
        
        # Step 4: Plan the query
        print('4. Planning Query...')
        plan = plan_query(intent, scope)
        print('   ✓ Plan created successfully')
        print('   - Source:', plan['source'])
        print('   - Intent:', plan['intent'])
        print('   - Filters:', plan['filters'])
        print()
        
        # Step 5: Build SQL
        print('5. Building SQL...')
        sql, params = build_sql(plan)
        print('   ✓ SQL:', sql[:100] + '...' if len(sql) > 100 else sql)
        print('   ✓ Params:', params)
        print()
        
        # Step 6: Execute and check results
        print('6. Executing Query...')
        columns, rows = execute_query(sql, params)
        print(f'   ✓ Query executed, returned {len(rows)} rows')
        
        if rows:
            print('   ✓ FOUND DATA! First row:')
            print('     ', dict(zip(columns, rows[0])))
        else:
            print('   ❌ NO ROWS RETURNED - This is the problem!')
            print('   Let me check why...')
            
            # Debug: Check if there's data matching the filters
            from employees.models import Employee
            section_c = Employee.objects.filter(section='C')
            print(f'   - Section C employees in DB: {section_c.count()}')
            
            if 'section' in plan['filters']:
                print(f'   - Query looking for section: {plan["filters"]["section"]}')
            
        return len(rows) > 0
        
    except Exception as e:
        print(f'❌ ERROR: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_hr_query()
    print()
    if success:
        print('✅ Query processing is working - data was found')
    else:
        print('❌ Issue identified - no data returned from query')
        print('This explains why HR Copilot shows "No matching HR records"')