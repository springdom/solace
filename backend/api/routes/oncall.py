"""On-call scheduling and escalation policy API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import AuthContext, require_role
from backend.core.oncall import get_current_oncall, validate_member_ids
from backend.database import get_db
from backend.models import UserRole
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
    UserResponse,
)
from backend.services.oncall import (
    create_mapping,
    create_override,
    create_policy,
    create_schedule,
    delete_mapping,
    delete_override,
    delete_policy,
    delete_schedule,
    get_mappings,
    get_policies,
    get_policy,
    get_schedule,
    get_schedules,
    update_policy,
    update_schedule,
)

router = APIRouter(prefix="/oncall", tags=["oncall"])


def _serialize_jsonb_field(value: list) -> list:
    """Recursively serialize Pydantic models and UUIDs for JSONB storage."""
    import uuid as _uuid

    result = []
    for item in value:
        if hasattr(item, "model_dump"):
            result.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            result.append({
                k: str(v) if isinstance(v, _uuid.UUID) else v
                for k, v in item.items()
            })
        else:
            result.append(item)
    return result


def _serialize_schedule_data(data: dict) -> dict:
    """Convert Pydantic member models to plain dicts for JSONB storage."""
    if "members" in data and data["members"] is not None:
        data["members"] = _serialize_jsonb_field(data["members"])
    return data


def _serialize_policy_data(data: dict) -> dict:
    """Convert Pydantic level/target models to plain dicts for JSONB storage."""
    if "levels" in data and data["levels"] is not None:
        serialized = []
        for lvl in data["levels"]:
            if hasattr(lvl, "model_dump"):
                serialized.append(lvl.model_dump(mode="json"))
            elif isinstance(lvl, dict):
                # Recursively handle targets within level dicts
                lvl_copy = dict(lvl)
                if "targets" in lvl_copy:
                    lvl_copy["targets"] = _serialize_jsonb_field(lvl_copy["targets"])
                serialized.append(lvl_copy)
            else:
                serialized.append(lvl)
        data["levels"] = serialized
    return data


# ─── Schedules ─────────────────────────────────────────────


@router.get(
    "/schedules",
    response_model=OnCallScheduleListResponse,
    summary="List on-call schedules",
)
async def list_schedules(
    active_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> OnCallScheduleListResponse:
    schedules, total = await get_schedules(
        db, active_only=active_only, page=page, page_size=page_size
    )
    return OnCallScheduleListResponse(
        schedules=[
            OnCallScheduleResponse.model_validate(s) for s in schedules
        ],
        total=total,
    )


@router.post(
    "/schedules",
    response_model=OnCallScheduleResponse,
    status_code=201,
    summary="Create an on-call schedule",
)
async def create_schedule_route(
    body: OnCallScheduleCreate,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> OnCallScheduleResponse:
    data = _serialize_schedule_data(body.model_dump(exclude_unset=True))

    # Validate member user_ids exist
    if data.get("members"):
        invalid = await validate_member_ids(db, data["members"])
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user IDs in members: {', '.join(invalid)}"
            )

    schedule = await create_schedule(db, **data)
    return OnCallScheduleResponse.model_validate(schedule)


@router.get(
    "/schedules/{schedule_id}",
    response_model=OnCallScheduleResponse,
    summary="Get an on-call schedule",
)
async def get_schedule_route(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> OnCallScheduleResponse:
    schedule = await get_schedule(db, str(schedule_id))
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return OnCallScheduleResponse.model_validate(schedule)


@router.put(
    "/schedules/{schedule_id}",
    response_model=OnCallScheduleResponse,
    summary="Update an on-call schedule",
)
async def update_schedule_route(
    schedule_id: uuid.UUID,
    body: OnCallScheduleUpdate,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> OnCallScheduleResponse:
    data = _serialize_schedule_data(body.model_dump(exclude_unset=True))

    # Validate member user_ids if members are being updated
    if data.get("members"):
        invalid = await validate_member_ids(db, data["members"])
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user IDs in members: {', '.join(invalid)}"
            )

    schedule = await update_schedule(db, str(schedule_id), **data)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return OnCallScheduleResponse.model_validate(schedule)


@router.delete(
    "/schedules/{schedule_id}",
    status_code=204,
    summary="Delete an on-call schedule",
)
async def delete_schedule_route(
    schedule_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await delete_schedule(db, str(schedule_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")


@router.get(
    "/schedules/{schedule_id}/current",
    response_model=OnCallCurrentResponse,
    summary="Get who is currently on call",
)
async def get_current_oncall_route(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> OnCallCurrentResponse:
    schedule = await get_schedule(db, str(schedule_id))
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    user = await get_current_oncall(db, str(schedule_id))
    return OnCallCurrentResponse(
        schedule_id=schedule.id,
        schedule_name=schedule.name,
        user=UserResponse.model_validate(user) if user else None,
    )


# ─── Overrides ─────────────────────────────────────────────


@router.post(
    "/schedules/{schedule_id}/overrides",
    response_model=OnCallOverrideResponse,
    status_code=201,
    summary="Create a temporary override",
)
async def create_override_route(
    schedule_id: uuid.UUID,
    body: OnCallOverrideCreate,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> OnCallOverrideResponse:
    # Verify schedule exists
    schedule = await get_schedule(db, str(schedule_id))
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    override = await create_override(
        db,
        schedule_id=schedule_id,
        user_id=body.user_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        reason=body.reason,
    )
    return OnCallOverrideResponse.model_validate(override)


@router.delete(
    "/overrides/{override_id}",
    status_code=204,
    summary="Delete an override",
)
async def delete_override_route(
    override_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await delete_override(db, str(override_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Override not found")


# ─── Escalation Policies ──────────────────────────────────


@router.get(
    "/policies",
    response_model=PolicyListResponse,
    summary="List escalation policies",
)
async def list_policies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PolicyListResponse:
    policies, total = await get_policies(db, page=page, page_size=page_size)
    return PolicyListResponse(
        policies=[
            EscalationPolicyResponse.model_validate(p) for p in policies
        ],
        total=total,
    )


@router.post(
    "/policies",
    response_model=EscalationPolicyResponse,
    status_code=201,
    summary="Create an escalation policy",
)
async def create_policy_route(
    body: EscalationPolicyCreate,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> EscalationPolicyResponse:
    data = _serialize_policy_data(body.model_dump(exclude_unset=True))
    policy = await create_policy(db, **data)
    return EscalationPolicyResponse.model_validate(policy)


@router.get(
    "/policies/{policy_id}",
    response_model=EscalationPolicyResponse,
    summary="Get an escalation policy",
)
async def get_policy_route(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EscalationPolicyResponse:
    policy = await get_policy(db, str(policy_id))
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return EscalationPolicyResponse.model_validate(policy)


@router.put(
    "/policies/{policy_id}",
    response_model=EscalationPolicyResponse,
    summary="Update an escalation policy",
)
async def update_policy_route(
    policy_id: uuid.UUID,
    body: EscalationPolicyUpdate,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> EscalationPolicyResponse:
    data = _serialize_policy_data(body.model_dump(exclude_unset=True))
    policy = await update_policy(db, str(policy_id), **data)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return EscalationPolicyResponse.model_validate(policy)


@router.delete(
    "/policies/{policy_id}",
    status_code=204,
    summary="Delete an escalation policy",
)
async def delete_policy_route(
    policy_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await delete_policy(db, str(policy_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Policy not found")


# ─── Service Mappings ─────────────────────────────────────


@router.get(
    "/mappings",
    response_model=list[ServiceMappingResponse],
    summary="List service-to-policy mappings",
)
async def list_mappings(
    db: AsyncSession = Depends(get_db),
) -> list[ServiceMappingResponse]:
    mappings = await get_mappings(db)
    return [ServiceMappingResponse.model_validate(m) for m in mappings]


@router.post(
    "/mappings",
    response_model=ServiceMappingResponse,
    status_code=201,
    summary="Create a service-to-policy mapping",
)
async def create_mapping_route(
    body: ServiceMappingCreate,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ServiceMappingResponse:
    mapping = await create_mapping(
        db, **body.model_dump(exclude_unset=True)
    )
    return ServiceMappingResponse.model_validate(mapping)


@router.delete(
    "/mappings/{mapping_id}",
    status_code=204,
    summary="Delete a service-to-policy mapping",
)
async def delete_mapping_route(
    mapping_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await delete_mapping(db, str(mapping_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Mapping not found")
