from django.conf import settings
from django.db import models


class Attendance(models.Model):
    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("INCOMPLETE", "Incomplete"),
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
        events = self.employee.attendance_events.filter(
            timestamp__date=self.date
        ).order_by("timestamp")

        check_in_events = events.filter(event_type="CHECK_IN")
        check_out_events = events.filter(event_type="CHECK_OUT")

        first_check_in = check_in_events.first()
        last_check_in = check_in_events.last()
        last_check_out = check_out_events.last()

        # Update check_in (first CHECK_IN event)
        if first_check_in:
            self.check_in = first_check_in.timestamp
            # Update geolocation from first check-in event if not set
            if not self.check_in_latitude and first_check_in.latitude:
                self.check_in_latitude = first_check_in.latitude
                self.check_in_longitude = first_check_in.longitude
                self.check_in_accuracy = first_check_in.accuracy
                self.check_in_distance = first_check_in.distance

        # Update check_out: only if latest CHECK_OUT comes AFTER latest CHECK_IN
        # If there's a CHECK_IN after the last CHECK_OUT, clear check_out
        if last_check_out and last_check_in:
            if last_check_out.timestamp > last_check_in.timestamp:
                # Check-out is after last check-in, use it
                self.check_out = last_check_out.timestamp
                if not self.check_out_latitude and last_check_out.latitude:
                    self.check_out_latitude = last_check_out.latitude
                    self.check_out_longitude = last_check_out.longitude
                    self.check_out_accuracy = last_check_out.accuracy
                    self.check_out_distance = last_check_out.distance
            else:
                # Check-in is after last check-out, clear check_out
                self.check_out = None
                self.check_out_latitude = None
                self.check_out_longitude = None
                self.check_out_accuracy = None
                self.check_out_distance = None
        elif last_check_out:
            # Only check-out exists, use it
            self.check_out = last_check_out.timestamp
            if not self.check_out_latitude and last_check_out.latitude:
                self.check_out_latitude = last_check_out.latitude
                self.check_out_longitude = last_check_out.longitude
                self.check_out_accuracy = last_check_out.accuracy
                self.check_out_distance = last_check_out.distance

        # Recompute working_duration and status
        if self.check_in and self.check_out:
            events = self.employee.attendance_events.filter(
                timestamp__date=self.date
            ).order_by("timestamp")
            
            check_in_count = events.filter(event_type="CHECK_IN").count()
            check_out_count = events.filter(event_type="CHECK_OUT").count()
            
            # For single IN/OUT pair: use checkout - checkin (existing behavior)
            # For multiple intervals: don't calculate complex breaks yet, 
            # fall back to last_checkout - first_checkin as before
            if check_in_count == 1 and check_out_count == 1:
                self.working_duration = self.check_out - self.check_in
            else:
                # Multiple intervals - keep simple last_checkout - first_checkin
                # (Phase 3 will introduce proper break calculations)
                self.working_duration = self.check_out - self.check_in
            
            # Standard status: PRESENT when both check_in and check_out exist
            self.status = "PRESENT"
        elif self.check_in:
            self.working_duration = None
            self.status = "INCOMPLETE"
        else:
            self.working_duration = None
            # If no events at all and status was INCOMPLETE, keep it
            # Don't override LEAVE status
            if self.status != "LEAVE":
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
        if not self.employee.shift or not self.employee.shift.is_active:
            return None
        
        shift = self.employee.shift
        first_check_in = self.check_in
        
        if not first_check_in:
            return None
        
        # Compare first check-in time with shift start time (same date)
        from datetime import datetime, time
        
        # Safely normalize shift times to datetime.time
        def to_time(t):
            if isinstance(t, time):
                return t
            if isinstance(t, str):
                # Parse HH:MM or HH:MM:SS format
                for fmt in ("%H:%M:%S", "%H:%M"):
                    try:
                        return datetime.strptime(t, fmt).time()
                    except ValueError:
                        continue
                raise ValueError(f"Invalid time format: {t}")
            raise TypeError(f"Cannot convert {type(t)} to time")
        
        shift_start_time = to_time(shift.start_time)
        shift_end_time = to_time(shift.end_time)
        
        shift_start = datetime.combine(self.date, shift_start_time)
        shift_end = datetime.combine(self.date, shift_end_time)
        
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
    correction_type = models.CharField(max_length=50) # 'RESET', 'EDIT'
    reason = models.TextField()
    previous_data = models.JSONField(default=dict)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.correction_type} by {self.admin_user} on {self.attendance}"