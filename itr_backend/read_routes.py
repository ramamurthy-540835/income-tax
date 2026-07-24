from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, FastAPI, Response
from fastapi.responses import Response as RawResponse

from itr_backend.auth import UserContext
from itr_backend.filing_service import FilingService


def register_read_routes(
    app: FastAPI,
    filing_dependency: Callable[..., FilingService],
    user_dependency: Callable[..., UserContext],
) -> None:
    @app.get(
        "/api/assessment-years/{assessment_year}/customers/"
        "{customer_id}/documents/{document_id}",
    )
    def download_document(
        assessment_year: str,
        customer_id: str,
        document_id: str,
        service: FilingService = Depends(filing_dependency),
        user: UserContext = Depends(user_dependency),
    ):
        user.require_customer_access(customer_id)
        payload, document = service.download_document(
            assessment_year, customer_id, document_id
        )
        return RawResponse(
            content=payload,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{document.document_id}.pdf"'
                ),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/portal-draft",
    )
    def get_portal_draft(
        assessment_year: str,
        customer_id: str,
        response: Response,
        service: FilingService = Depends(filing_dependency),
        user: UserContext = Depends(user_dependency),
    ):
        user.require_customer_access(customer_id)
        payload, generation = service.get_portal_draft(assessment_year, customer_id)
        response.headers["ETag"] = f'"{generation}"'
        response.headers["Cache-Control"] = "no-store"
        return payload
