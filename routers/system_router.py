from fastapi import APIRouter, status
from database import db

router = APIRouter(tags=["System"])

@router.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    try:
        db.collection('users').limit(1).get()
        return {"status": "active", "db_connection": "ok", "message": "System is running smoothly"}
    except Exception as e:
        return {"status": "inactive", "db_connection": "error", "detail": str(e)}