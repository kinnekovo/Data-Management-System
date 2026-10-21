from typing import Annotated

from bson import ObjectId
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.database import Database

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_database(request: Request) -> Database:
    return request.app.state.mongodb_database


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    database: Annotated[Database, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "AUTH_REQUIRED", "请先登录")
    user_id = decode_access_token(credentials.credentials, settings)
    if user_id is None or not ObjectId.is_valid(user_id):
        raise AppError(401, "INVALID_TOKEN", "登录凭证无效或已过期")
    user = database.users.find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise AppError(401, "INVALID_TOKEN", "登录凭证无效或已过期")
    return user


DatabaseDep = Annotated[Database, Depends(get_database)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
CurrentUser = Annotated[dict, Depends(get_current_user)]
