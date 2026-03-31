from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_payload, get_db
from app.schemas.account import (
    AccountConsentResponse,
    AccountDataExportResponse,
    AccountDeletionStatusResponse,
    UpdateMarketingConsentRequest,
)
from app.services.account_lifecycle import (
    export_account_data,
    get_account_deletion_status,
    request_account_deletion,
)
from app.services.audit import create_audit_log
from app.services.consent import get_current_consents, update_marketing_consents

router = APIRouter()


@router.get("/consents", response_model=AccountConsentResponse)
async def list_account_consents(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    return AccountConsentResponse.model_validate(
        await get_current_consents(db, UUID(payload["sub"]))
    )


@router.get("/data-export", response_model=AccountDataExportResponse)
async def download_account_data_export(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user_id = UUID(payload["sub"])
    return AccountDataExportResponse(
        exported_at=datetime.now(UTC),
        data=await export_account_data(db, user_id),
    )


@router.get("/deletion-status", response_model=AccountDeletionStatusResponse)
async def get_deletion_status(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    return AccountDeletionStatusResponse.model_validate(
        await get_account_deletion_status(db, UUID(payload["sub"]))
    )


@router.post("/delete-request", response_model=AccountDeletionStatusResponse)
async def create_delete_request(
    request: Request,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    return AccountDeletionStatusResponse.model_validate(
        await request_account_deletion(
            db,
            user_id=UUID(payload["sub"]),
            request=request,
        )
    )


@router.put("/consents", response_model=AccountConsentResponse)
async def update_account_consents(
    body: UpdateMarketingConsentRequest,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    consents = await update_marketing_consents(
        db,
        user_id=UUID(payload["sub"]),
        request=request,
        marketing_email=body.marketing_email,
        marketing_sms=body.marketing_sms,
    )
    await create_audit_log(
        db,
        action="account.consent.update",
        resource_type="user",
        resource_id=UUID(payload["sub"]),
        actor_user_id=UUID(payload["sub"]),
        actor_role=payload.get("role"),
        request=request,
        metadata={
            "marketing_email": body.marketing_email,
            "marketing_sms": body.marketing_sms,
        },
    )
    return AccountConsentResponse.model_validate(consents)
