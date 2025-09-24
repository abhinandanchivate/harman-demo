"""URL routing for the API application."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .auth import CustomTokenObtainPairView, CustomTokenRefreshView, MeAPIView
from .views import (
    AppointmentViewSet,
    AuditAnomalyViewSet,
    AuditEventViewSet,
    AuditExportViewSet,
    HL7MessageViewSet,
    MLModelVersionViewSet,
    MLTrainingJobViewSet,
    NotificationCampaignViewSet,
    NotificationTemplateViewSet,
    NotificationViewSet,
    ObservationViewSet,
    PatientViewSet,
    PersonalizedAlertViewSet,
    RiskScoreViewSet,
    RoleManagementView,
    RoleViewSet,
    TelemedicineConsentViewSet,
    TelemedicineMetricViewSet,
    TelemedicineSessionViewSet,
    UserRegistrationView,
    WaitlistViewSet,
)

router = DefaultRouter()
router.register(r"v1/hl7-parser", HL7MessageViewSet, basename="hl7-parser")
router.register(r"v1/patients", PatientViewSet, basename="patients")
router.register(r"v1/observations", ObservationViewSet, basename="observations")
router.register(r"v1/appointments", AppointmentViewSet, basename="appointments")
router.register(r"v1/waitlist", WaitlistViewSet, basename="waitlist")
router.register(r"v1/telemedicine/sessions", TelemedicineSessionViewSet, basename="telemedicine-sessions")
router.register(r"v1/telemedicine/consents", TelemedicineConsentViewSet, basename="telemedicine-consents")
router.register(r"v1/telemedicine/metrics", TelemedicineMetricViewSet, basename="telemedicine-metrics")
router.register(r"v1/notifications/templates", NotificationTemplateViewSet, basename="notification-templates")
router.register(r"v1/notifications/campaigns", NotificationCampaignViewSet, basename="notification-campaigns")
router.register(r"v1/notifications", NotificationViewSet, basename="notifications")
router.register(r"v1/analytics/risk-scores", RiskScoreViewSet, basename="risk-scores")
router.register(r"v1/analytics/training-jobs", MLTrainingJobViewSet, basename="training-jobs")
router.register(r"v1/analytics/model-versions", MLModelVersionViewSet, basename="model-versions")
router.register(r"v1/analytics/alerts", PersonalizedAlertViewSet, basename="personalized-alerts")
router.register(r"v1/audit/events", AuditEventViewSet, basename="audit-events")
router.register(r"v1/audit/exports", AuditExportViewSet, basename="audit-exports")
router.register(r"v1/audit/anomalies", AuditAnomalyViewSet, basename="audit-anomalies")
router.register(r"v1/admin/roles", RoleViewSet, basename="roles")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeAPIView.as_view(), name="auth_me"),
    path("auth/register/", UserRegistrationView.as_view(), name="auth_register"),
    path("admin/users/assign-role/", RoleManagementView.as_view(), name="assign_role"),
]
