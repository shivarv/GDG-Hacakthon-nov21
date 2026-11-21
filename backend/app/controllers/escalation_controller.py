from fastapi import APIRouter, Depends

from app.controllers.dependencies import get_escalation_service
from app.models import EscalationStatus
from app.schemas.escalation import EscalationWithTicket
from app.services.escalation_service import EscalationService

router = APIRouter(prefix="/api/escalations", tags=["escalations"])


@router.get("", response_model=list[EscalationWithTicket])
def list_escalations(
    status: EscalationStatus | None = EscalationStatus.ACTIVE,
    service: EscalationService = Depends(get_escalation_service),
):
    return service.list(status)
