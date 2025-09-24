"""Validation tests for serializers."""
from __future__ import annotations

from datetime import datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from ..models import Patient
from ..serializers import AppointmentSerializer, PatientSerializer


class PatientSerializerTests(TestCase):
    def test_future_birth_date_invalid(self):
        future = timezone.now().date() + timedelta(days=1)
        serializer = PatientSerializer(data={
            "resource_id": "patient-future",
            "primary_identifier": "MRN-FUT",
            "identifiers": [{"value": "MRN-FUT"}],
            "first_name": "Future",
            "last_name": "Person",
            "gender": "male",
            "birth_date": future,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("birth_date", serializer.errors)


class AppointmentSerializerTests(TestCase):
    def setUp(self) -> None:
        self.patient = Patient.objects.create(
            resource_id="patient-test",
            primary_identifier="MRN-TEST",
            identifiers=[{"value": "MRN-TEST"}],
            first_name="Test",
            last_name="Person",
            gender="male",
            birth_date=timezone.now().date() - timedelta(days=1000),
        )

    def test_end_before_start_invalid(self):
        start = timezone.now() + timedelta(days=1)
        serializer = AppointmentSerializer(data={
            "patient": self.patient.pk,
            "practitioner_reference": "doc-1",
            "status": "booked",
            "service_category": "general",
            "appointment_type": "routine",
            "start": start,
            "end": start - timedelta(hours=1),
            "confirmation_code": "CONF-1",
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("end", serializer.errors)
