from datetime import UTC

from fastapi import APIRouter, status
from pymongo.errors import DuplicateKeyError

from app.api.dependencies import CurrentUser, DatabaseDep, SettingsDep
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.auth import Credentials
from app.schemas.common import iso_datetime, utc_now

router = APIRouter(prefix="/auth", tags=["auth"])


def user_view(user: dict) -> dict[str, str]:
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "created_at": iso_datetime(user["created_at"]),
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: Credentials, database: DatabaseDep) -> dict:
    document = {
        "username": payload.username,
        "password_hash": hash_password(payload.password),
        "created_at": utc_now(),
    }
    try:
        result = database.users.insert_one(document)
    except DuplicateKeyError:
        raise AppError(409, "USERNAME_EXISTS", "用户名已存在") from None
    document["_id"] = result.inserted_id
    return user_view(document)


@router.post("/login")
def login(payload: Credentials, database: DatabaseDep, settings: SettingsDep) -> dict:
    user = database.users.find_one({"username": payload.username})
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise AppError(401, "INVALID_CREDENTIALS", "用户名或密码错误")
    token, expires_at = create_access_token(str(user["_id"]), settings)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": iso_datetime(expires_at.astimezone(UTC)),
        "user": user_view(user),
    }


@router.get("/me")
def me(current_user: CurrentUser) -> dict:
    return user_view(current_user)
