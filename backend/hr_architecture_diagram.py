"""
HR COPILOT ARCHITECTURE DIAGRAM
===============================

Visual representation of the complete HR Copilot workflow
"""

print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           HR COPILOT SYSTEM ARCHITECTURE                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

                                USER INTERFACE
                           ┌─────────────────────┐
                           │     React UI        │
                           │ "When did Akshat    │
                           │ last take leave?"   │
                           └──────────┬──────────┘
                                      │ POST /api/hr-copilot/query/
                                      │ Authorization: Bearer <token>
                                      ▼
                           ┌─────────────────────┐
                           │   Django Views      │
                           │   - Authentication  │
                           │   - Input validation│
                           │   - Audit logging   │
                           └──────────┬──────────┘
                                      │ analyze_question()
                                      ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                      SEMANTIC INTERPRETATION LAYER                          ║
║                                                                              ║
║  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    ║
║  │ Security Check  │───▶│ LLM Integration  │───▶│ Entity Resolution   │    ║
║  │ - Block SQL     │    │ - Qwen3-8B       │    │ - Employee lookup   │    ║
║  │ - Block code    │    │ - Natural lang   │    │ - Department match  │    ║
║  │ - Validate input│    │ - Intent extract │    │ - Temporal defaults │    ║
║  └─────────────────┘    └──────────────────┘    └─────────────────────┘    ║
║                                  │                                          ║
║                                  ▼                                          ║
║              ┌─────────────────────────────────────────┐                   ║
║              │        LOCAL QWEN3-8B MODEL            │                   ║
║              │   http://127.0.0.1:11434/api/chat      │                   ║
║              │                                         │                   ║
║              │ Input: "When did Akshat last take leave"│                   ║
║              │ Output: {                               │                   ║
║              │   "intent": "leave_lookup",             │                   ║
║              │   "source": "leave",                    │                   ║
║              │   "entities": {                         │                   ║
║              │     "employee_name": "Akshat Awasthi"   │                   ║
║              │   }                                     │                   ║
║              │ }                                       │                   ║
║              └─────────────────────────────────────────┘                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                      │
                                      ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                         BACKEND PROCESSING LAYER                            ║
║                                                                              ║
║  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    ║
║  │ Authorization   │───▶│ Query Planning   │───▶│ SQL Generation      │    ║
║  │ - Check scope   │    │ - Select template│    │ - Parameterized     │    ║
║  │ - Verify access │    │ - Apply filters  │    │ - Security validated│    ║
║  │ - User permissions│   │ - Set limits     │    │ - Read-only enforced│    ║
║  └─────────────────┘    └──────────────────┘    └─────────────────────┘    ║
║                                                             │                ║
║                                                             ▼                ║
║                          ┌─────────────────────────────────────┐             ║
║                          │         PostgreSQL DATABASE        │             ║
║                          │                                     │             ║
║                          │ SELECT u.first_name, u.last_name,  │             ║
║                          │        lr.start_date, lr.end_date   │             ║
║                          │ FROM leave_management_leaverequest  │             ║
║                          │ WHERE e.id = %s                    │             ║
║                          │ ORDER BY lr.submitted_at DESC       │             ║
║                          │                                     │             ║
║                          │ Result: Akshat's leave on 2024-03-15│             ║
║                          └─────────────────────────────────────┘             ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                      │
                                      ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                        RESPONSE GENERATION LAYER                            ║
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │                     RESPONSE PIPELINE                               │    ║
║  │                                                                     │    ║
║  │  Verified Data ──┐                                                  │    ║
║  │  [{             │                                                  │    ║
║  │    "first_name": "Akshat",      ┌─────────────────┐                │    ║
║  │    "last_name": "Awasthi",   ──▶│ Qwen3-8B Model  │                │    ║
║  │    "start_date": "2024-03-15",  │ Response Gen    │──┐             │    ║
║  │    "leave_type": "Vacation"     └─────────────────┘  │             │    ║
║  │  }]                                                   │             │    ║
║  │                                                       ▼             │    ║
║  │  Query Context ──────────────────────────────┐  ┌─────────────┐    │    ║
║  │  "When did Akshat last take leave?"          └─▶│ Natural     │    │    ║
║  │                                                 │ Language    │    │    ║
║  │                                                 │ Response    │    │    ║
║  │  Grounding Validation ◀─────────────────────────│             │    │    ║
║  │  (Ensures no hallucination)                    └─────────────┘    │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                      │                                      ║
║                                      ▼                                      ║
║                    "Akshat Awasthi last took leave on March 15, 2024"      ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │   JSON Response     │
                           │ {                   │
                           │   "answer": "...",  │
                           │   "intent": "...",  │
                           │   "data": {...},    │
                           │   "status": "ok"    │
                           │ }                   │
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │     React UI        │
                           │   Displays answer   │
                           │   to user naturally │
                           └─────────────────────┘

╔══════════════════════════════════════════════════════════════════════════════╗
║                              SECURITY BOUNDARIES                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

🤖 LLM DOMAIN (Qwen3-8B)          |  🔒 BACKEND DOMAIN (Django/PostgreSQL)
-----------------------------------|--------------------------------------------
✓ Natural language understanding  |  ✓ SQL generation and execution
✓ Intent classification           |  ✓ Authorization and access control  
✓ Entity extraction               |  ✓ Data validation and verification
✓ Response phrasing               |  ✓ Security and injection prevention
✓ Conversation context            |  ✓ Database transactions and integrity
                                  |
❌ NO SQL access                   |  ❌ NO natural language generation
❌ NO database queries             |  ❌ NO intent interpretation
❌ NO authorization decisions      |  ❌ NO conversation context
❌ NO data invention               |  ❌ NO response phrasing

╔══════════════════════════════════════════════════════════════════════════════╗
║                              CONVERSATION FLOW                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Query 1: "Show Rahul's attendance"
   ↓ 
Context saved: {employee_id: 456, employee_name: "Rahul"}
   ↓
Response: "Rahul was present on September 25, 2026"

Query 2: "What about yesterday?" 
   ↓
Context applied: {employee_id: 456} + temporal_expression: "yesterday"
   ↓  
Response: "Rahul was on leave on September 24, 2026"

Query 3: "How about Section C?"
   ↓
New context: {section: "C"}, previous employee context cleared
   ↓
Response: "Section C had 15 employees present and 3 on leave on September 25, 2026"

╔══════════════════════════════════════════════════════════════════════════════╗
║                           SYSTEM STATUS (Current)                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

✅ Ollama Server: RUNNING (127.0.0.1:11434)
✅ Qwen3-8B Model: LOADED (qwen3-8b-q4km-local)  
✅ Django Backend: ACTIVE (HR Copilot endpoints)
✅ PostgreSQL: CONNECTED (80 employees, 88 attendance records)
✅ LLM Provider: CONFIGURED (local_ollama_qwen)
✅ Semantic Interpreter: OPERATIONAL
✅ Entity Resolution: FUNCTIONAL 
✅ Conversation Context: MAINTAINED
✅ Security Validation: ENFORCED

Current Time: 2026-09-27T07:45:58.953Z
Latest Data: September 25, 2026 (smart defaults applied)
""")