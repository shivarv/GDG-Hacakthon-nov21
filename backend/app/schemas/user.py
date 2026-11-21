from pydantic import BaseModel, ConfigDict

from app.models.enums import UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str | None = None
    role: UserRole
    team: str
    escalation_level: int
    is_escalation_contact: bool
