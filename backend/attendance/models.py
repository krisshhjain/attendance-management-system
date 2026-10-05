from django.conf import settings
from django.db import models
from datetime import datetime, time, timedelta


def attendance_day_end(target_date):
    """Return the exclusive local boundary after an attendance date."""
    from django.utils import timezone

    return timezone.make_aware(
        datetime.combine(target_date + timedelta(days=1), time.min),
        timezone.get_current_timezone(),
    )


def calculate_working_duration(events, now=None, end_at=None):
    """Sum intervals, bounded to the attendance date when ``end_at`` is set."""
    from django.utils import timezone

    if now is None:
        now = timezone.now()
    if end_at is not None and now > end_at:
        now = end_at

    working_duration = timedelta(0)
    open_check_in = None

    for event in events:
        if event.event_type == "CHECK_IN":
            if open_check_in is None:
                open_check_in = event.timestamp
        elif event.event_type == "CHECK_OUT" and open_check_in is not None:
            if event.timestamp >= open_check_in:
                working_duration += event.timestamp - open_check_in
            open_check_in = None

    if open_check_in is not None and now >= open_check_in:
        working_duration += now - open_check_in

    return working_duration


def calculate_completed_working_duration(events):
    """Sum only closed intervals, excluding any currently open interval."""
    working_duration = timedelta(0)
    open_check_in = None

    for event in events:
        if event.event_type == "CHECK_IN":
            if open_check_in is None:
                open_check_in = event.timestamp
        elif event.event_type == "CHECK_OUT" and open_check_in is not None:
            if event.timestamp >= open_check_in:
                working_duration += event.timestamp - open_check_in
            open_check_in = None

    return working_duration


class Attendance(models.Model):
    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("INCOMPLETE", "Incomplete"),
        ("ABSENT", "Absent"),
        ("LEAVE", "Leave"),
    ]

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="INCOMPLETE",
    )
    leave_request = models.ForeignKey(
        "leave_management.LeaveRequest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_records",
    )
    working_duration = models.DurationField(null=True, blank=True)
    check_in_latitude = models.FloatField(null=True, blank=True)
    check_in_longitude = models.FloatField(null=True, blank=True)
    check_in_accuracy = models.FloatField(null=True, blank=True)
    check_in_distance = models.FloatField(null=True, blank=True)
    check_out_latitude = models.FloatField(null=True, blank=True)
    check_out_longitude = models.FloatField(null=True, blank=True)
    check_out_accuracy = models.FloatField(null=True, blank=True)
    check_out_distance = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"],
                name="unique_employee_attendance_per_day",
            )
        ]
        ordering = ["-date", "-check_in"]

    def __str__(self):
        return f"{self.employee} - {self.date}"

    def is_weekend(self):
        """
        Check if the attendance date is a weekend (Saturday=5 or Sunday=6).
        Returns: True if weekend, False otherwise.
        """
        return self.date.weekday() in [5, 6]  # Saturday=5, Sunday=6

    def recompute_from_events(self):
        """
        Recompute check_in, check_out, status, and working_duration from AttendanceEvents.
        First CHECK_IN -> check_in, Latest CHECK_OUT that comes AFTER the last CHECK_IN -> check_out.
        Falls back to existing Attendance fields if no events exist.
        """
        from django.utils import timezone

        # Filter events by matching the date part of timestamp (aware datetime)
        # Use simple __date lookup which works with timezone-aware datetimes
        effective_events = get_effective_attendance_events(self.employee, self.date)
        check_in_events = [event for event in effective_events if event.event_type == "CHECK_IN"]
        check_out_events = [event for event in effective_events if event.event_type == "CHECK_OUT"]

        first_check_in = check_in_events[0] if check_in_events else None
        last_check_out = check_out_events[-1] if check_out_events else None

        # Update check_in (first CHECK_IN event)
        if first_check_in:
            self.check_in = first_check_in.timestamp
            # Update geolocation from first check-in event if not set
            if not self.check_in_latitude and first_check_in.latitude:
                self.check_in_latitude = first_check_in.latitude
                self.check_in_longitude = first_check_in.longitude
                self.check_in_accuracy = first_check_in.accuracy
                self.check_in_distance = first_check_in.distance

        # Keep the latest checkout in the daily summary even when a later
        # check-in opens another interval.
        if last_check_out:
            self.check_out = last_check_out.timestamp
            if not self.check_out_latitude and last_check_out.latitude:
                self.check_out_latitude = last_check_out.latitude
                self.check_out_longitude = last_check_out.longitude
                self.check_out_accuracy = last_check_out.accuracy
                self.check_out_distance = last_check_out.distance

        # Recompute working_duration from each event pair, excluding breaks.
        latest_event = effective_events[-1] if effective_events else None
        if self.check_in:
            self.working_duration = calculate_working_duration(
                effective_events,
                end_at=attendance_day_end(self.date),
            )
            self.status = "INCOMPLETE" if latest_event and latest_event.event_type == "CHECK_IN" else "PRESENT"
        else:
            self.working_duration = None
            # If no events at all and status was INCOMPLETE, keep it
            # Don't override explicit non-attendance statuses.
            if self.status not in {"LEAVE", "ABSENT"}:
                self.status = "INCOMPLETE"

        self.save(update_fields=[
            "check_in", "check_out", "status", "working_duration",
            "check_in_latitude", "check_in_longitude", "check_in_accuracy",
            "check_in_distance", "check_out_latitude", "check_out_longitude",
            "check_out_accuracy", "check_out_distance", "updated_at"
        ])

    def get_shift_adherence(self):
        """
        Compute shift adherence status based on first check-in vs shift start.
        Returns: "ON_TIME", "LATE", or None (if no shift/check_in).
        This is a derived status separate from the core Attendance.status.
        """
        # If no shift assigned, return None
        effective_shift = self.employee.get_effective_shift()
        if not effective_shift or not effective_shift.is_active:
            return None
        
        shift = effective_shift
        first_check_in = self.check_in
        
        if not first_check_in:
            return None
        
        # Compare first check-in time with shift start time (same date)
        from datetime import datetime, time
        
        shift_start = datetime.combine(self.date, shift.start_time)
        shift_end = datetime.combine(self.date, shift.end_time)
        
        # Make timezone-aware if needed
        from django.utils import timezone
        if timezone.is_naive(shift_start):
            shift_start = timezone.make_aware(shift_start)
        if timezone.is_naive(shift_end):
            shift_end = timezone.make_aware(shift_end)
        
        # Allow 5-minute grace period
        grace_period = 5 * 60  # seconds
        
        if first_check_in <= shift_start + timezone.timedelta(seconds=grace_period):
            return "ON_TIME"
        else:
            return "LATE"

        self.save(update_fields=[
            "check_in", "check_out", "status", "working_duration",
            "check_in_latitude", "check_in_longitude", "check_in_accuracy",
            "check_in_distance", "check_out_latitude", "check_out_longitude",
            "check_out_accuracy", "check_out_distance", "updated_at"
        ])

        return self

    @classmethod
    def get_or_create_for_date(cls, employee, date):
        """Atomically get or create attendance record for employee/date."""
        from django.db import transaction
        with transaction.atomic():
            attendance, created = cls.objects.select_for_update().get_or_create(
                employee=employee,
                date=date,
            )
            return attendance, created


