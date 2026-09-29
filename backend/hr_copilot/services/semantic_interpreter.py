"""Enhanced semantic interpretation layer for natural language HR queries."""

import re
from datetime import date, timedelta
from typing import Dict, Any, Optional

from django.utils import timezone
from employees.models import Employee

from .llm import get_structured_intent
from .pipeline import CopilotError


class SemanticInterpreter:
    """Converts natural language queries into structured HR intents with dynamic entity resolution."""
    
    def __init__(self):
        self.temporal_expressions = {
            'today': lambda: timezone.localdate(),
            'yesterday': lambda: timezone.localdate() - timedelta(days=1),
            'two days ago': lambda: timezone.localdate() - timedelta(days=2),
            'the day before': lambda: timezone.localdate() - timedelta(days=2),
            'last week': lambda: (timezone.localdate() - timedelta(days=6), timezone.localdate()),
            'this week': lambda: (timezone.localdate() - timedelta(days=timezone.localdate().weekday()), timezone.localdate()),
            'this month': lambda: (timezone.localdate().replace(day=1), timezone.localdate()),
            'last month': lambda: self._get_last_month_range(),
        }
    
    def interpret_query(self, question: str, context: Dict[str, Any] = None, session_id: str = None) -> Dict[str, Any]:
        """
        Main entry point for semantic interpretation.
        
        Args:
            question: Natural language HR query
            context: Conversation context for follow-up handling
            session_id: Session identifier for bounded memory
            
        Returns:
            Structured intent with resolved entities and missing information
        """
        # First check for security violations
        self._validate_security(question)
        
        # Get LLM interpretation for all queries (including absence)
        structured_intent = get_structured_intent(question, session_id=session_id, context=context)
        if not structured_intent:
            raise CopilotError("llm_unavailable", "Natural language processing is not available.")
        
        # Apply conversation context
        if context:
            structured_intent = self._apply_conversation_context(structured_intent, context, question)
        
        # Resolve temporal expressions to actual dates
        self._resolve_temporal_expressions(structured_intent)
        
        # Apply safe defaults for vague queries
        self._apply_safe_defaults(structured_intent)
        
        # Dynamic entity resolution and validation
        self._resolve_dynamic_entities(structured_intent)
        
        # Check for ambiguities that need clarification
        self._detect_ambiguities(structured_intent)
        
        return structured_intent
    
    def _validate_security(self, question: str) -> None:
        """Reject queries that are outside HR domain or security sensitive."""
        lower = question.strip().casefold()
        
        # Check for code generation requests
        if re.search(r"\b(?:write|generate|create|debug)\b.*\b(?:python|java|javascript|react|django|api|sql|code)\b", lower):
            raise CopilotError("outside_hr_domain", "I'm the HR Copilot. I can help with authorized employee, attendance, and leave information.")
        
        # Check for system access attempts
        if re.search(r"\b(?:show|give|generate)\b.*\b(?:sql|system prompt|password|api key|secret)\b", lower):
            raise CopilotError("outside_hr_domain", "I'm the HR Copilot. I can help with authorized employee, attendance, and leave information.")
        
        # Check for unsupported entities
        if re.search(r"\b(br|business region)\b", lower):
            raise CopilotError("unsupported_entity", "BR is not represented in the current HR data model.")
        
        if re.search(r"\bleave\s+balances?\b", lower):
            raise CopilotError("unsupported_metric", "Leave balances use policy calculations and are not supported by this Copilot query version.")
    
    def _apply_conversation_context(self, intent: Dict[str, Any], context: Dict[str, Any], question: str) -> Dict[str, Any]:
        """Apply conversation context for follow-up questions."""
        entities = intent.get("entities", {})

        # Handle pronoun references to previous employee
        follow_up_reference = re.compile(r"\b(?:he|she|they|them|that employee|the employee)\b", re.IGNORECASE)
        if (context.get("current_employee_id") and 
            not entities.get("employee_name") and 
            not entities.get("employee_email") and 
            follow_up_reference.search(question)):
            entities["employee_id"] = context["current_employee_id"]
        
        # Inherit temporal context for relative references
        relative_temporal = re.search(r"\b(?:what about|how about)\s+(?:yesterday|today|last week|this month)\b", question.lower())
        if relative_temporal and not entities.get("temporal_expression"):
            # Update temporal expression based on relative reference
            temporal_match = re.search(r"\b(yesterday|today|last week|this month)\b", question.lower())
            if temporal_match:
                entities["temporal_expression"] = temporal_match.group(1)
        
        # Inherit section/department context for scope-based follow-ups
        scope_followup = re.search(r"\b(?:what about|how about|only the|just the)\b", question.lower())
        if scope_followup and context.get("current_section") and not entities.get("section"):
            # Only inherit if the question seems to be about the same scope
            if not re.search(r"\b(?:section|department|employee)\b", question.lower()):
                entities["section"] = context["current_section"]
        
        intent["entities"] = entities
        return intent
    
    def _resolve_temporal_expressions(self, intent: Dict[str, Any]) -> None:
        """Convert temporal expressions to actual date ranges."""
        entities = intent.get("entities", {})
        temporal_expr = entities.get("temporal_expression")
        
        if not temporal_expr:
            return
        
        temporal_expr = temporal_expr.lower().strip()
        
        # Handle natural date parsing (e.g., "March 15", "15th March 2026")
        natural_date = self._parse_natural_date(temporal_expr)
        if natural_date:
            entities["date_range"] = {"start": natural_date, "end": natural_date}
            entities.pop("temporal_expression", None)
            return
        
        # Handle ISO dates
        iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", temporal_expr)
        if iso_match:
            try:
                parsed_date = date.fromisoformat(iso_match.group(1))
                entities["date_range"] = {"start": parsed_date.isoformat(), "end": parsed_date.isoformat()}
                entities.pop("temporal_expression", None)
                return
            except ValueError:
                pass
        
        # Handle predefined expressions
        if temporal_expr in self.temporal_expressions:
            result = self.temporal_expressions[temporal_expr]()
            if isinstance(result, tuple):
                start_date, end_date = result
                entities["date_range"] = {"start": start_date.isoformat(), "end": end_date.isoformat()}
            else:
                entities["date_range"] = {"start": result.isoformat(), "end": result.isoformat()}
            entities.pop("temporal_expression", None)
        else:
            # Keep temporal expression for backend processing if not recognized
            pass
    
    def _parse_natural_date(self, text: str) -> Optional[str]:
        """Parse natural date expressions like 'March 15' or '15th March 2026'."""
        month_names = {
            "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
            "apr": 4, "april": 4, "may": 5, "june": 6, "jun": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
            "nov": 11, "november": 11, "dec": 12, "december": 12,
        }
        
        today = timezone.localdate()
        
        # Try "15th March" or "15 March 2026"
        m1 = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)(?:\s+(\d{4}))?\b", text.lower())
        if m1 and m1.group(2) in month_names:
            day = int(m1.group(1))
            month = month_names[m1.group(2)]
            year = int(m1.group(3)) if m1.group(3) else today.year
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                pass
        
        # Try "March 15" or "March 15 2026"
        m2 = re.search(r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{4}))?\b", text.lower())
        if m2 and m2.group(1) in month_names:
            month = month_names[m2.group(1)]
            day = int(m2.group(2))
            year = int(m2.group(3)) if m2.group(3) else today.year
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                pass
        
        return None
    
    def _get_last_month_range(self) -> tuple:
        """Calculate last month's date range."""
        today = timezone.localdate()
        last_month_end = today.replace(day=1) - timedelta(days=1)
        last_month_start = date(last_month_end.year, last_month_end.month, 1)
        return last_month_start, last_month_end
    
    def _apply_safe_defaults(self, intent: Dict[str, Any]) -> None:
        """Apply safe defaults for vague queries where appropriate."""
        entities = intent.get("entities", {})
        source = intent.get("source")
        intent_name = intent.get("intent")
        
        # For attendance queries without temporal context, use the most recent available data
        # instead of defaulting to "today" which might not have data yet
        if (source == "attendance" and 
            intent_name in ("attendance_lookup", "attendance_summary", "absence_lookup", "absence_count") and
            not entities.get("date_range") and 
            not entities.get("temporal_expression")):
            
            # Get the most recent attendance date from the database
            try:
                from attendance.models import Attendance
                latest_date = Attendance.objects.values_list('date', flat=True).order_by('-date').first()
                
                if latest_date:
                    # Use the most recent date with actual data
                    entities["date_range"] = {"start": latest_date.isoformat(), "end": latest_date.isoformat()}
                    entities["temporal_scope"] = {
                        "type": "latest_available", 
                        "start_date": latest_date.isoformat(), 
                        "end_date": latest_date.isoformat(), 
                        "source": "smart_default"
                    }
                else:
                    # Fallback to today if no data exists
                    today = timezone.localdate()
                    entities["date_range"] = {"start": today.isoformat(), "end": today.isoformat()}
                    entities["temporal_scope"] = {"type": "today", "start_date": today.isoformat(), "end_date": today.isoformat(), "source": "fallback"}
                    
            except Exception:
                # Fallback to today if database query fails
                today = timezone.localdate()
                entities["date_range"] = {"start": today.isoformat(), "end": today.isoformat()}
                entities["temporal_scope"] = {"type": "today", "start_date": today.isoformat(), "end_date": today.isoformat(), "source": "error_fallback"}
    
    def _resolve_dynamic_entities(self, intent: Dict[str, Any]) -> None:
        """Dynamically resolve entities against the database."""
        entities = intent.get("entities", {})

        department_value = str(entities.get("department") or "").strip().upper()
        subsection_match = re.fullmatch(r"([A-Z])([0-9]+)", department_value)
        if subsection_match and not entities.get("subsection"):
            entities["section"] = subsection_match.group(1)
            entities["subsection"] = department_value
            entities.pop("department", None)
        
        # Resolve department names with fuzzy matching
        if entities.get("department"):
            resolved_dept = self._resolve_department(entities["department"])
            if resolved_dept:
                entities["department"] = resolved_dept
            else:
                # Mark as missing information for clarification
                missing_info = intent.setdefault("missing_information", [])
                if "department" not in missing_info:
                    missing_info.append("department")
        
        # Normalize section and subsection formatting
        if entities.get("section"):
            entities["section"] = entities["section"].upper()
        
        if entities.get("subsection"):
            entities["subsection"] = entities["subsection"].upper()
    
    def _resolve_department(self, requested_dept: str) -> Optional[str]:
        """Resolve department name with fuzzy matching."""
        # Get all available departments
        departments = set(Employee.objects.values_list("department", flat=True).distinct())
        
        requested_lower = requested_dept.lower().strip()
        
        # Handle special cases
        if requested_lower in {"student", "student department", "students"}:
            return next((dept for dept in departments if dept.lower() in {"student", "student department"}), None)
        
        # Exact match (case insensitive)
        for dept in departments:
            if dept.lower() == requested_lower:
                return dept
        
        # Partial match (department contains the requested term)
        for dept in departments:
            if requested_lower in dept.lower() or dept.lower() in requested_lower:
                return dept
        
        # Fuzzy matching for common abbreviations
        abbreviations = {
            "hr": "human resources",
            "it": "information technology",
            "dev": "development",
            "eng": "engineering",
            "fin": "finance",
            "admin": "administration",
            "ops": "operations",
        }
        
        expanded = abbreviations.get(requested_lower)
        if expanded:
            for dept in departments:
                if expanded in dept.lower() or dept.lower().startswith(requested_lower):
                    return dept
        
        return None
    
    def _detect_ambiguities(self, intent: Dict[str, Any]) -> None:
        """Detect ambiguous references that need clarification."""
        entities = intent.get("entities", {})
        
        # Check for employee name ambiguity
        employee_name = entities.get("employee_name")
        if employee_name and not entities.get("employee_email"):
            from .employee_resolver import employee_resolver
            resolution = employee_resolver.resolve_employee(name=employee_name)
            
            if resolution.status == "ambiguous":
                ambiguities = intent.setdefault("ambiguities", [])
                if "employee_identity" not in ambiguities:
                    ambiguities.append("employee_identity")
            elif resolution.status == "not_found":
                missing_info = intent.setdefault("missing_information", [])
                if "employee_identity" not in missing_info:
                    missing_info.append("employee_identity")
            elif resolution.status == "resolved":
                # Replace name with resolved ID for backend processing
                entities["employee_id"] = resolution.employee_id
                entities.pop("employee_name", None)
        
        # Check for section/subsection ambiguity when referenced vaguely
        if not entities.get("section") and not entities.get("subsection"):
            # Look for vague section references in the original query
            # This would be handled by the LLM marking it as missing information
            pass


# Create singleton instance
semantic_interpreter = SemanticInterpreter()
