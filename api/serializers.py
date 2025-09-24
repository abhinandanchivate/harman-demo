"""Serializers for the FHIR Patient Portal API."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Appointment,
    AuditAnomaly,
    AuditEvent,
    AuditExport,
    HL7Batch,
    HL7Message,
    MLModelVersion,
    MLTrainingJob,
    Notification,
    NotificationCampaign,
    NotificationTemplate,
    Observation,
    ObservationAlertConfig,
    Patient,
    PatientExport,
    PatientMerge,
    PersonalizedAlert,
    Role,
    RiskScore,
    TelemedicineConsent,
    TelemedicineMetric,
    TelemedicineSession,
    UserRole,
    WaitlistEntry,
    PHONE_VALIDATOR,
)

User = get_user_model()


class RegistrationProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=32, allow_blank=True, required=False)
    date_of_birth = serializers.DateField(required=False)

    def validate_phone(self, value: str) -> str:
        if value:
            PHONE_VALIDATOR(value)
        return value

    def validate_date_of_birth(self, value):  # type: ignore[override]
        if value and value > timezone.now().date():
            raise serializers.ValidationError("date_of_birth cannot be in the future")
        return value


class UserRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    profile = RegistrationProfileSerializer()
    accept_terms = serializers.BooleanField()
    verification_method = serializers.ChoiceField(
        choices=[("email", "email"), ("sms", "sms")],
        default="email",
    )

    password_rules = (
        (re.compile(r"[A-Z]"), "include at least one uppercase letter"),
        (re.compile(r"[a-z]"), "include at least one lowercase letter"),
        (re.compile(r"[0-9]"), "include at least one digit"),
        (re.compile(r"[^A-Za-z0-9]"), "include at least one special character"),
    )

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value: str) -> str:
        missing = [message for pattern, message in self.password_rules if not pattern.search(value)]
        if missing:
            raise serializers.ValidationError(
                "Password must " + ", ".join(missing) + "."
            )
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if attrs.get("password") != attrs.get("confirm_password"):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        if not attrs.get("accept_terms"):
            raise serializers.ValidationError({"accept_terms": "You must accept the terms to register."})
        return attrs

    @transaction.atomic
    def create(self, validated_data: Dict[str, Any]):
        profile_data = validated_data.pop("profile")
        validated_data.pop("confirm_password")
        verification_method = validated_data.pop("verification_method", "email")
        validated_data.pop("accept_terms", None)

        email = validated_data["email"]
        password = validated_data["password"]

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=profile_data.get("first_name", ""),
            last_name=profile_data.get("last_name", ""),
        )

        profile = getattr(user, "profile", None)
        if profile:
            profile.phone = profile_data.get("phone", "")
            profile.date_of_birth = profile_data.get("date_of_birth")
            metadata = profile.device_info or {}
            metadata.update(
                {
                    "verification_method": verification_method,
                    "terms_accepted_at": timezone.now().isoformat(),
                }
            )
            profile.device_info = metadata
            profile.save()

        patient_role = Role.objects.filter(name__iexact="PATIENT").first()
        if patient_role:
            UserRole.objects.create(user=user, role=patient_role, reason="Self registration")

        self.instance = user
        return user

    def to_representation(self, instance: User) -> Dict[str, Any]:
        from .rbac import get_user_roles

        return {
            "id": instance.pk,
            "email": instance.email,
            "roles": get_user_roles(instance),
        }


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "description", "permissions", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserRoleSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)

    class Meta:
        model = UserRole
        fields = [
            "id",
            "user",
            "role",
            "assigned_by",
            "reason",
            "effective_date",
            "expiry_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserRoleAssignSerializer(serializers.Serializer):
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source="user")
    roles = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    effective_date = serializers.DateTimeField(required=False)
    expiry_date = serializers.DateTimeField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True)

    def validate_roles(self, value: List[str]) -> List[str]:
        unknown = [role for role in value if not Role.objects.filter(name__iexact=role).exists()]
        if unknown:
            raise serializers.ValidationError(f"Unknown roles: {', '.join(unknown)}")
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        effective_date = attrs.get("effective_date", timezone.now())
        expiry_date = attrs.get("expiry_date")
        if expiry_date and expiry_date <= effective_date:
            raise serializers.ValidationError("expiry_date must be after effective_date")
        attrs.setdefault("effective_date", effective_date)
        return attrs


class HL7BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = HL7Batch
        fields = [
            "id",
            "batch_id",
            "status",
            "total_messages",
            "processed",
            "failed",
            "processing_time",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class HL7MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = HL7Message
        fields = [
            "id",
            "message_id",
            "correlation_id",
            "status",
            "raw_message",
            "parsed_payload",
            "errors",
            "processed_at",
            "hl7_version",
            "sending_application",
            "receiving_application",
            "batch",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_hl7_version(self, value: str) -> str:
        allowed = {"2.3", "2.4", "2.5", "2.6", "2.7", "2.8"}
        if value not in allowed:
            raise serializers.ValidationError("Unsupported HL7 version")
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if not attrs.get("raw_message"):
            raise serializers.ValidationError({"raw_message": "HL7 message content is required."})
        return attrs


class PatientSerializer(serializers.ModelSerializer):
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id",
            "resource_id",
            "primary_identifier",
            "identifiers",
            "first_name",
            "middle_name",
            "last_name",
            "gender",
            "birth_date",
            "email",
            "phone",
            "address",
            "telecom",
            "created_by",
            "organization_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate_birth_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError("Birth date cannot be in the future.")
        return value

    def validate_email(self, value):
        if value and "@" not in value:
            raise serializers.ValidationError("Enter a valid email address.")
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if not attrs.get("first_name") or not attrs.get("last_name"):
            raise serializers.ValidationError("First and last name are required.")
        if attrs.get("gender") not in {choice[0] for choice in Patient.GENDER_CHOICES}:
            raise serializers.ValidationError({"gender": "Invalid gender value."})
        return attrs


class PatientMergeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientMerge
        fields = [
            "id",
            "source_patient",
            "target_patient",
            "reason",
            "merge_strategy",
            "fields",
            "audit_reason",
            "merged_fields",
            "audit_id",
            "performed_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PatientExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientExport
        fields = [
            "id",
            "patient",
            "format",
            "include_sections",
            "status",
            "download_url",
            "size",
            "expires_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_format(self, value: str) -> str:
        valid = {choice[0] for choice in PatientExport.FORMAT_CHOICES}
        if value not in valid:
            raise serializers.ValidationError("Unsupported export format")
        return value


class ObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Observation
        fields = [
            "id",
            "patient",
            "resource_id",
            "status",
            "category",
            "code",
            "loinc_code",
            "effective_time",
            "value_quantity",
            "components",
            "issued",
            "performer",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_effective_time(self, value):
        if value > timezone.now():
            raise serializers.ValidationError("Effective time cannot be in the future.")
        return value


class ObservationAlertConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObservationAlertConfig
        fields = [
            "id",
            "patient",
            "observation_code",
            "thresholds",
            "notification_channels",
            "active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient",
            "practitioner_reference",
            "status",
            "service_category",
            "appointment_type",
            "start",
            "end",
            "confirmation_code",
            "location",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        start = attrs.get("start")
        end = attrs.get("end")
        if start and start < timezone.now():
            raise serializers.ValidationError({"start": "Start time must be in the future."})
        if start and end and end <= start:
            raise serializers.ValidationError({"end": "End time must be after start time."})
        return attrs


# class WaitlistEntrySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = WaitlistEntry
#         fields = [
#             "id",
#             "appointment",
#             "patient",
#             "preferred_dates",
#             "preferred_times",
#             "priority",
#             "notification_preferences",
#             "created_at",
#             "updated_at",
#         ]
#         read_only_fields = ["id", "created_at", "updated_at"]
class WaitlistEntrySerializer(serializers.ModelSerializer):
    patient = serializers.SlugRelatedField(
        slug_field="resource_id",
        queryset=Patient.objects.all()
    )

    class Meta:
        model = WaitlistEntry
        fields = [
            "id",
            "appointment",
            "patient",
            "preferred_dates",
            "preferred_times",
            "priority",
            "notification_preferences",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TelemedicineSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemedicineSession
        fields = [
            "id",
            "appointment",
            "session_id",
            "session_type",
            "scheduled_start",
            "estimated_duration",
            "join_urls",
            "access_window",
            "session_settings",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_scheduled_start(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("Scheduled start must be in the future.")
        return value


class TelemedicineConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemedicineConsent
        fields = [
            "id",
            "session",
            "user_id",
            "consent_type",
            "granted",
            "timestamp",
            "ip_address",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TelemedicineMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemedicineMetric
        fields = [
            "id",
            "session",
            "quality_metrics",
            "duration_seconds",
            "participants",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ["id", "name", "channels", "variables", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class NotificationSerializer(serializers.ModelSerializer):
    template = NotificationTemplateSerializer(read_only=True)
    template_id = serializers.PrimaryKeyRelatedField(
        queryset=NotificationTemplate.objects.all(), source="template", write_only=True, required=False
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient_id",
            "channels",
            "template",
            "template_id",
            "data",
            "scheduled_at",
            "priority",
            "status",
            "channel_statuses",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class NotificationCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationCampaign
        fields = [
            "id",
            "campaign_name",
            "template",
            "recipients",
            "channels",
            "scheduled_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_scheduled_at(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("Scheduled time must be in the future.")
        return value


class RiskScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskScore
        fields = [
            "id",
            "patient",
            "risk_type",
            "score",
            "level",
            "confidence",
            "factors",
            "recommendations",
            "calculated_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_score(self, value: float) -> float:
        if not 0 <= value <= 1:
            raise serializers.ValidationError("Score must be between 0 and 1.")
        return value


class MLTrainingJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLTrainingJob
        fields = [
            "id",
            "job_id",
            "model_name",
            "model_type",
            "algorithm",
            "target_variable",
            "features",
            "parameters",
            "dataset_info",
            "status",
            "progress",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MLModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLModelVersion
        fields = [
            "id",
            "model_id",
            "version",
            "description",
            "training_job",
            "performance_metrics",
            "deployment_config",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PersonalizedAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalizedAlert
        fields = [
            "id",
            "patient",
            "model",
            "risk_assessment",
            "recommendations",
            "fhir_resources",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "event_type",
            "user_id",
            "resource_type",
            "resource_id",
            "action",
            "timestamp",
            "session_id",
            "ip_address",
            "user_agent",
            "metadata",
            "immutable_hash",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AuditExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditExport
        fields = [
            "id",
            "export_id",
            "status",
            "format",
            "download_url",
            "estimated_completion",
            "digital_signature",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AuditAnomalySerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditAnomaly
        fields = ["id", "period", "anomalies", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