class Shift(models.Model):
    EMPLOYMENT_TYPES = [
        ("PERMANENT", "Permanent"),
        ("CONTRACT", "Contract"),
        ("INTERN", "Intern"),
    ]
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_TYPES,
        blank=True,
        default="",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        indexes = [
            models.Index(fields=["employment_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class AttendanceEvent(models.Model):
    EVENT_TYPES = [
        ("CHECK_IN", "Check In"),
        ("CHECK_OUT", "Check Out"),
    ]
    SOURCE_CHOICES = [
        ("MOBILE", "Mobile App"),
        ("KIOSK", "Kiosk"),
        ("ADMIN", "Admin Override"),
        ("FACE_WEB", "Facial Web"),
    ]

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="attendance_events",
    )
    correction = models.ForeignKey(
        "AttendanceCorrection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_events",
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_events",
    )
    timestamp = models.DateTimeField()
    event_type = models.CharField(max_length=10, choices=EVENT_TYPES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="MOBILE")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)
    distance = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["employee", "timestamp"]),
            models.Index(fields=["employee", "event_type", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.employee} - {self.event_type} at {self.timestamp}"


def get_effective_attendance_events(employee, target_date):
    """Return the events that currently define one attendance date.

    Historical events are never deleted. Once a correction-linked event
    exists, only events from the latest correction remain authoritative among
    correction events; unlinked operational/admin events remain available for
    the counterpart of a partial correction.
    """
    event_rows = list(
        employee.attendance_events.filter(timestamp__date=target_date)
        .select_related("correction")
        .order_by("timestamp", "id")
    )
    correction_ids = {event.correction_id for event in event_rows if event.correction_id}
    corrections = list(
        AttendanceCorrection.objects.filter(
            attendance__employee=employee,
            attendance__date=target_date,
        ).order_by("timestamp", "id")
    )
    latest_correction = corrections[-1] if corrections else None
    latest_correction_id = latest_correction.id if latest_correction else None

    if (
        latest_correction is not None
        and latest_correction.previous_data.get("effective_event_mode") == "REPLACE"
        and not latest_correction.attendance_events.exists()
    ):
        return []

    if correction_ids:
        active_correction_events = [
            event for event in event_rows
            if event.correction_id == latest_correction_id
        ]
        unlinked_events = [event for event in event_rows if event.correction_id is None]
        corrected_types = {event.event_type for event in active_correction_events}
        effective_events = [
            event for event in unlinked_events
            if event.source == "ADMIN" or event.event_type not in corrected_types
        ]
        effective_events.extend(active_correction_events)
        return sorted(effective_events, key=lambda event: (event.timestamp, event.id))

    admin_event_types = {
        event.event_type for event in event_rows if event.source == "ADMIN"
    }
    return [
        event for event in event_rows
        if event.source == "ADMIN" or event.event_type not in admin_event_types
    ]


class AttendanceAuditLog(models.Model):
    EVENT_TYPES = [
        ("CHECK_IN", "Check In"),
        ("CHECK_OUT", "Check Out"),
        ("ENROLLMENT", "Enrollment"),
    ]
    STATUS_CHOICES = [
        ("SUCCESS", "Success"),
        ("FAILED_NO_FACE", "Failed - No Face"),
        ("FAILED_MULTI_FACE", "Failed - Multiple Faces"),
        ("FAILED_UNKNOWN", "Failed - Unknown Identity"),
        ("FAILED_ERROR", "Failed - Error"),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    distance = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    # Optional: we could add a snapshot ImageField here in the future
    
    def __str__(self):
        return f"{self.event_type} - {self.status} at {self.timestamp}"


class AttendanceCorrection(models.Model):
    attendance = models.ForeignKey(
        Attendance,
        on_delete=models.SET_NULL,
        null=True,
        related_name="corrections"
    )
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    correction_type = models.CharField(max_length=50) # 'RESET', 'EDIT', 'REGULARIZATION'
    reason = models.TextField()
    previous_data = models.JSONField(default=dict)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.correction_type} by {self.admin_user} on {self.attendance}"


class RegularizationRequest(models.Model):
    REQUEST_TYPES = [
        ("FORGOT_CHECK_IN", "Forgot Check-In"),
        ("FORGOT_CHECK_OUT", "Forgot Check-Out"),
        ("INCORRECT_ATTENDANCE", "Incorrect Attendance"),
        ("SYSTEM_ISSUE", "System Issue"),
    ]
    
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]
    
    # Primary fields
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="regularization_requests",
    )
    attendance_date = models.DateField()
    request_type = models.CharField(max_length=30, choices=REQUEST_TYPES)
    
    # Existing attendance (before correction)
    existing_check_in = models.DateTimeField(null=True, blank=True)
    existing_check_out = models.DateTimeField(null=True, blank=True)
    
    # Requested attendance (after correction)
    requested_check_in = models.DateTimeField(null=True, blank=True)
    requested_check_out = models.DateTimeField(null=True, blank=True)

    # Final times applied by the reviewer; these can differ from the request.
    approved_check_in = models.DateTimeField(null=True, blank=True)
    approved_check_out = models.DateTimeField(null=True, blank=True)
    
    # Request details
    reason = models.TextField()
    description = models.TextField(blank=True, default="")
    
    # Status and review
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regularization_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Link to resulting attendance correction (after approval)
    attendance_correction = models.ForeignKey(
        AttendanceCorrection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regularization_request",
    )
    PERIOD_TYPES = [("DAY", "Day"), ("WEEK", "Week"), ("MONTH", "Month")]
    period_type = models.CharField(max_length=10, choices=PERIOD_TYPES, default="DAY")
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    attachment = models.URLField(max_length=1000, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "attendance_date", "status"],
                condition=models.Q(status="PENDING"),
                name="unique_pending_regularization_per_employee_per_date",
            )
        ]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["attendance_date"]),
            models.Index(fields=["reviewed_by", "reviewed_at"]),
        ]

    def __str__(self):
        return f"Regularization: {self.employee} - {self.attendance_date} ({self.status})"
    
    def clean(self):
        """Validate the regularization request."""
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        import datetime
        
        # Validate 48-hour rule or current week rule
        if self.attendance_date:
            reference_date = timezone.localtime(self.created_at).date() if self.id and self.created_at else timezone.localdate()
            if self.attendance_date > reference_date:
                raise ValidationError("Regularization requests are not allowed for future dates.")
                
            if self.period_type in ["WEEK", "MONTH"]:
                week_start = reference_date - datetime.timedelta(days=reference_date.weekday())
                if self.attendance_date < week_start:
                    raise ValidationError(
                        "Multi-day regularization requests are only allowed for dates in the current calendar week."
                    )
            else:
                max_allowed_date = reference_date - datetime.timedelta(days=2)
                
                if self.attendance_date < max_allowed_date:
                    raise ValidationError(
                        "Regularization requests are only allowed within 48 hours of the attendance date."
                    )
        
        # Validate requested times are logical
        if self.requested_check_in and self.requested_check_out:
            if self.requested_check_out <= self.requested_check_in:
                raise ValidationError(
                    "Requested check-out time must be after check-in time."
                )
        
        # Validate that requested times are on the correct date
        if self.requested_check_in and self.attendance_date:
            if self.requested_check_in.date() != self.attendance_date:
                raise ValidationError(
                    "Requested check-in time must be on the attendance date."
                )
        
        if self.requested_check_out and self.attendance_date:
            if self.requested_check_out.date() != self.attendance_date:
                raise ValidationError(
                    "Requested check-out time must be on the attendance date."
                )
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.clean()
        super().save(*args, **kwargs)
    
    @property
    def is_within_48_hours(self):
        """Check if the request is eligible based on the 48-hour or current-week window."""
        from django.utils import timezone
        import datetime
        
        reference_date = timezone.localtime(self.created_at).date() if self.id and self.created_at else timezone.localdate()
        if self.attendance_date > reference_date:
            return False
            
        if self.period_type in ["WEEK", "MONTH"]:
            week_start = reference_date - datetime.timedelta(days=reference_date.weekday())
            return self.attendance_date >= week_start
            
        cutoff_date = reference_date - datetime.timedelta(days=2)
        return self.attendance_date >= cutoff_date
    
    @property
    def can_be_processed(self):
        """Check if the request can be approved or rejected."""
        return self.status == "PENDING" and self.is_within_48_hours
    
    def approve(
        self,
        reviewed_by_user,
        apply_correction=True,
        approved_check_in=None,
        approved_check_out=None,
    ):
        """
        Approve the regularization request and optionally apply the correction.
        
        Args:
            reviewed_by_user: User who is approving the request
            apply_correction: Whether to apply the attendance correction (default: True)
        
        Returns:
            AttendanceCorrection instance if correction was applied, None otherwise
        """
        from django.utils import timezone
        from django.db import transaction
        
        if self.status != "PENDING":
            raise ValueError(f"Cannot approve request with status {self.status}")
        
        if not self.is_within_48_hours:
            raise ValueError("Cannot approve request outside 48-hour window")
        
        final_check_in = approved_check_in
        if final_check_in is None:
            final_check_in = self.requested_check_in or self.existing_check_in
        final_check_out = approved_check_out
        if final_check_out is None:
            final_check_out = self.requested_check_out or self.existing_check_out

        if final_check_in and final_check_out and final_check_out <= final_check_in:
            raise ValueError("Final check-out time must be after final check-in time.")

        # Only explicitly corrected fields become correction-linked events.
        # The other final value is retained for request metadata and is read
        # from the historical counterpart during effective-event selection.
        correction_check_in = approved_check_in if approved_check_in is not None else self.requested_check_in
        correction_check_out = approved_check_out if approved_check_out is not None else self.requested_check_out

        with transaction.atomic():
            # Update request status
            self.status = "APPROVED"
            self.reviewed_by = reviewed_by_user
            self.reviewed_at = timezone.now()
            self.approved_check_in = final_check_in
            self.approved_check_out = final_check_out
            self.save(update_fields=[
                "status", "reviewed_by", "reviewed_at",
                "approved_check_in", "approved_check_out", "updated_at",
            ])

            if apply_correction:
                return self._apply_attendance_correction(
                    reviewed_by_user,
                    final_check_in,
                    final_check_out,
                    correction_check_in=correction_check_in,
                    correction_check_out=correction_check_out,
                )
        
        return None
    
    def reject(self, reviewed_by_user, rejection_reason):
        """
        Reject the regularization request.
        
        Args:
            reviewed_by_user: User who is rejecting the request
            rejection_reason: Reason for rejection
        """
        from django.utils import timezone
        
        if self.status != "PENDING":
            raise ValueError(f"Cannot reject request with status {self.status}")
        
        self.status = "REJECTED"
        self.reviewed_by = reviewed_by_user
        self.reviewed_at = timezone.now()
        self.rejection_reason = rejection_reason
        self.save(update_fields=[
            "status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"
        ])
    
    def _apply_attendance_correction(
        self,
        reviewed_by_user,
        final_check_in,
        final_check_out,
        correction_check_in=None,
        correction_check_out=None,
    ):
        """
        Apply the regularization correction to attendance records.
        
        This method:
        1. Gets or creates the Attendance record for the date
        2. Stores the previous state
        3. Creates corrective AttendanceEvents with source='ADMIN'
        4. Recomputes the attendance summary
        5. Creates an AttendanceCorrection audit record
        
        Returns:
            AttendanceCorrection instance
        """
        from django.db import transaction
        
        with transaction.atomic():
            # Get or create attendance record
            attendance, created = Attendance.get_or_create_for_date(
                employee=self.employee,
                date=self.attendance_date
            )
            
            # Store previous state for audit
            previous_data = {
                "check_in": attendance.check_in.isoformat() if attendance.check_in else None,
                "check_out": attendance.check_out.isoformat() if attendance.check_out else None,
                "status": attendance.status,
                "working_duration": str(attendance.working_duration) if attendance.working_duration else None,
            }
            
            # Create audit record
            correction = AttendanceCorrection.objects.create(
                attendance=attendance,
                admin_user=reviewed_by_user,
                correction_type="REGULARIZATION",
                reason=f"Regularization approved: {self.reason}",
                previous_data=previous_data,
            )

            # Create corrective events linked to this exact correction.
            self._create_correction_events(
                final_check_in,
                final_check_out,
                correction=correction,
                correction_check_in=correction_check_in,
                correction_check_out=correction_check_out,
            )

            # Recompute attendance from effective events.
            attendance.recompute_from_events()
            
            # Link the correction to this request
            self.attendance_correction = correction
            self.save(update_fields=["attendance_correction", "updated_at"])
            
            return correction
    
    def _create_correction_events(
        self,
        check_in,
        check_out,
        correction,
        correction_check_in=None,
        correction_check_out=None,
    ):
        """
        Create corrective AttendanceEvents based on the regularization request.
        
        This preserves the event-based architecture by creating new events
        with source='ADMIN' rather than directly modifying attendance summaries.
        """
        # Get employee's effective shift for the date
        shift = self.employee.get_effective_shift()
        
        # Create check-in event if requested
        if correction_check_in:
            AttendanceEvent.objects.create(
                employee=self.employee,
                shift=shift,
                timestamp=correction_check_in,
                event_type="CHECK_IN",
                source="ADMIN",
                correction=correction,
            )
        
        # Create check-out event if requested
        if correction_check_out:
            AttendanceEvent.objects.create(
                employee=self.employee,
                shift=shift,
                timestamp=correction_check_out,
                event_type="CHECK_OUT",
                source="ADMIN",
                correction=correction,
            )


