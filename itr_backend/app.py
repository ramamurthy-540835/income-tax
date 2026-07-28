from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import Response as RawResponse
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery, firestore, storage

from itr_backend.analytics import BigQueryAnalyticsRepository
from itr_backend.audit import FirestoreAuditRepository
from itr_backend.auth import (
    Authenticator,
    StaticAuthenticator,
    UserContext,
    build_authenticator,
)
from itr_backend.config import Settings
from itr_backend.enrollment import (
    AssessmentYearEnrollmentService,
    EnrollmentError,
    EnrollmentRequest,
    FirestoreAssessmentYearEnrollmentRepository,
)
from itr_backend.filing_models import (
    AutomatedTaxCalculation,
    CalculationResult,
    ClientOnboardingRequest,
    FilingEvidence,
    FilingProfile,
    NormalizedReturnData,
    PortalDraft,
    PortalValidationResult,
    ReviewDecision,
    TaxYearDescriptor,
    WorkspaceSummary,
)
from itr_backend.filing_repositories import (
    ConcurrentUpdateError,
    FirestoreFilingMetadataRepository,
    GCSArtifactRepository,
)
from itr_backend.filing_service import (
    FilingArtifactNotFoundError,
    FilingService,
    FilingValidationError,
)
from itr_backend.models import (
    CustomerCreate,
    CustomerList,
    CustomerRecord,
    CustomerStatusUpdate,
    HealthResponse,
    normalize_assessment_year,
)
from itr_backend.notice_models import (
    NoticeCase,
    NoticeCaseCreate,
    NoticeCaseList,
    NoticeAnalysis,
    NoticeAnalysisRequest,
    NoticeReview,
    ResponseDraft,
)
from itr_backend.notice_service import NoticeService
from itr_backend.read_routes import register_read_routes
from itr_backend.repositories import (
    FirestoreCustomerRepository,
    GCSWorkspaceRepository,
)
from itr_backend.service import (
    CustomerNotFoundError,
    CustomerProvisioningError,
    CustomerService,
)
from itr_backend.storage_models import (
    ArtifactWriteResult,
    BatchDocumentUploadResult,
    DocumentCategory,
    DocumentList,
    DocumentRecord,
    FilingState,
)
from itr_backend.tax_years import list_tax_years


@dataclass(frozen=True)
class BackendRuntime:
    customer_service: CustomerService
    filing_service: FilingService
    enrollment_service: AssessmentYearEnrollmentService
    authenticator: Authenticator
    notice_service: NoticeService


@lru_cache
def build_runtime() -> BackendRuntime:
    settings = Settings.from_env()
    firestore_client = firestore.Client(project=settings.gcp_project_id)
    storage_client = storage.Client(project=settings.gcp_project_id)
    analytics = BigQueryAnalyticsRepository(
        bigquery.Client(project=settings.gcp_project_id),
        settings.bigquery_dataset,
    )
    bucket = storage_client.bucket(settings.gcs_bucket_name)
    customer_repository = FirestoreCustomerRepository(firestore_client)
    workspace_repository = GCSWorkspaceRepository(bucket)
    filing_metadata = FirestoreFilingMetadataRepository(firestore_client)
    artifacts = GCSArtifactRepository(bucket)
    return BackendRuntime(
        customer_service=CustomerService(
            customers=customer_repository,
            workspaces=workspace_repository,
            analytics=analytics,
        ),
        filing_service=FilingService(
            metadata=filing_metadata,
            artifacts=artifacts,
            audit=FirestoreAuditRepository(firestore_client),
            analytics=analytics,
        ),
        enrollment_service=AssessmentYearEnrollmentService(
            enrollment=FirestoreAssessmentYearEnrollmentRepository(firestore_client),
            workspace=workspace_repository,
            metadata=filing_metadata,
            artifacts=artifacts,
        ),
        authenticator=build_authenticator(firestore_client),
        notice_service=NoticeService(
            artifacts=artifacts,
            audit=FirestoreAuditRepository(firestore_client),
            metadata=filing_metadata,
            analytics=analytics,
        ),
    )


