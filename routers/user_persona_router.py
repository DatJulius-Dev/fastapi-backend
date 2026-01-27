from fastapi import APIRouter
from services.persona_service import update_user_persona

router = APIRouter()

@router.get("/users/{user_id}/persona")
def get_user_persona(user_id: str):
    persona = update_user_persona(user_id)
    return persona