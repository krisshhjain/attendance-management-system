# Generated migration for HR Copilot pending actions

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("hr_copilot", "0002_copilotconversationcontext"),
    ]

    operations = [
        # created_at does not exist in the existing
        # copilotconversationcontext table, so add it here.
        migrations.AddField(
            model_name="copilotconversationcontext",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),

        # updated_at is intentionally NOT added here.
        # It already exists in the database from migration 0002.

        migrations.CreateModel(
            name="CopilotPendingAction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "action_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                    ),
                ),
                (
                    "session_id",
                    models.CharField(
                        db_index=True,
                        max_length=128,
                    ),
                ),
                (
                    "conversation_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        max_length=128,
                        null=True,
                    ),
                ),
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            (
                                "attendance_update",
                                "Update Attendance",
                            ),
                            (
                                "attendance_create",
                                "Create Attendance",
                            ),
                            (
                                "attendance_delete",
                                "Delete Attendance",
                            ),
                            (
                                "leave_create",
                                "Create Leave Request",
                            ),
                            (
                                "leave_update",
                                "Update Leave Request",
                            ),
                            (
                                "leave_cancel",
                                "Cancel Leave Request",
                            ),
                            (
                                "leave_approve",
                                "Approve Leave Request",
                            ),
                            (
                                "leave_deny",
                                "Deny Leave Request",
                            ),
                            (
                                "employee_update",
                                "Update Employee",
                            ),
                            (
                                "bulk_attendance_update",
                                "Bulk Update Attendance",
                            ),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "intent",
                    models.CharField(max_length=100),
                ),
                (
                    "source",
                    models.CharField(max_length=50),
                ),
                (
                    "target_data",
                    models.JSONField(
                        help_text=(
                            "Resolved target entities "
                            "(employee_id, date, etc)"
                        ),
                    ),
                ),
                (
                    "proposed_changes",
                    models.JSONField(
                        help_text="The changes to be made",
                    ),
                ),
                (
                    "current_state",
                    models.JSONField(
                        blank=True,
                        help_text="Current state before change",
                        null=True,
                    ),
                ),
                (
                    "validated",
                    models.BooleanField(default=False),
                ),
                (
                    "authorization_scope",
                    models.JSONField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "validation_errors",
                    models.JSONField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            (
                                "PENDING",
                                "Pending Approval",
                            ),
                            (
                                "APPROVED",
                                "Approved - Executing",
                            ),
                            (
                                "EXECUTED",
                                "Successfully Executed",
                            ),
                            (
                                "CANCELLED",
                                "Cancelled by User",
                            ),
                            (
                                "EXPIRED",
                                "Expired (Timeout)",
                            ),
                            (
                                "FAILED",
                                "Execution Failed",
                            ),
                        ],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                (
                    "requires_confirmation",
                    models.BooleanField(default=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "approved_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "executed_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        help_text=(
                            "Action expires if not approved "
                            "by this time"
                        ),
                    ),
                ),
                (
                    "execution_result",
                    models.JSONField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "execution_error",
                    models.TextField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        help_text=(
                            "Human-readable description "
                            "of the action"
                        ),
                    ),
                ),
                (
                    "warning_message",
                    models.TextField(
                        blank=True,
                        help_text="Warnings about the action",
                        null=True,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="copilot_pending_actions",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "db_table": "hr_copilot_pending_action",
                "ordering": ["-created_at"],
            },
        ),

        migrations.CreateModel(
            name="CopilotActionAudit",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "session_id",
                    models.CharField(
                        db_index=True,
                        max_length=128,
                    ),
                ),
                (
                    "action_type",
                    models.CharField(max_length=50),
                ),
                (
                    "intent",
                    models.CharField(max_length=100),
                ),
                (
                    "operation",
                    models.CharField(max_length=100),
                ),
                (
                    "target_description",
                    models.TextField(),
                ),
                (
                    "previous_state",
                    models.JSONField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "new_state",
                    models.JSONField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "execution_time_ms",
                    models.IntegerField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "success",
                    models.BooleanField(),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "authorization_scope",
                    models.JSONField(),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "user_agent",
                    models.TextField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "timestamp",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "pending_action",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="audit_records",
                        to="hr_copilot.copilotpendingaction",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "db_table": "hr_copilot_action_audit",
                "ordering": ["-timestamp"],
            },
        ),

        migrations.AddIndex(
            model_name="copilotpendingaction",
            index=models.Index(
                fields=[
                    "user",
                    "session_id",
                    "status",
                ],
                name="hr_copilot_pending_action_user_id_c24b4e_idx",
            ),
        ),

        migrations.AddIndex(
            model_name="copilotpendingaction",
            index=models.Index(
                fields=[
                    "status",
                    "expires_at",
                ],
                name="hr_copilot_pending_action_status_67a1f8_idx",
            ),
        ),

        migrations.AddIndex(
            model_name="copilotpendingaction",
            index=models.Index(
                fields=["conversation_id"],
                name="hr_copilot_pending_action_convers_930db0_idx",
            ),
        ),

        migrations.AddIndex(
            model_name="copilotactionaudit",
            index=models.Index(
                fields=[
                    "user",
                    "timestamp",
                ],
                name="hr_copilot_action_audit_user_id_c36a99_idx",
            ),
        ),

        migrations.AddIndex(
            model_name="copilotactionaudit",
            index=models.Index(
                fields=[
                    "action_type",
                    "success",
                ],
                name="hr_copilot_action_audit_action__6c00c4_idx",
            ),
        ),

        migrations.AddIndex(
            model_name="copilotactionaudit",
            index=models.Index(
                fields=["session_id"],
                name="hr_copilot_action_audit_session_7026f0_idx",
            ),
        ),
    ]