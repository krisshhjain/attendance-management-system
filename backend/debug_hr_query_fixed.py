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
    print('=== Debugging HR Copilot No Matching Records Issue ===')
    
    # Test query from the user
    query = 'Give me information regarding attendance and leave from Section C'
    print(f'Query: "{query}"')
    print()
    
    try:
        # Step 1: Test semantic interpretation
        print('1. Testing Semantic Interpretation...')
        intent = semantic_interpreter.interpret_query(query)
        print('   Intent:', intent['intent'])
        print('   Source:', intent['source']) 
        print('   Entities:', intent['entities'])
        print()
        
        # Step 2: Get test user with proper permissions
        print('2. Getting Test User...')
        test_user = User.objects.filter(is_superuser=True).first()
        if not test_user:
            print('   No superuser found, using first user')
            test_user = User.objects.first()
        print(f'   User: {test_user.email}')
        print()
        
        # Step 3: Check user scope
        print('3. Checking User Scope...')
        scope = derive_scope(test_user)
        print('   Scope:', scope)
        print()
        
        # Step 4: Plan the query
        print('4. Planning Query...')
        plan = plan_query(intent, scope)
        print('   Plan created successfully')
        print('   - Source:', plan['source'])
        print('   - Intent:', plan['intent'])
        print('   - Filters:', plan['filters'])
        print()
        
        # Step 5: Build SQL
        print('5. Building SQL...')
        sql, params = build_sql(plan)
        print('   SQL:', sql)
        print('   Params:', params)
        print()
        
        # Step 6: Execute and check results
        print('6. Executing Query...')
        columns, rows = execute_query(sql, params)
        print(f'   Query executed, returned {len(rows)} rows')
        
        if rows:
            print('   FOUND DATA! First few rows:')
            for i, row in enumerate(rows[:3]):
                print(f'     Row {i+1}:', dict(zip(columns, row)))
        else:
            print('   NO ROWS RETURNED - This is the problem!')
            print('   Investigating why...')
            
            # Debug: Check if there's data matching the filters
            from employees.models import Employee
            from attendance.models import Attendance
            
            print('   Database check:')
            section_c = Employee.objects.filter(section='C')
            print(f'   - Section C employees in DB: {section_c.count()}')
            
            recent_attendance = Attendance.objects.filter(employee__section='C')
            print(f'   - Section C attendance records: {recent_attendance.count()}')
            
            if 'section' in plan['filters']:
                print(f'   - Query looking for section: {plan["filters"]["section"]}')
                
            # Check if the SQL is correct by testing a simpler version
            print('   Testing simpler query:')
            simple_sql = "SELECT COUNT(*) FROM employees_employee e WHERE e.section = %s"
            simple_params = ['C']
            simple_columns, simple_rows = execute_query(simple_sql, simple_params)
            print(f'   Simple count query returned: {simple_rows}')
            
        return len(rows) > 0
        
    except Exception as e:
        print(f'ERROR: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_hr_query()
    print()
    if success:
        print('SUCCESS: Query processing is working - data was found')
    else:
        print('ISSUE IDENTIFIED: No data returned from query')
        print('This explains why HR Copilot shows "No matching HR records"')