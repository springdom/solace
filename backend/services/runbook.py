"""CRUD services for runbook rules and template resolution."""

import logging
from datetime import UTC, datetime
from fnmatch import fnmatch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.runbook import RunbookRule

logger = logging.getLogger(__name__)


# ─── CRUD ────────────────────────────────────────────────


async def get_runbook_rules(
    db: AsyncSession,
    active_only: bool = False,
) -> list[RunbookRule]:
    """List all runbook rules, ordered by priority."""
    stmt = select(RunbookRule).order_by(
        RunbookRule.priority.asc(),
        RunbookRule.created_at.asc(),
    )
    if active_only:
        stmt = stmt.where(RunbookRule.is_active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_runbook_rule(
    db: AsyncSession,
    rule_id: str,
) -> RunbookRule | None:
    """Get a single runbook rule by ID."""
    stmt = select(RunbookRule).where(RunbookRule.id == rule_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_runbook_rule(
    db: AsyncSession,
    **kwargs,
) -> RunbookRule:
    """Create a new runbook rule."""
    rule = RunbookRule(**kwargs)
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


async def update_runbook_rule(
    db: AsyncSession,
    rule_id: str,
    **kwargs,
) -> RunbookRule | None:
    """Update an existing runbook rule."""
    rule = await get_runbook_rule(db, rule_id)
    if not rule:
        return None
    for key, value in kwargs.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    rule.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(rule)
    return rule


async def delete_runbook_rule(
    db: AsyncSession,
    rule_id: str,
) -> bool:
    """Delete a runbook rule. Returns True if found and deleted."""
    rule = await get_runbook_rule(db, rule_id)
    if not rule:
        return False
    await db.delete(rule)
    await db.flush()
    return True


# ─── Template Resolution ─────────────────────────────────


class _SafeDict(dict):
    """Dict subclass that returns '{key}' for missing keys instead of raising."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def resolve_template(
    template: str,
    service: str | None = None,
    host: str | None = None,
    name: str | None = None,
    environment: str | None = None,
) -> str:
    """Resolve template variables in a runbook URL.

    Supported variables: {service}, {host}, {name}, {environment}
    Unknown variables are left as-is. None values become empty string.
    """
    return template.format_map(
        _SafeDict(
            service=service or "",
            host=host or "",
            name=name or "",
            environment=environment or "",
        )
    )


# ─── Pattern Matching ────────────────────────────────────


async def find_matching_runbook(
    db: AsyncSession,
    service: str | None,
    name: str | None,
    host: str | None = None,
    environment: str | None = None,
) -> str | None:
    """Find the first matching runbook rule and resolve its template.

    Fetches all active rules ordered by priority (lower = first).
    Evaluates service_pattern and name_pattern as globs (fnmatch).
    First match wins. Returns the resolved URL or None.
    """
    rules = await get_runbook_rules(db, active_only=True)

    svc = service or ""

    for rule in rules:
        # Service pattern match (required)
        if not fnmatch(svc, rule.service_pattern):
            continue

        # Name pattern match (optional — skip check if no pattern set)
        if rule.name_pattern and name:
            if not fnmatch(name, rule.name_pattern):
                continue
        elif rule.name_pattern and not name:
            # Rule requires a name pattern but alert has no name
            continue

        # Match found — resolve template
        return resolve_template(
            rule.runbook_url_template,
            service=service,
            host=host,
            name=name,
            environment=environment,
        )

    return None
