"""REST API views for the FHIR Patient Portal."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import filters
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
)
from .serializers import (
    AppointmentSerializer,
    AuditAnomalySerializer,
    AuditEventSerializer,
    AuditExportSerializer,
    HL7BatchSerializer,
    HL7MessageSerializer,
    MLModelVersionSerializer,
    MLTrainingJobSerializer,
    NotificationCampaignSerializer,
    NotificationSerializer,
    NotificationTemplateSerializer,
    ObservationAlertConfigSerializer,
    ObservationSerializer,
    PatientExportSerializer,
    PatientMergeSerializer,
    PatientSerializer,
    PersonalizedAlertSerializer,
    RiskScoreSerializer,
    TelemedicineConsentSerializer,
    TelemedicineMetricSerializer,
    TelemedicineSessionSerializer,
    UserRegistrationSerializer,
    UserRoleAssignSerializer,
    UserRoleSerializer,
    WaitlistEntrySerializer,
    RoleSerializer,
)
from .permissions import ActionPermissionMixin, IsAdmin
from .rbac import ROLE_PERMISSIONS


class UserRegistrationView(APIView):
    """Allow new users to self-register with validation."""

    permission_classes = [permissions.AllowAny]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RoleProtectedModelViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    """Base viewset that wires RBAC to DRF actions."""

    permission_classes = [permissions.IsAuthenticated]
    filterset_class = None

    def perform_create(self, serializer):
        model_class = getattr(serializer.Meta, "model", None)
        if model_class and hasattr(model_class, "created_by"):
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()


class RoleViewSet(RoleProtectedModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    action_permission_map = {
        "list": ("admin", "read"),
        "retrieve": ("admin", "read"),
        "create": ("admin", "assign"),
        "update": ("admin", "assign"),
        "partial_update": ("admin", "assign"),
        "destroy": ("admin", "assign"),
    }


class RoleManagementView(APIView):
    """Assign roles to users."""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = UserRoleAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        roles = serializer.validated_data["roles"]
        effective_date = serializer.validated_data["effective_date"]
        expiry_date = serializer.validated_data.get("expiry_date")
        reason = serializer.validated_data.get("reason", "")
        assignments: List[UserRole] = []
        for role_name in roles:
            role = get_object_or_404(Role, name__iexact=role_name)
            assignment, _ = UserRole.objects.update_or_create(
                user=user,
                role=role,
                defaults={
                    "assigned_by": request.user,
                    "reason": reason,
                    "effective_date": effective_date,
                    "expiry_date": expiry_date,
                },
            )
            assignments.append(assignment)
        return Response(UserRoleSerializer(assignments, many=True).data, status=status.HTTP_201_CREATED)


class HL7MessageViewSet(RoleProtectedModelViewSet):
    queryset = HL7Message.objects.all().order_by("-created_at")
    serializer_class = HL7MessageSerializer
    filterset_class = filters.HL7MessageFilter
    action_permission_map = {
        "list": ("hl7", "read"),
        "retrieve": ("hl7", "read"),
        "ingest": ("hl7", "create"),
        "batch": ("hl7", "create"),
    }

    @action(detail=False, methods=["post"], url_path="ingest")
    def ingest(self, request: Request) -> Response:
        payload = request.data.copy() if hasattr(request.data, "copy") else request.data
        if not isinstance(payload, dict):
            payload = {"raw_message": payload}
        payload.setdefault("message_id", payload.get("messageId") or f"msg-{timezone.now().timestamp()}")
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        message = serializer.save(status="processed", processed_at=timezone.now())
        response = {
            "messageId": message.message_id,
            "correlationId": message.correlation_id,
            "status": message.status,
            "timestamp": message.created_at,
            "errors": message.errors,
        }
        return Response(response, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="parse-status/(?P<message_id>[^/]+)")
    def parse_status(self, request: Request, message_id: str) -> Response:
        message = get_object_or_404(self.get_queryset(), message_id=message_id)
        payload = {
            "messageId": message.message_id,
            "status": message.status,
            "processedAt": message.processed_at,
            "resourcesCreated": len(message.parsed_payload.get("fhirResources", [])),
            "errors": message.errors,
        }
        return Response(payload)

    @action(detail=False, methods=["post"], url_path="batch")
    def batch(self, request: Request) -> Response:
        serializer = HL7BatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = serializer.save(status="partial_success")
        return Response(HL7BatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class PatientViewSet(RoleProtectedModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    filterset_class = filters.PatientFilter
    action_permission_map = {
        "list": ("patients", "read"),
        "retrieve": ("patients", "read"),
        "create": ("patients", "create"),
        "update": ("patients", "update"),
        "partial_update": ("patients", "update"),
        "destroy": ("patients", "delete"),
        "search": ("patients", "read"),
        "merge": ("patients", "merge"),
        "export_patient": ("patients", "export"),
    }

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request: Request) -> Response:
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        entries = [{"resource": item} for item in serializer.data]
        return Response(
            {
                "resourceType": "Bundle",
                "type": "searchset",
                "total": len(entries),
                "entry": entries,
            }
        )

    @action(detail=True, methods=["post"], url_path="merge/(?P<target_id>[^/.]+)")
    def merge(self, request: Request, pk: str, target_id: str) -> Response:
        source = self.get_object()
        target = get_object_or_404(Patient, pk=target_id)
        serializer = PatientMergeSerializer(data={
            "source_patient": source.pk,
            "target_patient": target.pk,
            "reason": request.data.get("reason", "Duplicate records identified"),
            "merge_strategy": request.data.get("mergeStrategy", "keep_latest"),
            "fields": request.data.get("fields", []),
            "audit_reason": request.data.get("auditReason", ""),
            "merged_fields": request.data.get("mergedFields", []),
            "audit_id": request.data.get("auditId", ""),
            "performed_by": request.user.pk if request.user.is_authenticated else None,
        })
        serializer.is_valid(raise_exception=True)
        merge = serializer.save()
        payload = {
            "status": "merged",
            "resultPatientId": target.resource_id,
            "mergedFields": merge.merged_fields,
            "auditId": merge.audit_id,
        }
        return Response(payload)

    @action(detail=True, methods=["get"], url_path="export")
    def export_patient(self, request: Request, pk: str) -> Response:
        patient = self.get_object()
        serializer = PatientExportSerializer(data={
            "patient": patient.pk,
            "format": request.query_params.get("format", "pdf"),
            "include_sections": [
                section for section in request.query_params.get("includeSections", "").split(",") if section
            ],
            "status": "completed",
            "download_url": f"/api/v1/exports/{patient.pk}/download",
            "size": "2MB",
            "expires_at": timezone.now() + timedelta(days=7),
        })
        serializer.is_valid(raise_exception=True)
        export = serializer.save()
        payload = {
            "exportId": f"export-{export.pk}",
            "status": export.status,
            "downloadUrl": export.download_url,
            "format": export.format,
            "size": export.size,
            "expiresAt": export.expires_at,
        }
        return Response(payload)


class ObservationViewSet(RoleProtectedModelViewSet):
    queryset = Observation.objects.select_related("patient")
    serializer_class = ObservationSerializer
    filterset_class = filters.ObservationFilter
    action_permission_map = {
        "list": ("observations", "read"),
        "retrieve": ("observations", "read"),
        "create": ("observations", "create"),
        "update": ("observations", "update"),
        "partial_update": ("observations", "update"),
        "destroy": ("observations", "delete"),
        "trends": ("observations", "trend"),
        "configure_alert": ("observations", "alert"),
    }

    @action(detail=False, methods=["get"], url_path="(?P<patient_id>[^/.]+)/trends")
    def trends(self, request: Request, patient_id: str) -> Response:
        queryset = self.get_queryset().filter(patient__resource_id=patient_id)
        code = request.query_params.get("code")
        if code:
            queryset = queryset.filter(code=code)
        period = request.query_params.get("period", "P30D")
        lookback = 30
        if period.startswith("P") and period.endswith("D"):
            lookback = int(period[1:-1])
        start_time = timezone.now() - timedelta(days=lookback)
        queryset = queryset.filter(effective_time__gte=start_time)
        data_points = []
        values: List[float] = []
        for obs in queryset:
            value = obs.value_quantity.get("value") if isinstance(obs.value_quantity, dict) else None
            if value is not None:
                values.append(value)
            data_points.append(
                {
                    "timestamp": obs.effective_time,
                    "value": value,
                    "status": obs.status,
                }
            )
        payload = {
            "patientId": patient_id,
            "observationType": code,
            "unit": queryset.first().value_quantity.get("unit") if queryset else None,
            "timeRange": {
                "start": start_time,
                "end": timezone.now(),
            },
            "dataPoints": data_points,
            "referenceRanges": {
                "low": min(values) if values else None,
                "high": max(values) if values else None,
            },
        }
        return Response(payload)

    @action(detail=False, methods=["post"], url_path="alerts/configure")
    def configure_alert(self, request: Request) -> Response:
        serializer = ObservationAlertConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        return Response(serializer.to_representation(config), status=status.HTTP_201_CREATED)


class AppointmentViewSet(RoleProtectedModelViewSet):
    queryset = Appointment.objects.select_related("patient")
    serializer_class = AppointmentSerializer
    filterset_class = filters.AppointmentFilter
    action_permission_map = {
        "list": ("appointments", "read"),
        "retrieve": ("appointments", "read"),
        "create": ("appointments", "create"),
        "update": ("appointments", "update"),
        "partial_update": ("appointments", "update"),
        "destroy": ("appointments", "delete"),
        "availability": ("appointments", "read"),
        "waitlist": ("appointments", "create"),
    }

    @action(detail=False, methods=["get"], url_path="availability")
    def availability(self, request: Request) -> Response:
        practitioner = request.query_params.get("practitioner")
        date_str = request.query_params.get("date")
        duration = int(request.query_params.get("duration", "30"))
        if date_str:
            parsed = datetime.fromisoformat(date_str)
            if timezone.is_naive(parsed):
                date = timezone.make_aware(parsed)
            else:
                date = parsed
        else:
            date = timezone.now()
        slots = [
            {
                "start": date.replace(hour=9, minute=0, second=0, microsecond=0),
                "end": date.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(minutes=duration),
                "type": "available",
            },
            {
                "start": date.replace(hour=10, minute=0, second=0, microsecond=0),
                "end": date.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(minutes=duration),
                "type": "tentative",
            },
        ]
        payload = {
            "date": date.date(),
            "practitioner": practitioner,
            "availableSlots": slots,
        }
        return Response(payload)

    @action(detail=True, methods=["post"], url_path="waitlist")
    def waitlist(self, request: Request, pk: str) -> Response:
        appointment = self.get_object()
        patient_identifier = request.data.get("patientId")
        patient_obj = get_object_or_404(Patient, resource_id=patient_identifier)
        serializer = WaitlistEntrySerializer(data={
            "appointment": appointment.pk,
            "patient": patient_obj.pk,
            "preferred_dates": request.data.get("preferredDates", []),
            "preferred_times": request.data.get("preferredTimes", []),
            "priority": request.data.get("priority", "routine"),
            "notification_preferences": request.data.get("notificationPreferences", {}),
        })
        serializer.is_valid(raise_exception=True)
        entry = serializer.save()
        return Response(serializer.to_representation(entry), status=status.HTTP_201_CREATED)


class WaitlistViewSet(RoleProtectedModelViewSet):
    queryset = WaitlistEntry.objects.select_related("appointment", "patient")
    serializer_class = WaitlistEntrySerializer
    action_permission_map = {
        "list": ("appointments", "read"),
        "retrieve": ("appointments", "read"),
    }


class TelemedicineSessionViewSet(RoleProtectedModelViewSet):
    queryset = TelemedicineSession.objects.select_related("appointment")
    serializer_class = TelemedicineSessionSerializer
    action_permission_map = {
        "list": ("telemedicine", "read"),
        "retrieve": ("telemedicine", "read"),
        "create": ("telemedicine", "create"),
    }


class TelemedicineConsentViewSet(RoleProtectedModelViewSet):
    queryset = TelemedicineConsent.objects.select_related("session")
    serializer_class = TelemedicineConsentSerializer
    action_permission_map = {
        "list": ("telemedicine", "read"),
        "create": ("telemedicine", "create"),
    }


class TelemedicineMetricViewSet(RoleProtectedModelViewSet):
    queryset = TelemedicineMetric.objects.select_related("session")
    serializer_class = TelemedicineMetricSerializer
    action_permission_map = {
        "retrieve": ("telemedicine", "read"),
        "list": ("telemedicine", "read"),
    }


class NotificationTemplateViewSet(RoleProtectedModelViewSet):
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    action_permission_map = {
        "list": ("notifications", "read"),
        "retrieve": ("notifications", "read"),
        "create": ("notifications", "create"),
        "update": ("notifications", "update"),
        "partial_update": ("notifications", "update"),
    }


class NotificationViewSet(RoleProtectedModelViewSet):
    queryset = Notification.objects.select_related("template")
    serializer_class = NotificationSerializer
    filterset_class = filters.NotificationFilter
    action_permission_map = {
        "list": ("notifications", "read"),
        "retrieve": ("notifications", "read"),
        "create": ("notifications", "create"),
    }


class NotificationCampaignViewSet(RoleProtectedModelViewSet):
    queryset = NotificationCampaign.objects.select_related("template")
    serializer_class = NotificationCampaignSerializer
    action_permission_map = {
        "list": ("notifications", "read"),
        "retrieve": ("notifications", "read"),
        "create": ("notifications", "create"),
    }


class RiskScoreViewSet(RoleProtectedModelViewSet):
    queryset = RiskScore.objects.select_related("patient")
    serializer_class = RiskScoreSerializer
    filterset_class = filters.RiskScoreFilter
    action_permission_map = {
        "list": ("analytics", "read"),
        "retrieve": ("analytics", "read"),
        "create": ("analytics", "create"),
    }


class MLTrainingJobViewSet(RoleProtectedModelViewSet):
    queryset = MLTrainingJob.objects.all()
    serializer_class = MLTrainingJobSerializer
    action_permission_map = {
        "list": ("analytics", "read"),
        "retrieve": ("analytics", "read"),
        "create": ("analytics", "create"),
    }


class MLModelVersionViewSet(RoleProtectedModelViewSet):
    queryset = MLModelVersion.objects.select_related("training_job")
    serializer_class = MLModelVersionSerializer
    action_permission_map = {
        "list": ("analytics", "read"),
        "retrieve": ("analytics", "read"),
        "create": ("analytics", "create"),
    }


class PersonalizedAlertViewSet(RoleProtectedModelViewSet):
    queryset = PersonalizedAlert.objects.select_related("patient", "model")
    serializer_class = PersonalizedAlertSerializer
    action_permission_map = {
        "list": ("analytics", "read"),
        "retrieve": ("analytics", "read"),
        "create": ("analytics", "create"),
    }


class AuditEventViewSet(RoleProtectedModelViewSet):
    queryset = AuditEvent.objects.all()
    serializer_class = AuditEventSerializer
    action_permission_map = {
        "list": ("audit", "read"),
        "retrieve": ("audit", "read"),
        "create": ("audit", "create"),
    }


class AuditExportViewSet(RoleProtectedModelViewSet):
    queryset = AuditExport.objects.all()
    serializer_class = AuditExportSerializer
    action_permission_map = {
        "list": ("audit", "read"),
        "retrieve": ("audit", "read"),
        "create": ("audit", "export"),
    }


class AuditAnomalyViewSet(RoleProtectedModelViewSet):
    queryset = AuditAnomaly.objects.all()
    serializer_class = AuditAnomalySerializer
    action_permission_map = {
        "list": ("audit", "read"),
        "retrieve": ("audit", "read"),
        "create": ("audit", "create"),
    }


