"""Database models for the FHIR Patient Portal."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

User = get_user_model()

PHONE_VALIDATOR = RegexValidator(r"^[0-9+\-()\s]{7,20}$", "Enter a valid phone number.")


class TimeStampedModel(models.Model):
    """Abstract base class for created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Role(TimeStampedModel):
    """Application role with a structured permissions map."""

    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:  # pragma: no cover - human readable
        return self.name


class UserProfile(TimeStampedModel):
    """Additional metadata tracked for each user."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=32, blank=True, validators=[PHONE_VALIDATOR])
    date_of_birth = models.DateField(null=True, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    device_info = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:  # pragma: no cover - human readable
        return f"Profile for {self.user}"


class UserRole(TimeStampedModel):
    """Assignment of a role to a user with effective windows."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_assignments")
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_roles",
    )
    reason = models.CharField(max_length=255, blank=True)
    effective_date = models.DateTimeField(default=timezone.now)
    expiry_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "role", "effective_date")
        ordering = ["-effective_date"]

    @property
    def is_active(self) -> bool:
        """Return whether the assignment is active at the current time."""
        now = timezone.now()
        if self.expiry_date and self.expiry_date < now:
            return False
        return self.effective_date <= now


class HL7Batch(TimeStampedModel):
    """Batch of HL7 messages processed together."""

    batch_id = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=32, default="pending")
    total_messages = models.PositiveIntegerField(default=0)
    processed = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    processing_time = models.DurationField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]


class HL7Message(TimeStampedModel):
    """Individual HL7 message ingestion record."""

    message_id = models.CharField(max_length=64, unique=True)
    correlation_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=32, default="received")
    raw_message = models.TextField()
    parsed_payload = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    hl7_version = models.CharField(max_length=16, default="2.5")
    sending_application = models.CharField(max_length=128, blank=True)
    receiving_application = models.CharField(max_length=128, blank=True)
    batch = models.ForeignKey(
        HL7Batch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )

    class Meta:
        ordering = ["-created_at"]


class Patient(TimeStampedModel):
    """Patient demographic information aligned with FHIR."""

    GENDER_CHOICES = (
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
        ("unknown", "Unknown"),
    )

    resource_id = models.CharField(max_length=64, unique=True)
    primary_identifier = models.CharField(max_length=64, unique=True)
    identifiers = models.JSONField(default=list, blank=True)
    first_name = models.CharField(max_length=120)
    middle_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120)
    gender = models.CharField(max_length=32, choices=GENDER_CHOICES)
    birth_date = models.DateField()
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True, validators=[PHONE_VALIDATOR])
    address = models.JSONField(default=dict, blank=True)
    telecom = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patients_created",
    )
    organization_id = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def clean(self) -> None:
        if self.birth_date > timezone.now().date():
            raise models.ValidationError({"birth_date": "Birth date cannot be in the future."})


class PatientMerge(TimeStampedModel):
    """Audit of patient merge operations."""

    source_patient = models.ForeignKey(
        Patient, related_name="merge_sources", on_delete=models.CASCADE
    )
    target_patient = models.ForeignKey(
        Patient, related_name="merge_targets", on_delete=models.CASCADE
    )
    reason = models.CharField(max_length=255)
    merge_strategy = models.CharField(max_length=64, default="keep_latest")
    fields = models.JSONField(default=list, blank=True)
    audit_reason = models.CharField(max_length=255, blank=True)
    merged_fields = models.JSONField(default=list, blank=True)
    audit_id = models.CharField(max_length=64, blank=True)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patient_merges",
    )


class PatientExport(TimeStampedModel):
    """Tracks patient data exports."""

    FORMAT_CHOICES = (
        ("pdf", "PDF"),
        ("fhir", "FHIR"),
        ("cda", "CDA"),
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="exports")
    format = models.CharField(max_length=8, choices=FORMAT_CHOICES)
    include_sections = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=32, default="pending")
    download_url = models.CharField(max_length=255, blank=True)
    size = models.CharField(max_length=32, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)


