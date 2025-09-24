"""Filter classes for API endpoints."""
from __future__ import annotations

import django_filters
from django.db import models

from .models import (
    Appointment,
    HL7Message,
    Notification,
    Observation,
    Patient,
    RiskScore,
)


class PatientFilter(django_filters.FilterSet):
    identifier = django_filters.CharFilter(field_name="primary_identifier", lookup_expr="iexact")
    name = django_filters.CharFilter(method="filter_by_name")
    birthdate = django_filters.DateFilter(field_name="birth_date")
    phone = django_filters.CharFilter(field_name="phone", lookup_expr="icontains")
    email = django_filters.CharFilter(field_name="email", lookup_expr="icontains")

    class Meta:
        model = Patient
        fields = ["identifier", "name", "birthdate", "phone", "email"]

    def filter_by_name(self, queryset, name, value):
        tokens = value.split()
        for token in tokens:
            queryset = queryset.filter(
                models.Q(first_name__icontains=token)
                | models.Q(last_name__icontains=token)
                | models.Q(middle_name__icontains=token)
            )
        return queryset


class ObservationFilter(django_filters.FilterSet):
    patient = django_filters.CharFilter(field_name="patient__resource_id", lookup_expr="iexact")
    code = django_filters.CharFilter(field_name="code", lookup_expr="iexact")
    category = django_filters.CharFilter(field_name="category", lookup_expr="iexact")
    start = django_filters.DateTimeFilter(field_name="effective_time", lookup_expr="gte")
    end = django_filters.DateTimeFilter(field_name="effective_time", lookup_expr="lte")

    class Meta:
        model = Observation
        fields = ["patient", "code", "category", "start", "end"]


class AppointmentFilter(django_filters.FilterSet):
    practitioner = django_filters.CharFilter(field_name="practitioner_reference", lookup_expr="iexact")
    patient = django_filters.CharFilter(field_name="patient__resource_id", lookup_expr="iexact")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    date = django_filters.DateFilter(field_name="start__date")

    class Meta:
        model = Appointment
        fields = ["practitioner", "patient", "status", "date"]


class HL7MessageFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    version = django_filters.CharFilter(field_name="hl7_version", lookup_expr="iexact")

    class Meta:
        model = HL7Message
        fields = ["status", "version"]


class NotificationFilter(django_filters.FilterSet):
    recipient = django_filters.CharFilter(field_name="recipient_id", lookup_expr="iexact")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")

    class Meta:
        model = Notification
        fields = ["recipient", "status"]


class RiskScoreFilter(django_filters.FilterSet):
    patient = django_filters.CharFilter(field_name="patient__resource_id", lookup_expr="iexact")
    risk_type = django_filters.CharFilter(field_name="risk_type", lookup_expr="iexact")

    class Meta:
        model = RiskScore
        fields = ["patient", "risk_type"]
