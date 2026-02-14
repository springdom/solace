"""Tests for runbook rules: schemas, models, and template resolution."""

import uuid
from datetime import UTC, datetime

from backend.models.runbook import RunbookRule
from backend.schemas import (
    AlertRunbookUpdate,
    RunbookRuleCreate,
    RunbookRuleListResponse,
    RunbookRuleResponse,
    RunbookRuleUpdate,
)
from backend.services.runbook import resolve_template

# ─── Schema Validation Tests ─────────────────────────────


class TestRunbookRuleSchemas:
    def test_create_minimal(self):
        r = RunbookRuleCreate(
            service_pattern="payment-*",
            runbook_url_template="https://confluence.com/runbooks#{service}",
        )
        assert r.service_pattern == "payment-*"
        assert r.name_pattern is None
        assert r.description is None
        assert r.priority == 0
        assert r.is_active is True

    def test_create_full(self):
        r = RunbookRuleCreate(
            service_pattern="billing-*",
            name_pattern="HighCPU*",
            runbook_url_template="https://wiki.example.com/{service}/{name}",
            description="Links billing CPU alerts",
            priority=10,
            is_active=False,
        )
        assert r.service_pattern == "billing-*"
        assert r.name_pattern == "HighCPU*"
        assert r.priority == 10
        assert r.is_active is False

    def test_update_partial(self):
        u = RunbookRuleUpdate(priority=5)
        assert u.priority == 5
        assert u.service_pattern is None
        assert u.is_active is None

    def test_update_full(self):
        u = RunbookRuleUpdate(
            service_pattern="auth-*",
            name_pattern="Login*",
            runbook_url_template="https://wiki.example.com/{service}",
            description="Updated desc",
            priority=3,
            is_active=False,
        )
        assert u.service_pattern == "auth-*"
        assert u.is_active is False

    def test_response_from_attributes(self):
        now = datetime.now(UTC)
        rule_id = uuid.uuid4()
        r = RunbookRuleResponse(
            id=rule_id,
            service_pattern="*",
            runbook_url_template="https://example.com",
            priority=0,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        assert r.id == rule_id
        assert r.name_pattern is None
        assert r.description is None

    def test_list_response(self):
        now = datetime.now(UTC)
        rule_id = uuid.uuid4()
        lr = RunbookRuleListResponse(
            rules=[
                RunbookRuleResponse(
                    id=rule_id,
                    service_pattern="svc-*",
                    runbook_url_template="https://example.com/{service}",
                    created_at=now,
                    updated_at=now,
                ),
            ],
            total=1,
        )
        assert lr.total == 1
        assert len(lr.rules) == 1
        assert lr.rules[0].service_pattern == "svc-*"

    def test_alert_runbook_update_defaults(self):
        u = AlertRunbookUpdate(runbook_url="https://example.com/runbook")
        assert u.runbook_url == "https://example.com/runbook"
        assert u.create_rule is False

    def test_alert_runbook_update_with_rule(self):
        u = AlertRunbookUpdate(
            runbook_url="https://example.com/runbook",
            create_rule=True,
        )
        assert u.create_rule is True


# ─── Model Tests ──────────────────────────────────────────


class TestRunbookRuleModel:
    def test_repr(self):
        rule = RunbookRule(
            id=uuid.uuid4(),
            service_pattern="payment-*",
            runbook_url_template="https://example.com/{service}",
        )
        r = repr(rule)
        assert "RunbookRule" in r
        assert "payment-*" in r

    def test_defaults(self):
        """Server defaults apply at DB level; in-memory construction
        requires explicit values for priority/is_active."""
        rule = RunbookRule(
            service_pattern="*",
            runbook_url_template="https://example.com",
            priority=0,
            is_active=True,
        )
        assert rule.priority == 0
        assert rule.is_active is True
        assert rule.name_pattern is None
        assert rule.description is None


# ─── Template Resolution Tests ────────────────────────────


class TestTemplateResolution:
    def test_basic_service_variable(self):
        result = resolve_template(
            "https://confluence.com/runbooks#{service}",
            service="payment-api",
        )
        assert result == "https://confluence.com/runbooks#payment-api"

    def test_multiple_variables(self):
        result = resolve_template(
            "https://wiki.example.com/{service}/{host}/{name}",
            service="billing",
            host="web-01",
            name="HighCPU",
        )
        assert result == "https://wiki.example.com/billing/web-01/HighCPU"

    def test_all_four_variables(self):
        result = resolve_template(
            "https://wiki.example.com/{service}/{host}/{name}/{environment}",
            service="api",
            host="prod-1",
            name="MemoryLeak",
            environment="production",
        )
        assert result == "https://wiki.example.com/api/prod-1/MemoryLeak/production"

    def test_none_values_become_empty(self):
        result = resolve_template(
            "https://wiki.example.com/{service}/{host}",
            service=None,
            host=None,
        )
        assert result == "https://wiki.example.com//"

    def test_unknown_variables_preserved(self):
        result = resolve_template(
            "https://wiki.example.com/{service}/{unknown_var}",
            service="payment-api",
        )
        assert result == "https://wiki.example.com/payment-api/{unknown_var}"

    def test_no_variables_passthrough(self):
        url = "https://wiki.example.com/static-runbook"
        result = resolve_template(url, service="anything")
        assert result == url

    def test_fragment_url_with_service(self):
        result = resolve_template(
            "https://confluence.com/runbooks#{service}",
            service="auth-service",
        )
        assert result == "https://confluence.com/runbooks#auth-service"

    def test_empty_template(self):
        result = resolve_template("", service="test")
        assert result == ""

    def test_environment_only(self):
        result = resolve_template(
            "https://wiki.example.com/runbooks/{environment}",
            environment="staging",
        )
        assert result == "https://wiki.example.com/runbooks/staging"