class Observation(TimeStampedModel):
    """Clinical observations such as vital signs."""

    STATUS_CHOICES = (
        ("final", "Final"),
        ("preliminary", "Preliminary"),
        ("amended", "Amended"),
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="observations")
    resource_id = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)
    category = models.CharField(max_length=64)
    code = models.CharField(max_length=64)
    loinc_code = models.CharField(max_length=64, blank=True)
    effective_time = models.DateTimeField()
    value_quantity = models.JSONField(default=dict, blank=True)
    components = models.JSONField(default=list, blank=True)
    issued = models.DateTimeField(null=True, blank=True)
    performer = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ["-effective_time"]

    def clean(self) -> None:
        if self.effective_time > timezone.now():
            raise models.ValidationError({"effective_time": "Effective time cannot be in the future."})


class ObservationAlertConfig(TimeStampedModel):
    """Threshold-based alert configuration per patient and observation."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="alert_configs")
    observation_code = models.CharField(max_length=64)
    thresholds = models.JSONField(default=dict)
    notification_channels = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("patient", "observation_code")


class Appointment(TimeStampedModel):
    """Patient appointments."""

    STATUS_CHOICES = (
        ("booked", "Booked"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="appointments")
    practitioner_reference = models.CharField(max_length=64)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="booked")
    service_category = models.CharField(max_length=64, blank=True)
    appointment_type = models.CharField(max_length=64, blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    confirmation_code = models.CharField(max_length=32, unique=True)
    location = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start"]
        indexes = [models.Index(fields=["practitioner_reference", "start"])]

    def clean(self) -> None:
        if self.end <= self.start:
            raise models.ValidationError({"end": "End time must be after start time."})
        if self.start < timezone.now():
            raise models.ValidationError({"start": "Start time must be in the future."})


class WaitlistEntry(TimeStampedModel):
    """Appointment waitlist entries."""

    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, related_name="waitlist_entries"
    )
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="waitlist")
    preferred_dates = models.JSONField(default=list, blank=True)
    preferred_times = models.JSONField(default=list, blank=True)
    priority = models.CharField(max_length=32, default="routine")
    notification_preferences = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("appointment", "patient")


class TelemedicineSession(TimeStampedModel):
    """Virtual visit session metadata."""

    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, related_name="telemedicine_sessions"
    )
    session_id = models.CharField(max_length=64, unique=True)
    session_type = models.CharField(max_length=32, default="video_consultation")
    scheduled_start = models.DateTimeField()
    estimated_duration = models.PositiveIntegerField(help_text="Duration in minutes")
    join_urls = models.JSONField(default=dict)
    access_window = models.JSONField(default=dict)
    session_settings = models.JSONField(default=dict)


class TelemedicineConsent(TimeStampedModel):
    """Consent captured for telemedicine sessions."""

    session = models.ForeignKey(
        TelemedicineSession, on_delete=models.CASCADE, related_name="consents"
    )
    user_id = models.CharField(max_length=64)
    consent_type = models.CharField(max_length=64)
    granted = models.BooleanField(default=False)
    timestamp = models.DateTimeField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)


class TelemedicineMetric(TimeStampedModel):
    """Quality metrics for telemedicine sessions."""

    session = models.OneToOneField(
        TelemedicineSession, on_delete=models.CASCADE, related_name="metrics"
    )
    quality_metrics = models.JSONField(default=dict)
    duration_seconds = models.PositiveIntegerField(default=0)
    participants = models.JSONField(default=list)


class NotificationTemplate(TimeStampedModel):
    """Notification templates for multiple channels."""

    name = models.CharField(max_length=64, unique=True)
    channels = models.JSONField(default=dict)
    variables = models.JSONField(default=list, blank=True)


class Notification(TimeStampedModel):
    """Individual notification dispatch record."""

    recipient_id = models.CharField(max_length=64)
    channels = models.JSONField(default=list)
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    data = models.JSONField(default=dict, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=32, default="normal")
    status = models.CharField(max_length=32, default="scheduled")
    channel_statuses = models.JSONField(default=list, blank=True)


class NotificationCampaign(TimeStampedModel):
    """Bulk notification campaign configuration."""

    campaign_name = models.CharField(max_length=128)
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.PROTECT,
        related_name="campaigns",
    )
    recipients = models.JSONField(default=list)
    channels = models.JSONField(default=list)
    scheduled_at = models.DateTimeField()


class RiskScore(TimeStampedModel):
    """Risk scoring results for patients."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="risk_scores")
    risk_type = models.CharField(max_length=64)
    score = models.FloatField(validators=[MinValueValidator(0.0)])
    level = models.CharField(max_length=32)
    confidence = models.FloatField(default=0.0)
    factors = models.JSONField(default=list)
    recommendations = models.JSONField(default=list)
    calculated_at = models.DateTimeField()


