from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user

router = APIRouter(tags=["auth"])


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    return {"email": user.email, "name": user.name}