class RegularizationRequestDay(models.Model):
    """One affected attendance date within a grouped regularization request."""
    request = models.ForeignKey(
        RegularizationRequest,
        on_delete=models.CASCADE,
        related_name="days",
    )
    attendance_date = models.DateField()
    request_type = models.CharField(max_length=30, choices=RegularizationRequest.REQUEST_TYPES)
    existing_check_in = models.DateTimeField(null=True, blank=True)
    existing_check_out = models.DateTimeField(null=True, blank=True)
    requested_check_in = models.DateTimeField(null=True, blank=True)
    requested_check_out = models.DateTimeField(null=True, blank=True)
    approved_check_in = models.DateTimeField(null=True, blank=True)
    approved_check_out = models.DateTimeField(null=True, blank=True)
    reason = models.TextField()
    description = models.TextField(blank=True, default="")
    attendance_correction = models.ForeignKey(
        AttendanceCorrection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regularization_request_days",
    )

    class Meta:
        ordering = ["attendance_date"]
        constraints = [
            models.UniqueConstraint(fields=["request", "attendance_date"], name="unique_regularization_request_day")
        ]

    def __str__(self):
        return f"Regularization day: {self.request_id} - {self.attendance_date}"
class OfficeLocation(models.Model):
    name = models.CharField(max_length=255, unique=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius_meters = models.FloatField(default=150.0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.latitude}, {self.longitude})"


class RegularizationQuotaPolicy(models.Model):
    """Application-wide request limits configured by an app superuser."""
    weekly_limit = models.PositiveSmallIntegerField(default=1)
    monthly_limit = models.PositiveSmallIntegerField(default=4)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regularization_quota_policy_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Regularization quota policy"
        verbose_name_plural = "Regularization quota policy"

    @classmethod
    def get_solo(cls):
        policy, _ = cls.objects.get_or_create(pk=1)
        return policy

    def __str__(self):
        return f"Regularization limits: {self.weekly_limit}/week, {self.monthly_limit}/month"
