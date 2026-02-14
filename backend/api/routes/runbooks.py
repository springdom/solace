"""Runbook rules API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import AuthContext, require_role
from backend.database import get_db
from backend.models import UserRole
from backend.schemas import (
    RunbookRuleCreate,
    RunbookRuleListResponse,
    RunbookRuleResponse,
    RunbookRuleUpdate,
)
from backend.services.runbook import (
    create_runbook_rule,
    delete_runbook_rule,
    get_runbook_rules,
    update_runbook_rule,
)

router = APIRouter(prefix="/runbooks", tags=["runbooks"])


@router.get(
    "/rules",
    response_model=RunbookRuleListResponse,
    summary="List runbook rules",
)
async def list_rules(
    db: AsyncSession = Depends(get_db),
) -> RunbookRuleListResponse:
    """List all runbook rules, ordered by priority."""
    rules = await get_runbook_rules(db)
    return RunbookRuleListResponse(
        rules=[RunbookRuleResponse.model_validate(r) for r in rules],
        total=len(rules),
    )


@router.post(
    "/rules",
    response_model=RunbookRuleResponse,
    status_code=201,
    summary="Create a runbook rule",
)
async def create_rule(
    body: RunbookRuleCreate,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> RunbookRuleResponse:
    """Create a new runbook rule for auto-attaching runbook URLs."""
    rule = await create_runbook_rule(db, **body.model_dump(exclude_unset=True))
    return RunbookRuleResponse.model_validate(rule)


@router.put(
    "/rules/{rule_id}",
    response_model=RunbookRuleResponse,
    summary="Update a runbook rule",
)
async def update_rule(
    rule_id: uuid.UUID,
    body: RunbookRuleUpdate,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> RunbookRuleResponse:
    """Update an existing runbook rule."""
    rule = await update_runbook_rule(
        db, str(rule_id), **body.model_dump(exclude_unset=True)
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Runbook rule not found")
    return RunbookRuleResponse.model_validate(rule)


@router.delete(
    "/rules/{rule_id}",
    status_code=204,
    summary="Delete a runbook rule",
)
async def delete_rule(
    rule_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a runbook rule."""
    deleted = await delete_runbook_rule(db, str(rule_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Runbook rule not found")
