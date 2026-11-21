from fastapi import APIRouter, Depends

from app.controllers.dependencies import get_user_service
from app.schemas.user import UserRead
from app.services.user_service import UserService

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(escalation_contacts: bool = False, service: UserService = Depends(get_user_service)):
    return service.list(escalation_contacts)