def build_customer_service() -> CustomerService:
    return build_runtime().customer_service


def _parse_generation(value: str | None) -> int | None:
    if value is None:
        return None
    normalized = value.strip().strip('"')
    try:
        generation = int(normalized)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="If-Match must contain a GCS generation"
        ) from exc
    if generation < 1:
        raise HTTPException(
            status_code=400, detail="If-Match generation must be positive"
        )
    return generation


def create_app(
    customer_service: CustomerService | None = None,
    filing_service: FilingService | None = None,
    enrollment_service: AssessmentYearEnrollmentService | None = None,
    authenticator: Authenticator | None = None,
    notice_service: NoticeService | None = None,
) -> FastAPI:
    app = FastAPI(
        title="AIDIRAC Income Tax API",
        version="0.2.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "If-Match"],
        expose_headers=["ETag"],
    )
    app.state.customer_service = customer_service
    app.state.filing_service = filing_service
    app.state.enrollment_service = enrollment_service
    if authenticator is None and customer_service is not None:
        authenticator = StaticAuthenticator(
            UserContext(
                subject="test-user",
                email="test@example.invalid",
                roles={"admin", "preparer", "reviewer"},
                all_customers=True,
            )
        )
    app.state.authenticator = authenticator
    app.state.notice_service = notice_service

    def current_user(request: Request) -> UserContext:
        configured = request.app.state.authenticator or build_runtime().authenticator
        return configured.authenticate(request)

    def customer_api(request: Request) -> CustomerService:
        return request.app.state.customer_service or build_runtime().customer_service

    def filing_api(request: Request) -> FilingService:
        return request.app.state.filing_service or build_runtime().filing_service

    def enrollment_api(
        request: Request,
    ) -> AssessmentYearEnrollmentService:
        return (
            request.app.state.enrollment_service or build_runtime().enrollment_service
        )

    def notice_api(request: Request) -> NoticeService:
        return request.app.state.notice_service or build_runtime().notice_service

    @app.exception_handler(ConcurrentUpdateError)
    def concurrent_update_handler(request: Request, exc: ConcurrentUpdateError):
        return RawResponse(
            content='{"detail":"Artifact changed; reload and retry"}',
            status_code=409,
            media_type="application/json",
        )

    @app.exception_handler(FilingArtifactNotFoundError)
    def artifact_not_found_handler(request: Request, exc: FilingArtifactNotFoundError):
        return RawResponse(
            content='{"detail":"Filing artifact not found"}',
            status_code=404,
            media_type="application/json",
        )

    @app.exception_handler(FilingValidationError)
    def filing_validation_handler(request: Request, exc: FilingValidationError):
        import json

        return RawResponse(
            content=json.dumps(
                {
                    "detail": str(exc),
                    "issues": [issue.model_dump(mode="json") for issue in exc.issues],
                }
            ),
            status_code=422,
            media_type="application/json",
        )

    @app.get("/healthz", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/api/tax-years", response_model=list[TaxYearDescriptor])
    def tax_years(
        user: UserContext = Depends(current_user),
    ) -> list[TaxYearDescriptor]:
        return list_tax_years()

    @app.post(
        "/api/assessment-years/{assessment_year}/customers",
        response_model=CustomerRecord,
        status_code=status.HTTP_201_CREATED,
    )
    def create_customer(
        assessment_year: str,
        payload: CustomerCreate,
        service: CustomerService = Depends(customer_api),
        user: UserContext = Depends(current_user),
    ) -> CustomerRecord:
        user.require_any_role("admin", "preparer")
        try:
            return service.create(assessment_year, payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except CustomerProvisioningError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get(
        "/api/assessment-years/{assessment_year}/customers",
        response_model=CustomerList,
    )
    def list_customers(
        assessment_year: str,
        service: CustomerService = Depends(customer_api),
        user: UserContext = Depends(current_user),
    ) -> CustomerList:
        user.require_any_role("admin", "preparer", "reviewer")
        if not user.all_customers:
            raise HTTPException(status_code=403, detail="Customer list denied")
        try:
            ay = normalize_assessment_year(assessment_year)
            return CustomerList(assessment_year=ay, customers=service.list(ay))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}",
        response_model=CustomerRecord,
    )
    def get_customer(
        assessment_year: str,
        customer_id: str,
        service: CustomerService = Depends(customer_api),
        user: UserContext = Depends(current_user),
    ) -> CustomerRecord:
        user.require_customer_access(customer_id)
        try:
            return service.get(assessment_year, customer_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Customer not found") from exc

    @app.post(
        "/api/assessment-years/{assessment_year}/clients/onboard",
        response_model=CustomerRecord,
        status_code=201,
    )
    def onboard_client(
        assessment_year: str,
        payload: ClientOnboardingRequest,
        customers: CustomerService = Depends(customer_api),
        filings: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> CustomerRecord:
        user.require_any_role("admin", "preparer")
        customer = customers.create(
            assessment_year,
            CustomerCreate(
                display_name=payload.display_name,
                preferred_regime=payload.preferred_regime,
                is_active=payload.is_active,
            ),
        )
        _, generation = filings.get_profile(
            customer.assessment_year, customer.customer_id
        )
        filings.put_profile(
            customer.assessment_year,
            customer.customer_id,
            payload.profile,
            generation,
            user.subject,
        )
        return customer

    @app.patch(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/status",
        response_model=CustomerRecord,
    )
    def update_customer_status(
        assessment_year: str,
        customer_id: str,
        payload: CustomerStatusUpdate,
        service: CustomerService = Depends(customer_api),
        user: UserContext = Depends(current_user),
    ) -> CustomerRecord:
        user.require_any_role("admin", "preparer")
        user.require_customer_access(customer_id)
        try:
            return service.set_active(
                assessment_year, customer_id, payload.is_active
            )
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Customer not found") from exc

    @app.post(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/enroll",
        response_model=CustomerRecord,
        status_code=201,
    )
    def enroll_customer(
        assessment_year: str,
        customer_id: str,
        payload: EnrollmentRequest,
        service: AssessmentYearEnrollmentService = Depends(enrollment_api),
        user: UserContext = Depends(current_user),
    ) -> CustomerRecord:
        user.require_any_role("admin", "preparer")
        user.require_customer_access(customer_id)
        try:
            return service.enroll(assessment_year, customer_id, payload)
        except (ValueError, EnrollmentError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/profile",
        response_model=FilingProfile,
    )
    def get_profile(
        assessment_year: str,
        customer_id: str,
        response: Response,
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> FilingProfile:
        user.require_customer_access(customer_id)
        profile, generation = service.get_profile(assessment_year, customer_id)
        response.headers["ETag"] = f'"{generation}"'
        return profile

    @app.put(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/profile",
        response_model=ArtifactWriteResult,
    )
    def put_profile(
        assessment_year: str,
        customer_id: str,
        payload: FilingProfile,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> ArtifactWriteResult:
        user.require_any_role("admin", "preparer")
        user.require_customer_access(customer_id)
        return ArtifactWriteResult(
            artifact=service.put_profile(
                assessment_year,
                customer_id,
                payload,
                _parse_generation(if_match),
                user.subject,
            )
        )

    @app.get(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/return-data",
        response_model=NormalizedReturnData,
    )
    def get_return_data(
        assessment_year: str,
        customer_id: str,
        response: Response,
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> NormalizedReturnData:
        user.require_customer_access(customer_id)
        data, generation = service.get_return_data(assessment_year, customer_id)
        response.headers["ETag"] = f'"{generation}"'
        return data

    @app.put(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/return-data",
        response_model=ArtifactWriteResult,
    )
    def put_return_data(
        assessment_year: str,
        customer_id: str,
        payload: NormalizedReturnData,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> ArtifactWriteResult:
        user.require_any_role("admin", "preparer")
        user.require_customer_access(customer_id)
        return ArtifactWriteResult(
            artifact=service.put_return_data(
                assessment_year,
                customer_id,
                payload,
                _parse_generation(if_match),
                user.subject,
            )
        )

    @app.post(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/calculations/{regime}",
        response_model=CalculationResult,
    )
    def calculate(
        assessment_year: str,
        customer_id: str,
        regime: Literal["old", "new"],
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> CalculationResult:
        user.require_any_role("admin", "preparer", "reviewer")
        user.require_customer_access(customer_id)
        return service.calculate(assessment_year, customer_id, regime, user.subject)

    @app.post(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/calculations/{regime}/pdf",
    )
    def calculate_pdf(
        assessment_year: str,
        customer_id: str,
        regime: Literal["old", "new"],
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ):
        user.require_any_role("admin", "preparer", "reviewer")
        user.require_customer_access(customer_id)
        payload, filename = service.generate_calculation_pdf(
            assessment_year, customer_id, regime, user.subject
        )
        return RawResponse(
            content=payload,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @app.post(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/automation/calculate",
        response_model=AutomatedTaxCalculation,
    )
    def automate_tax_from_documents(
        assessment_year: str,
        customer_id: str,
        compare_new: bool = False,
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> AutomatedTaxCalculation:
        user.require_any_role("admin", "preparer", "reviewer")
        user.require_customer_access(customer_id)
        return service.extract_and_calculate(
            assessment_year,
            customer_id,
            compare_new,
            user.subject,
        )

    @app.post(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/documents",
        response_model=DocumentRecord,
        status_code=201,
    )
    async def upload_document(
        assessment_year: str,
        customer_id: str,
        category: Annotated[DocumentCategory, Form()],
        file: Annotated[UploadFile, File()],
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> DocumentRecord:
        user.require_any_role("admin", "preparer", "customer")
        user.require_customer_access(customer_id)
        content = await file.read()
        return service.upload_document(
            assessment_year,
            customer_id,
            category,
            file.filename or "document.pdf",
            content,
            user.subject,
        )

    @app.get(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/documents",
        response_model=DocumentList,
    )
    def list_documents(
        assessment_year: str,
        customer_id: str,
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> DocumentList:
        user.require_customer_access(customer_id)
        return DocumentList(
            documents=service.list_documents(assessment_year, customer_id)
        )

    @app.post(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/documents/batch",
        response_model=BatchDocumentUploadResult,
        status_code=201,
    )
    async def batch_upload_documents(
        assessment_year: str,
        customer_id: str,
        files: Annotated[list[UploadFile], File()],
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> BatchDocumentUploadResult:
        user.require_any_role("admin", "preparer", "customer")
        user.require_customer_access(customer_id)
        if not files or len(files) > 50:
            raise HTTPException(
                status_code=422, detail="upload between 1 and 50 documents per batch"
            )
        accepted: list[DocumentRecord] = []
        failed: list[dict[str, str]] = []
        for file in files:
            filename = file.filename or "document"
            try:
                accepted.append(
                    service.auto_upload_document(
                        assessment_year,
                        customer_id,
                        filename,
                        await file.read(),
                        file.content_type or "application/octet-stream",
                        user.subject,
                    )
                )
            except FilingValidationError as exc:
                failed.append({"filename": filename, "reason": str(exc)})
        return BatchDocumentUploadResult(documents=accepted, failed=failed)

    @app.put(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/portal-draft",
        response_model=PortalValidationResult,
    )
    def put_portal_draft(
        assessment_year: str,
        customer_id: str,
        payload: PortalDraft,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> PortalValidationResult:
        user.require_any_role("admin", "preparer")
        user.require_customer_access(customer_id)
        return service.put_portal_draft(
            assessment_year,
            customer_id,
            payload,
            _parse_generation(if_match),
            user.subject,
        )

    @app.get(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/portal-validation",
        response_model=PortalValidationResult,
    )
    def get_portal_validation(
        assessment_year: str,
        customer_id: str,
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> PortalValidationResult:
        user.require_customer_access(customer_id)
        return service.get_portal_validation(assessment_year, customer_id)

    @app.post(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/review",
        response_model=FilingState,
    )
    def review(
        assessment_year: str,
        customer_id: str,
        payload: ReviewDecision,
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> FilingState:
        user.require_any_role("admin", "reviewer")
        user.require_customer_access(customer_id)
        return service.review(assessment_year, customer_id, payload, user.subject)

    @app.get(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/export",
    )
    def export_portal_json(
        assessment_year: str,
        customer_id: str,
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ):
        user.require_any_role("admin", "preparer", "reviewer")
        user.require_customer_access(customer_id)
        payload, filename = service.export_portal_json(
            assessment_year, customer_id, user.subject
        )
        return RawResponse(
            content=payload,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @app.post(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/filing-evidence",
        response_model=FilingState,
    )
    def record_filing_evidence(
        assessment_year: str,
        customer_id: str,
        payload: FilingEvidence,
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> FilingState:
        user.require_any_role("admin", "preparer", "reviewer")
        user.require_customer_access(customer_id)
        return service.record_filing_evidence(
            assessment_year, customer_id, payload, user.subject
        )

    @app.get(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/summary",
        response_model=WorkspaceSummary,
    )
    def workspace_summary(
        assessment_year: str,
        customer_id: str,
        service: FilingService = Depends(filing_api),
        user: UserContext = Depends(current_user),
    ) -> WorkspaceSummary:
        user.require_customer_access(customer_id)
        return service.summary(assessment_year, customer_id)

    @app.post(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/notices",
        response_model=NoticeCase,
        status_code=201,
    )
    def create_notice_case(
        assessment_year: str,
        customer_id: str,
        payload: NoticeCaseCreate,
        service: NoticeService = Depends(notice_api),
        user: UserContext = Depends(current_user),
    ) -> NoticeCase:
        user.require_any_role("admin", "preparer")
        user.require_customer_access(customer_id)
        return service.create(assessment_year, customer_id, payload, user.subject)

    @app.post(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/notices/analyze",
        response_model=NoticeAnalysis,
    )
    def analyze_pasted_notice(
        assessment_year: str,
        customer_id: str,
        payload: NoticeAnalysisRequest,
        service: NoticeService = Depends(notice_api),
        user: UserContext = Depends(current_user),
    ) -> NoticeAnalysis:
        user.require_any_role("admin", "preparer", "reviewer", "customer")
        user.require_customer_access(customer_id)
        if normalize_assessment_year(payload.assessment_year) != normalize_assessment_year(
            assessment_year
        ):
            raise HTTPException(status_code=422, detail="assessment year mismatch")
        return service.analyze(payload)

    @app.get(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/notices",
        response_model=NoticeCaseList,
    )
    def list_notice_cases(
        assessment_year: str,
        customer_id: str,
        service: NoticeService = Depends(notice_api),
        user: UserContext = Depends(current_user),
    ) -> NoticeCaseList:
        user.require_customer_access(customer_id)
        return service.list(assessment_year, customer_id)

    @app.post(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/notices/{case_id}/draft",
        response_model=ResponseDraft,
    )
    def draft_notice_response(
        assessment_year: str,
        customer_id: str,
        case_id: str,
        service: NoticeService = Depends(notice_api),
        user: UserContext = Depends(current_user),
    ) -> ResponseDraft:
        user.require_any_role("admin", "preparer", "reviewer")
        user.require_customer_access(customer_id)
        return service.draft(assessment_year, customer_id, case_id, user.subject)

    @app.post(
        "/api/assessment-years/{assessment_year}/customers/{customer_id}/notices/{case_id}/review",
        response_model=ResponseDraft,
    )
    def review_notice_response(
        assessment_year: str,
        customer_id: str,
        case_id: str,
        payload: NoticeReview,
        service: NoticeService = Depends(notice_api),
        user: UserContext = Depends(current_user),
    ) -> ResponseDraft:
        user.require_any_role("admin", "reviewer")
        user.require_customer_access(customer_id)
        return service.review(
            assessment_year, customer_id, case_id, payload, user.subject
        )

    register_read_routes(app, filing_api, current_user)
    return app


app = create_app()
