from fastapi import APIRouter
from pydantic import BaseModel
from app.core.auth import verify_password, create_token, verify_token

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginRequest):
    if req.username != "admin" or not verify_password(req.password):
        return {"error": "用户名或密码错误"}
    token = create_token()
    return {"data": {"token": token}}


@router.get("/check")
def check_auth(token: str = ""):
    if verify_token(token):
        return {"data": {"authenticated": True}}
    return {"data": {"authenticated": False}}
