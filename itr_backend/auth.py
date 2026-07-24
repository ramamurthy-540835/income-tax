from __future__ import annotations

import os
from typing import Literal, Protocol

from fastapi import HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.cloud import firestore
from google.oauth2 import id_token
from pydantic import BaseModel, Field

Role = Literal["admin", "preparer", "reviewer", "customer"]


class UserContext(BaseModel):
    subject: str
    email: str
    roles: set[Role] = Field(default_factory=set)
    customer_ids: set[str] = Field(default_factory=set)
    all_customers: bool = False

    def require_any_role(self, *roles: Role) -> None:
        if not self.roles.intersection(roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )

    def require_customer_access(self, customer_id: str) -> None:
        if not self.all_customers and customer_id not in self.customer_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customer access denied",
            )


class Authenticator(Protocol):
    def authenticate(self, request: Request) -> UserContext: ...


class GoogleAuthenticator:
    def __init__(
        self,
        firestore_client: firestore.Client,
        audience: str | None,
    ):
        self._firestore = firestore_client
        self._audience = audience
        self._request = google_requests.Request()

    def authenticate(self, request: Request) -> UserContext:
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token required",
            )
        token = authorization.removeprefix("Bearer ").strip()
        try:
            claims = id_token.verify_oauth2_token(
                token, self._request, audience=self._audience
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid identity token",
            ) from exc
        subject = str(claims.get("sub") or "")
        email = str(claims.get("email") or "").lower()
        if not subject or not email or claims.get("email_verified") is not True:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Verified email identity required",
            )
        access = self._firestore.collection("users").document(subject).get()
        if not access.exists:
            access = (
                self._firestore.collection("user_access_by_email").document(email).get()
            )
        if not access.exists:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has not been granted application access",
            )
        value = access.to_dict()
        if value.get("active") is not True:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User access is disabled",
            )
        return UserContext(
            subject=subject,
            email=email,
            roles=set(value.get("roles", [])),
            customer_ids=set(value.get("customer_ids", [])),
            all_customers=bool(value.get("all_customers")),
        )


class DevelopmentAuthenticator:
    def authenticate(self, request: Request) -> UserContext:
        if os.getenv("ENVIRONMENT", "development").lower() == "production":
            raise RuntimeError("development authentication cannot run in production")
        return UserContext(
            subject="development-user",
            email="developer@localhost",
            roles={"admin", "preparer", "reviewer"},
            all_customers=True,
        )


class StaticAuthenticator:
    """Test-only authenticator supplied explicitly to create_app."""

    def __init__(self, user: UserContext):
        self._user = user

    def authenticate(self, request: Request) -> UserContext:
        return self._user


def build_authenticator(
    firestore_client: firestore.Client,
) -> Authenticator:
    mode = os.getenv("AUTH_MODE", "google").lower()
    if mode == "development":
        return DevelopmentAuthenticator()
    if mode != "google":
        raise RuntimeError("AUTH_MODE must be google or development")
    audience = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    if os.getenv("ENVIRONMENT", "development").lower() == "production" and not audience:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_ID is required in production")
    return GoogleAuthenticator(
        firestore_client=firestore_client,
        audience=audience,
    )
