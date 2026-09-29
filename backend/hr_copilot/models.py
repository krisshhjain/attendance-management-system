from django.conf import settings
from django.db import models
import uuid


class CopilotQueryAudit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    question = models.TextField()
    intent = models.JSONField(default=dict)
    query_plan = models.JSONField(default=dict)
    sql = models.TextField(blank=True, default="")
    validation_result = models.CharField(max_length=32, default="not_run")
    scope_result = models.CharField(max_length=32, default="not_run")
    execution_result = models.CharField(max_length=32, default="not_run")
    error_code = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class CopilotConversationContext(models.Model):
    """Session-scoped conversation context for HR Copilot follow-up queries."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    conversation_id = models.CharField(max_length=128)
    context = models.JSONField(default=dict)
    messages = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'conversation_id')
        ordering = ['-updated_at']


class CopilotPendingAction(models.Model):
    """Stores pending write actions that require user approval."""
    
    ACTION_TYPES = [
        ('attendance_update', 'Update Attendance'),
        ('attendance_create', 'Create Attendance'),
        ('attendance_delete', 'Delete Attendance'),
        ('leave_create', 'Create Leave Request'),
        ('leave_update', 'Update Leave Request'),
        ('leave_cancel', 'Cancel Leave Request'),
        ('leave_approve', 'Approve Leave Request'),
        ('leave_deny', 'Deny Leave Request'),
        ('employee_update', 'Update Employee'),
        ('bulk_attendance_update', 'Bulk Update Attendance'),
    ]
    
    STATUS_CHOICES = [
        ('AWAITING_INFORMATION', 'Awaiting Information'),
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved - Executing'),
        ('EXECUTED', 'Successfully Executed'),
        ('CANCELLED', 'Cancelled by User'),
        ('EXPIRED', 'Expired (Timeout)'),
        ('FAILED', 'Execution Failed'),
    ]
    
    # Primary fields
    action_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    session_id = models.CharField(max_length=128, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='copilot_pending_actions')
    conversation_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    
    # Action metadata
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    intent = models.CharField(max_length=100)
    source = models.CharField(max_length=50)
    
    # Target and parameters (JSON stored for flexibility)
    target_data = models.JSONField(help_text="Resolved target entities (employee_id, date, etc)")
    proposed_changes = models.JSONField(help_text="The changes to be made")
    current_state = models.JSONField(null=True, blank=True, help_text="Current state before change")
    
    # Validation and authorization
    validated = models.BooleanField(default=False)
    authorization_scope = models.JSONField(null=True, blank=True)
    validation_errors = models.JSONField(null=True, blank=True)
    
    # Status and lifecycle
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    requires_confirmation = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(help_text="Action expires if not approved by this time")
    
    # Execution results
    execution_result = models.JSONField(null=True, blank=True)
    execution_error = models.TextField(null=True, blank=True)
    
    # Human-readable description
    description = models.TextField(help_text="Human-readable description of the action")
    warning_message = models.TextField(null=True, blank=True, help_text="Warnings about the action")
    
    class Meta:
        db_table = 'hr_copilot_pending_action'
        indexes = [
            models.Index(fields=['user', 'session_id', 'status']),
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['conversation_id']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Action {self.action_id}: {self.action_type} for {self.user.email}"
    
    @property
    def is_expired(self):
        """Check if the action has expired."""
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @property
    def is_executable(self):
        """Check if the action can be executed."""
        return (self.status == 'PENDING' and 
                self.validated and 
                not self.is_expired)
    
    def mark_approved(self):
        """Mark the action as approved and ready for execution."""
        if self.status != 'PENDING':
            raise ValueError(f"Cannot approve action in status {self.status}")
        
        if not self.validated:
            raise ValueError("Cannot approve unvalidated action")
        
        if self.is_expired:
            raise ValueError("Cannot approve expired action")
        
        from django.utils import timezone
        self.status = 'APPROVED'
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_at'])
    
    def mark_executed(self, result=None):
        """Mark the action as successfully executed."""
        from django.utils import timezone
        self.status = 'EXECUTED'
        self.executed_at = timezone.now()
        if result:
            self.execution_result = result
        self.save(update_fields=['status', 'executed_at', 'execution_result'])
    
    def mark_failed(self, error_message):
        """Mark the action as failed during execution."""
        from django.utils import timezone
        self.status = 'FAILED'
        self.executed_at = timezone.now()
        self.execution_error = error_message
        self.save(update_fields=['status', 'executed_at', 'execution_error'])
    
    def cancel(self):
        """Cancel the pending action."""
        if self.status not in ['AWAITING_INFORMATION', 'PENDING']:
            raise ValueError(f"Cannot cancel action in status {self.status}")
        
        self.status = 'CANCELLED'
        self.save(update_fields=['status'])


class CopilotActionAudit(models.Model):
    """Audit trail for all HR Copilot actions (both read and write)."""
    
    # Reference to the pending action (null for read operations)
    pending_action = models.ForeignKey(
        CopilotPendingAction, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='audit_records'
    )
    
    # Basic audit fields
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=128, db_index=True)
    action_type = models.CharField(max_length=50)  # read/write
    intent = models.CharField(max_length=100)
    
    # Operation details
    operation = models.CharField(max_length=100)
    target_description = models.TextField()
    
    # Before/after state for write operations
    previous_state = models.JSONField(null=True, blank=True)
    new_state = models.JSONField(null=True, blank=True)
    
    # Execution metadata
    execution_time_ms = models.IntegerField(null=True, blank=True)
    success = models.BooleanField()
    explicit_confirmation = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)
    
    # Security and authorization
    authorization_scope = models.JSONField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    # Timestamps
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'hr_copilot_action_audit'
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action_type', 'success']),
            models.Index(fields=['session_id']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Audit: {self.action_type} - {self.intent} by {self.user.email}"
