"""Intent normalization layer for HR Copilot.

This module provides deterministic mapping between LLM outputs and backend tools,
ensuring the LLM cannot arbitrarily select backend sources or tools.
"""

import re
from datetime import date, timedelta
from typing import Dict, Any
from .pipeline import CopilotError
from .regex_safety import (
    find_email_address,
    find_ordered_capture,
    has_ordered_regex_matches,
)


def _is_find_employee_query(text: str) -> bool:
    """Match a trailing ``find <name>`` query with a linear suffix scan."""
    end = len(text) - 1 if text.endswith("\n") else len(text)
    suffix_start = end
    while suffix_start > 0:
        character = text[suffix_start - 1]
        if character.isalnum() or character == "_" or character in " .'-":
            suffix_start -= 1
        else:
            break

    suffix = text[suffix_start:end]
    match = re.search(r"\bfind\s+", suffix)
    if not match:
        return False
    name = suffix[match.end():]
    return bool(name and any(not character.isspace() for character in name))


class IntentNormalizer:
    """Normalizes LLM intent output to backend-compatible format."""
    
    def __init__(self):
        self.unsupported_write_intents = {
            'attendance_delete', 'leave_update', 'employee_update',
            'bulk_attendance_update',
        }
        # Deterministic intent → source mapping
        self.intent_source_mapping = {
            # Attendance operations
            'attendance_lookup': 'attendance',
            'attendance_update': 'attendance', 
            'attendance_create': 'attendance',
            'attendance_summary': 'attendance',
            'attendance_count': 'attendance',
            'attendance_trend': 'attendance',
            'attendance_intelligence': 'attendance',
            'leave_regularization_intelligence': 'leave',
            'workforce_intelligence': 'employee',
            'attendance_force_checkout': 'attendance',
            'regularization_create': 'attendance',
            'regularization_approve': 'attendance',
            'regularization_reject': 'attendance',
            'employee_shift_assign': 'employee',
            'employee_status_update': 'employee',
            
            # Employee operations  
            'employee_lookup': 'employee',
            'employee_summary': 'employee',
            'employee_count': 'employee',
            
            # Leave operations
            'leave_lookup': 'leave',
            'leave_create': 'leave',
            'leave_update': 'leave', 
            'leave_cancel': 'leave',
            'leave_approve': 'leave',
            'leave_deny': 'leave',
            'leave_summary': 'leave',
            'leave_count': 'leave',
            'leave_trend': 'leave',
            
            # Absence operations (uses employee source for queries)
            'absence_lookup': 'employee',
            'absence_count': 'employee',
            
            # Comparison operations
            'comparison': 'employee',
        }
        
        # Intent → backend tool mapping
        self.intent_tool_mapping = {
            # Read operations
            'attendance_lookup': 'attendance_read_tool',
            'attendance_summary': 'attendance_read_tool', 
            'attendance_count': 'attendance_read_tool',
            'attendance_trend': 'attendance_read_tool',
            'attendance_intelligence': 'attendance_intelligence_tool',
            'leave_regularization_intelligence': 'leave_regularization_intelligence_tool',
            'workforce_intelligence': 'workforce_intelligence_tool',
            'attendance_force_checkout': 'attendance_force_checkout_tool',
            'regularization_create': 'regularization_create_tool',
            'regularization_approve': 'regularization_review_tool',
            'regularization_reject': 'regularization_review_tool',
            'employee_shift_assign': 'employee_shift_assign_tool',
            'employee_status_update': 'employee_status_update_tool',
            
            'employee_lookup': 'employee_lookup_tool',
            'employee_summary': 'employee_lookup_tool',
            'employee_count': 'employee_lookup_tool',
            
            'leave_lookup': 'leave_read_tool',
            'leave_summary': 'leave_read_tool',
            'leave_count': 'leave_read_tool',
            'leave_trend': 'leave_read_tool',
            
            'absence_lookup': 'absence_lookup_tool',
            'absence_count': 'absence_lookup_tool',
            
            'comparison': 'comparison_tool',
            
            # Write operations
            'attendance_update': 'attendance_update_tool',
            'attendance_create': 'attendance_create_tool',
            
            'leave_create': 'leave_create_tool',
            'leave_update': 'leave_update_tool',
            'leave_cancel': 'leave_cancel_tool',
            'leave_approve': 'leave_approve_tool',
            'leave_deny': 'leave_deny_tool',
        }
        
        # Read vs Write classification
        self.read_intents = {
            'attendance_lookup', 'attendance_summary', 'attendance_count', 'attendance_trend',
            'attendance_intelligence',
            'leave_regularization_intelligence',
            'workforce_intelligence',
            'employee_lookup', 'employee_summary', 'employee_count', 
            'leave_lookup', 'leave_summary', 'leave_count', 'leave_trend',
            'absence_lookup', 'absence_count',
            'comparison', 'unknown'
        }
        
        self.write_intents = {
            'attendance_update', 'attendance_create', 'attendance_delete',
            'leave_create', 'leave_update', 'leave_cancel', 'leave_approve', 'leave_deny',
            'employee_update', 'bulk_attendance_update'
            , 'attendance_force_checkout', 'regularization_create', 'regularization_approve',
            'regularization_reject', 'employee_shift_assign', 'employee_status_update'
        }
        
        # Status normalization mapping
        self.status_mapping = {
            'absent': 'ABSENT',
            'present': 'PRESENT',
            'incomplete': 'INCOMPLETE', 
            'leave': 'LEAVE',
            'checked_in': 'INCOMPLETE',
            'completed': 'PRESENT'
        }
    
    def normalize_intent(self, llm_output: Dict[str, Any], original_query: str = "") -> Dict[str, Any]:
        """
        Normalize LLM output to backend-compatible intent format.
        
        Args:
            llm_output: Raw output from LLM
            original_query: Original user query for fallback processing
            
        Returns:
            Normalized intent with correct source and action_type
        """
        if not isinstance(llm_output, dict):
            raise CopilotError("invalid_intent", "LLM returned invalid intent format")
        
        intent_name = llm_output.get('intent')
        if not intent_name:
            raise CopilotError("invalid_intent", "Missing intent in LLM output")

        if intent_name in self.unsupported_write_intents:
            raise CopilotError("unsupported_write", "That HR Copilot action is not supported yet.")

        # Keep one typed attendance-intelligence intent even when the model
        # selects a legacy attendance read intent but supplies a metric.
        if intent_name in {"attendance_lookup", "attendance_summary", "attendance_trend"} and (
            (llm_output.get("entities") or {}).get("attendance_metric")
        ):
            intent_name = "attendance_intelligence"
        if intent_name in {"leave_lookup", "leave_summary", "leave_trend"} and (
            (llm_output.get("entities") or {}).get("intelligence_metric")
        ):
            intent_name = "leave_regularization_intelligence"
        if intent_name in {"employee_lookup", "employee_summary", "employee_count"} and (
            (llm_output.get("entities") or {}).get("workforce_metric")
        ):
            intent_name = "workforce_intelligence"

        inferred_read = self._infer_read_intelligence(original_query)
        if inferred_read and not self._looks_like_explicit_write(original_query):
            intent_name, inferred_entities = inferred_read
            llm_entities = dict(llm_output.get("entities") or {})
            llm_entities.update(inferred_entities)
            llm_output = {**llm_output, "intent": intent_name, "entities": llm_entities}

        # Keep the LLM as the semantic analyzer, while correcting a clear
        # imperative attendance write if the model returned an unrelated read intent.
        inferred_write = self._infer_attendance_write(original_query)
        if inferred_write:
            intent_name = 'attendance_update'
            llm_entities = dict(llm_output.get('entities') or {})
            for key, value in inferred_write.items():
                # A clear command in the user's words wins over an incorrect
                # enum selected by the language model.
                llm_entities[key] = value
            llm_output = {**llm_output, 'intent': intent_name, 'entities': llm_entities}
        
        # Normalize the intent structure
        normalized = {
            'intent': intent_name,
            'entities': llm_output.get('entities', {}),
            'missing_information': llm_output.get('missing_information', []),
            'ambiguities': llm_output.get('ambiguities', []),
            'confidence': llm_output.get('confidence', 1.0),
            'original_query': original_query
        }
        
        # Deterministically set source based on intent, ignoring LLM's source
        if intent_name in self.intent_source_mapping:
            normalized['source'] = self.intent_source_mapping[intent_name]
        else:
            # Fallback for unknown intents
            normalized['source'] = None
            normalized['intent'] = 'unknown'
        
        # Deterministically set action_type
        if intent_name in self.write_intents:
            normalized['action_type'] = 'write'
            normalized['requires_approval'] = True
        else:
            normalized['action_type'] = 'read'
            normalized['requires_approval'] = False
        
        # Set backend tool
        if intent_name in self.intent_tool_mapping:
            normalized['backend_tool'] = self.intent_tool_mapping[intent_name]
        else:
            normalized['backend_tool'] = None
        
        # Normalize entities
        normalized['entities'] = self._normalize_entities(
            normalized['entities'], 
            intent_name, 
            original_query
        )

        # Small local models sometimes echo a field in missing_information
        # even after extracting that field. Do not ask the user for data we
        # already have; preserve semantic markers such as employee_identity.
        field_aliases = {
            'employee': ('employee_id', 'employee_name', 'employee_email'),
            'employee_name': ('employee_id', 'employee_name', 'employee_email'),
            'employee_email': ('employee_id', 'employee_name', 'employee_email'),
            'date': ('date_range', 'temporal_expression'),
            'attendance_date': ('date_range', 'temporal_expression'),
            'section': ('section',),
            'subsection': ('subsection',),
            'department': ('department',),
            'status': ('target_status', 'attendance_status'),
            'reason': ('reason',),
        }
        normalized['missing_information'] = [
            item for item in normalized['missing_information']
            if item not in field_aliases or not any(normalized['entities'].get(key) for key in field_aliases[item])
        ]

        return normalized

    @staticmethod
    def _looks_like_explicit_write(query: str) -> bool:
        return bool(re.match(r"\s*(?:please\s+)?(?:approve|reject|deny|cancel|create|submit|file|mark|edit|change|update|assign|activate|deactivate|force|reset)\b", query or "", re.IGNORECASE))

    @staticmethod
    def _infer_read_intelligence(query: str):
        """Recover existing typed metrics when a small model selects a legacy read intent."""
        text = (query or "").casefold()
        if re.search(r"\bnot\s+(?:yet\s+)?checked\s*[- ]?in\b", text):
            return "attendance_intelligence", {"attendance_metric": "missing_checkins"}
        if re.search(r"\blate\b|after\s+(?:the\s+)?shift\s+start", text):
            return "attendance_intelligence", {"attendance_metric": "late_employees"}
        if (
            re.search(r"\bhow many hours\b|\bworking hours\b", text)
            or has_ordered_regex_matches(text, r"\bhours did ", r"\bwork\b")
        ):
            return "attendance_intelligence", {"attendance_metric": "working_hours"}
        if re.search(r"\bincomplete\b|forgot(?:ten)?\s+to\s+check\s*[- ]?out", text):
            return "attendance_intelligence", {"attendance_metric": "incomplete_explanation"}
        if re.search(r"\bconsecutive absences?\b|absence streak", text):
            return "attendance_intelligence", {"attendance_metric": "absence_streaks"}
        if (
            has_ordered_regex_matches(text, r"\bcompare\b", r"\b(?:week|month)\b")
            or re.search(r"\bweek\s+(?:over\s+)?week\b", text)
        ):
            return "attendance_intelligence", {"attendance_metric": "period_comparison"}
        if (
            re.search(r"\bleave\s+balance\b|\bremaining leave\b", text)
            or has_ordered_regex_matches(text, r"\bcasual leaves? ", r"\bleft\b")
        ):
            return "leave_regularization_intelligence", {"intelligence_metric": "leave_balance"}
        if re.search(r"\bpending\s+leave\b", text):
            return "leave_regularization_intelligence", {"intelligence_metric": "leave_requests"}
        if re.search(r"\bpending\s+regulari[sz]ation\b", text):
            return "leave_regularization_intelligence", {"intelligence_metric": "regularization_pending"}
        if re.search(r"\bregulari[sz]ation\s+history\b|\battendance\s+(?:was\s+)?corrected\b", text):
            return "leave_regularization_intelligence", {"intelligence_metric": "regularization_history"}
        if (
            re.search(r"\bemployee\s+details?\b", text)
            or _is_find_employee_query(text)
        ):
            return "workforce_intelligence", {"workforce_metric": "employee_details" if "details" in text else "employee_search"}
        if (
            has_ordered_regex_matches(text, r"\bshift\b", r"\bassigned\b")
            or re.search(r"\bassigned\s+shift\b", text)
            or has_ordered_regex_matches(text, r"\bassigned\s+to\b", r"\bshift\b")
            or has_ordered_regex_matches(text, r"\bwhich\s+shift\b", r"\bwork\s+in\b")
        ):
            entities = {"workforce_metric": "shift_assignments"}
            identity = IntentNormalizer._extract_workforce_employee_identity(query)
            if identity:
                entities.update(identity)
            assigned_shift = find_ordered_capture(text, r"\bassigned\s+to\s+", r"\s+shift\b")
            if assigned_shift and re.fullmatch(r"[A-Za-z][A-Za-z .'-]*", assigned_shift):
                entities["shift_name"] = assigned_shift.strip()
            return "workforce_intelligence", entities
        if re.search(r"\bface\s+enrollment\b|\benrolled\s+(?:their\s+)?face\b", text):
            return "workforce_intelligence", {"workforce_metric": "face_enrollment"}
        if re.search(r"\boffice\s+locations?\b", text):
            return "workforce_intelligence", {"workforce_metric": "office_locations"}
        if re.search(r"\bactive\b|\binactive\b", text) and "employee" in text:
            return "workforce_intelligence", {"workforce_metric": "employee_status"}
        if re.search(r"\bconfigured\s+shifts?\b|\ball\s+shifts\b", text):
            return "workforce_intelligence", {"workforce_metric": "shift_configuration"}
        return None

    @staticmethod
    def _extract_workforce_employee_identity(query: str) -> Dict[str, Any]:
        """Preserve an explicit workforce target when Qwen omits it."""
        text = query or ""
        email = find_email_address(text)
        if email:
            return {"employee_email": email}

        patterns = (
            r"\bshift\s+is\s+(?P<name>[A-Za-z][A-Za-z .'-]*?)\s+assigned\b",
            r"\b(?:show|find)\s+(?P<name>[A-Za-z][A-Za-z .'-]*?)\s+(?:'s|’s)\s+(?:current\s+)?shift\b",
            r"\bdoes\s+(?P<name>[A-Za-z][A-Za-z .'-]*?)\s+work\s+in\s+which\s+shift\b",
            r"\bwhich\s+shift\s+does\s+(?P<name>[A-Za-z][A-Za-z .'-]*?)\s+work\s+in\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group("name").strip(" .,'\"?")
                if name:
                    return {"employee_name": name}
        return {}
    
    def _normalize_entities(self, entities: Dict[str, Any], intent: str, query: str) -> Dict[str, Any]:
        """Normalize and validate entities."""
        if not isinstance(entities, dict):
            entities = {}
        
        normalized = entities.copy()
        
        # Normalize attendance status for write operations
        if intent in self.write_intents:
            # Try to extract status from various fields
            target_status = (
                entities.get('target_status') or 
                entities.get('attendance_status') or
                entities.get('status')
            )
            
            # Fallback: extract from query text
            if not target_status and query:
                query_lower = query.lower()
                for word, status in self.status_mapping.items():
                    if word in query_lower:
                        target_status = status
                        break
                if not target_status and re.search(r"\b(?:add|record)\s+attendance\b", query_lower):
                    target_status = "PRESENT"
            
            if target_status:
                # Normalize status
                status_key = str(target_status).casefold()
                if status_key in self.status_mapping:
                    normalized['target_status'] = self.status_mapping[status_key]
                else:
                    normalized['target_status'] = target_status.upper()
        
        # Normalize employee name
        if entities.get('employee_name'):
            # Clean up employee name
            name = str(entities['employee_name']).strip()
            if name:
                normalized['employee_name'] = name

        # Keep identity/date extraction deterministic for common attendance-write
        # phrasing; the LLM sometimes returns the right intent but omits entities.
        if intent in {'attendance_update', 'attendance_create'}:
            if not normalized.get('employee_name') and not normalized.get('employee_email'):
                employee_name = self._extract_attendance_employee_name(query)
                if employee_name:
                    normalized['employee_name'] = employee_name
            if not normalized.get('date_range'):
                target_date = self._extract_attendance_date(query)
                if target_date:
                    normalized['date_range'] = {'start': target_date, 'end': target_date}
        
        # Normalize temporal expressions to date ranges if possible
        temporal_expr = entities.get('temporal_expression')
        if temporal_expr and not entities.get('date_range'):
            # This will be handled by the existing temporal resolution logic
            normalized['temporal_expression'] = temporal_expr
        
        # Clean up empty values
        normalized = {k: v for k, v in normalized.items() if v is not None and v != ""}
        
        return normalized

    @staticmethod
    def _extract_attendance_employee_name(query: str) -> str | None:
        patterns = (
            (r"\b(?:please\s+)?(?:mark|make|set|change|update|correct|add)\s+", r"\s+(?:['’]s\s+)?(?:as\s+)?(?:present|absent|leave|incomplete|attendance|check[ -]?in|check[ -]?out)\b"),
            (r"\b(?:attendance|check[ -]?in|check[ -]?out)\s+(?:for|of)\s+", r"\s+(?:on|for|as|to|with)\b|[,.!?]|$"),
            (r"\b(?:add|record)\s+attendance\s+for\s+", r"\s+(?:on|for|as)\b|[,.!?]|$"),
        )
        for start_pattern, end_pattern in patterns:
            captured_name = find_ordered_capture(query, start_pattern, end_pattern)
            if captured_name is None:
                continue
            name = captured_name.strip(" \t\r\n,.'’\"")
            name = re.sub(r"['’]s$", "", name).strip()
            if name and not re.search(r"\d", name):
                return name
        return None
    @staticmethod
    def _extract_attendance_date(query: str) -> str | None:
        from datetime import datetime
        from django.utils import timezone
        current_year = timezone.localdate().year
        text_lower = query.casefold()
        for word, offset in (("today", 0), ("yesterday", -1), ("tomorrow", 1)):
            if re.search(rf"\b{word}\b", text_lower):
                return (timezone.localdate() + timedelta(days=offset)).isoformat()
        for pattern, date_format in (
            (r"\b\d{4}-\d{2}-\d{2}\b", "%Y-%m-%d"),
            (r"\b\d{1,2}/\d{1,2}/\d{4}\b", "%d/%m/%Y"),
            (r"\b\d{1,2}-\d{1,2}-\d{4}\b", "%d-%m-%Y"),
        ):
            match = re.search(pattern, query)
            if match:
                try:
                    return datetime.strptime(match.group(0), date_format).date().isoformat()
                except ValueError as error:
                    raise CopilotError("invalid_date", "Use a valid calendar date.") from error

        months = {name: index for index, name in enumerate((
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ), 1)}
        month_pattern = "|".join(months)
        for pattern in (
            rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<month>{month_pattern})(?:\s+(?P<year>\d{{4}}))?\b",
            rf"\b(?P<month>{month_pattern})\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(?P<year>\d{{4}}))?\b",
        ):
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                try:
                    return date(int(match.group("year") or current_year), months[match.group("month").casefold()], int(match.group("day"))).isoformat()
                except ValueError as error:
                    raise CopilotError("invalid_date", "Use a valid calendar date.") from error
        return None

    def _infer_attendance_write(self, query: str) -> Dict[str, Any] | None:
        if not query or not re.match(r"\s*(?:please\s+)?(?:mark|make|set|change|update|correct|add|record)\b", query, re.IGNORECASE):
            return None
        lower = query.casefold()
        target_status = None
        for word, status in self.status_mapping.items():
            if re.search(rf"\b{re.escape(word)}\b", lower):
                target_status = status
                break
        if target_status is None and re.search(r"\b(?:add|record)\s+attendance\b", lower):
            target_status = 'PRESENT'
        if target_status is None:
            return None
        entities = {'target_status': target_status}
        employee_name = self._extract_attendance_employee_name(query)
        if employee_name:
            entities['employee_name'] = employee_name
        attendance_date = self._extract_attendance_date(query)
        if attendance_date:
            entities['date_range'] = {'start': attendance_date, 'end': attendance_date}
        return entities

    def validate_normalized_intent(self, normalized_intent: Dict[str, Any]) -> bool:
        """Validate that the normalized intent is properly formed."""
        required_fields = ['intent', 'source', 'action_type', 'entities']
        
        for field in required_fields:
            if field not in normalized_intent:
                raise CopilotError("invalid_intent", f"Missing required field: {field}")
        
        intent_name = normalized_intent['intent']
        source = normalized_intent['source']
        
        # Validate intent-source consistency
        expected_source = self.intent_source_mapping.get(intent_name)
        if expected_source and source != expected_source:
            raise CopilotError(
                "intent_source_mismatch", 
                f"Intent '{intent_name}' expects source '{expected_source}' but got '{source}'"
            )
        
        return True


# Create singleton instance
intent_normalizer = IntentNormalizer()
