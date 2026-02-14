"""Tests for on-call scheduling and escalation logic."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.oncall import (
    find_escalation_policy,
    get_current_oncall,
    resolve_escalation_targets,
)
from backend.models.oncall import (
    EscalationPolicy,
    OnCallOverride,
    OnCallSchedule,
    RotationType,
    ServiceEscalationMapping,
)
from backend.schemas import (
    EscalationPolicyCreate,
    EscalationPolicyResponse,
    EscalationPolicyUpdate,
    OnCallCurrentResponse,
    OnCallOverrideCreate,
    OnCallOverrideResponse,
    OnCallScheduleCreate,
    OnCallScheduleListResponse,
    OnCallScheduleResponse,
    OnCallScheduleUpdate,
    PolicyListResponse,
    ServiceMappingCreate,
    ServiceMappingResponse,
)


# ─── Schema Validation Tests ─────────────────────────────


class TestOnCallSchemas:
    def test_schedule_create_defaults(self):
        s = OnCallScheduleCreate(name="Primary")
        assert s.timezone == "UTC"
        assert s.rotation_type == "weekly"
        assert s.handoff_time == "09:00"
        assert s.rotation_interval_days == 7
        assert s.members == []
        assert s.is_active is True

    def test_schedule_create_custom(self):
        s = OnCallScheduleCreate(
            name="Custom Rotation",
            timezone="America/New_York",
            rotation_type="daily",
            handoff_time="08:00",
            rotation_interval_days=1,
            members=[
                {"user_id": str(uuid.uuid4()), "order": 0},
                {"user_id": str(uuid.uuid4()), "order": 1},
            ],
        )
        assert s.rotation_type == "daily"
        assert len(s.members) == 2

    def test_schedule_update_partial(self):
        s = OnCallScheduleUpdate(name="Updated Name")
        dumped = s.model_dump(exclude_unset=True)
        assert "name" in dumped
        assert "timezone" not in dumped

    def test_schedule_response_from_attributes(self):
        now = datetime.now(UTC)
        data = {
            "id": uuid.uuid4(),
            "name": "Primary",
            "timezone": "UTC",
            "rotation_type": "weekly",
            "members": [],
            "handoff_time": "09:00",
            "rotation_interval_days": 7,
            "effective_from": now,
            "is_active": True,
            "overrides": [],
            "created_at": now,
            "updated_at": now,
        }
        resp = OnCallScheduleResponse.model_validate(data)
        assert resp.name == "Primary"
        assert resp.overrides == []

    def test_schedule_list_response(self):
        resp = OnCallScheduleListResponse(schedules=[], total=0)
        assert resp.total == 0

    def test_override_create(self):
        uid = uuid.uuid4()
        now = datetime.now(UTC)
        o = OnCallOverrideCreate(
            user_id=uid,
            starts_at=now,
            ends_at=now + timedelta(hours=8),
            reason="Vacation cover",
        )
        assert o.user_id == uid
        assert o.reason == "Vacation cover"

    def test_override_response(self):
        now = datetime.now(UTC)
        data = {
            "id": uuid.uuid4(),
            "schedule_id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "starts_at": now,
            "ends_at": now + timedelta(hours=8),
            "reason": "Swap",
            "created_at": now,
        }
        resp = OnCallOverrideResponse.model_validate(data)
        assert resp.reason == "Swap"

    def test_current_response_no_user(self):
        resp = OnCallCurrentResponse(
            schedule_id=uuid.uuid4(),
            schedule_name="Primary",
            user=None,
        )
        assert resp.user is None


class TestEscalationSchemas:
    def test_policy_create_defaults(self):
        p = EscalationPolicyCreate(name="Default Policy")
        assert p.repeat is False
        assert p.levels == []

    def test_policy_create_with_levels(self):
        p = EscalationPolicyCreate(
            name="Multi-Level",
            repeat=True,
            levels=[
                {
                    "level": 1,
                    "targets": [{"type": "schedule", "id": str(uuid.uuid4())}],
                    "timeout_minutes": 15,
                },
                {
                    "level": 2,
                    "targets": [{"type": "user", "id": str(uuid.uuid4())}],
                    "timeout_minutes": 30,
                },
            ],
        )
        assert len(p.levels) == 2
        assert p.repeat is True

    def test_policy_update_partial(self):
        p = EscalationPolicyUpdate(repeat=True)
        dumped = p.model_dump(exclude_unset=True)
        assert "repeat" in dumped
        assert "name" not in dumped

    def test_policy_response(self):
        now = datetime.now(UTC)
        data = {
            "id": uuid.uuid4(),
            "name": "Default",
            "repeat": False,
            "levels": [],
            "created_at": now,
            "updated_at": now,
        }
        resp = EscalationPolicyResponse.model_validate(data)
        assert resp.name == "Default"

    def test_policy_list_response(self):
        resp = PolicyListResponse(policies=[], total=0)
        assert resp.total == 0

    def test_mapping_create(self):
        pid = uuid.uuid4()
        m = ServiceMappingCreate(
            service_pattern="billing-svc",
            severity_filter=["critical", "high"],
            escalation_policy_id=pid,
        )
        assert m.service_pattern == "billing-svc"
        assert m.escalation_policy_id == pid

    def test_mapping_create_wildcard(self):
        m = ServiceMappingCreate(
            service_pattern="*",
            escalation_policy_id=uuid.uuid4(),
        )
        assert m.severity_filter is None

    def test_mapping_response(self):
        data = {
            "id": uuid.uuid4(),
            "service_pattern": "order-svc",
            "severity_filter": ["critical"],
            "escalation_policy_id": uuid.uuid4(),
        }
        resp = ServiceMappingResponse.model_validate(data)
        assert resp.service_pattern == "order-svc"


# ─── Model Tests ─────────────────────────────────────────


class TestOnCallModels:
    def test_rotation_type_enum(self):
        assert RotationType.DAILY == "daily"
        assert RotationType.WEEKLY == "weekly"
        assert RotationType.CUSTOM == "custom"

    def test_schedule_repr(self):
        s = OnCallSchedule(name="Primary")
        assert "Primary" in repr(s)

    def test_policy_repr(self):
        p = EscalationPolicy(name="Default")
        assert "Default" in repr(p)

    def test_override_repr(self):
        sid = uuid.uuid4()
        uid = uuid.uuid4()
        o = OnCallOverride(
            schedule_id=sid, user_id=uid,
            starts_at=datetime.now(UTC),
            ends_at=datetime.now(UTC) + timedelta(hours=8),
        )
        assert "schedule=" in repr(o)

    def test_mapping_repr(self):
        pid = uuid.uuid4()
        m = ServiceEscalationMapping(
            service_pattern="billing-svc",
            escalation_policy_id=pid,
        )
        assert "billing-svc" in repr(m)