class MLTrainingJob(TimeStampedModel):
    """Represents model training pipeline executions."""

    job_id = models.CharField(max_length=64, unique=True)
    model_name = models.CharField(max_length=128)
    model_type = models.CharField(max_length=64)
    algorithm = models.CharField(max_length=64)
    target_variable = models.CharField(max_length=128)
    features = models.JSONField(default=list)
    parameters = models.JSONField(default=dict)
    dataset_info = models.JSONField(default=dict)
    status = models.CharField(max_length=32, default="running")
    progress = models.JSONField(default=dict)


class MLModelVersion(TimeStampedModel):
    """Deployment information for trained models."""

    model_id = models.CharField(max_length=64)
    version = models.CharField(max_length=32)
    description = models.TextField(blank=True)
    training_job = models.ForeignKey(
        MLTrainingJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="model_versions",
    )
    performance_metrics = models.JSONField(default=dict)
    deployment_config = models.JSONField(default=dict)
    status = models.CharField(max_length=32, default="deployed")

    class Meta:
        unique_together = ("model_id", "version")


class PersonalizedAlert(TimeStampedModel):
    """Personalized clinical alerts generated by ML models."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="personalized_alerts")
    model = models.ForeignKey(
        MLModelVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
    )
    risk_assessment = models.JSONField(default=dict)
    recommendations = models.JSONField(default=list)
    fhir_resources = models.JSONField(default=list)


class AuditEvent(TimeStampedModel):
    """Immutable audit log of access events."""

    event_type = models.CharField(max_length=64)
    user_id = models.CharField(max_length=64)
    resource_type = models.CharField(max_length=64)
    resource_id = models.CharField(max_length=64)
    action = models.CharField(max_length=32)
    timestamp = models.DateTimeField()
    session_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict)
    immutable_hash = models.CharField(max_length=128, blank=True)


class AuditExport(TimeStampedModel):
    """Audit export jobs."""

    export_id = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=32, default="processing")
    format = models.CharField(max_length=16, default="csv")
    download_url = models.CharField(max_length=255, blank=True)
    estimated_completion = models.DateTimeField(null=True, blank=True)
    digital_signature = models.TextField(blank=True)


class AuditAnomaly(TimeStampedModel):
    """Detected anomalies in audit trails."""

    period = models.CharField(max_length=16, default="P7D")
    anomalies = models.JSONField(default=list)


class FhirAccessLog(TimeStampedModel):
    """External FHIR gateway requests."""

    request_id = models.CharField(max_length=64, unique=True)
    resource_type = models.CharField(max_length=64)
    resource_id = models.CharField(max_length=64)
    api_key = models.CharField(max_length=64)
    status_code = models.PositiveIntegerField(default=200)
    response_payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(default=timezone.now)


__all__ = [
    "AuditAnomaly",
    "AuditEvent",
    "AuditExport",
    "FhirAccessLog",
    "HL7Batch",
    "HL7Message",
    "MLModelVersion",
    "MLTrainingJob",
    "Notification",
    "NotificationCampaign",
    "NotificationTemplate",
    "Observation",
    "ObservationAlertConfig",
    "Patient",
    "PatientExport",
    "PatientMerge",
    "PersonalizedAlert",
    "Role",
    "RiskScore",
    "TelemedicineConsent",
    "TelemedicineMetric",
    "TelemedicineSession",
    "UserProfile",
    "UserRole",
    "WaitlistEntry",
    "Appointment",
]
