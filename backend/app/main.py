import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services import ai_review_repository, document_repository, insight_repository, learning_repository, repository_analysis_repository, review_repository, security_repository, user_repository, webhook_repository, workflow_repository
from app.services.config import settings
from app.services.database import close_db
from app.routers import ai_reviews, architecture, assistant, auth, dashboard, documentation_intelligence, documents, feedback_learning, github, health, insights, repository_intelligence, reviews, security, supply_chain, test_generation, webhook, workflows

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await user_repository.ensure_indexes()
        await review_repository.ensure_indexes()
        await ai_review_repository.ensure_indexes()
        await document_repository.ensure_indexes()
        await insight_repository.ensure_indexes()
        await learning_repository.ensure_indexes()
        await workflow_repository.ensure_indexes()
        await webhook_repository.ensure_indexes()
        await repository_analysis_repository.ensure_indexes()
        await security_repository.ensure_indexes()
    except Exception:
        logger.exception("Failed to ensure database indexes; continuing")
    yield
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(title="SmartSDLC API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(github.router, tags=["github"])
    app.include_router(reviews.router, tags=["reviews"])
    # Sprint 3 AI review routes. Registered twice on purpose: once at the root,
    # matching every other router in this app, and once under /api to match the
    # documented public contract. Both paths hit the same handlers, so the
    # frontend and external clients can use either without a redirect.
    # operation_id suffixes keep OpenAPI unique for the duplicated operations.
    app.include_router(ai_reviews.router, tags=["ai-reviews"])
    app.include_router(
        ai_reviews.router,
        prefix="/api",
        tags=["ai-reviews"],
        generate_unique_id_function=lambda route: f"api_{route.name}",
    )
    app.include_router(webhook.router, tags=["webhook"])
    app.include_router(feedback_learning.router, tags=["feedback"])
    app.include_router(workflows.router, tags=["workflows"])
    app.include_router(dashboard.router, tags=["dashboard"])
    app.include_router(documents.router, tags=["documents"])
    app.include_router(insights.router, tags=["insights"])
    app.include_router(repository_intelligence.router, tags=["repository-intelligence"])
    # Sprint 4 security intelligence routes, registered on both paths for the
    # same reason as the Sprint 3 AI review routes above.
    app.include_router(security.router, tags=["security"])
    app.include_router(
        security.router,
        prefix="/api",
        tags=["security"],
        generate_unique_id_function=lambda route: f"api_{route.name}",
    )
    # Architecture intelligence routes, dual-registered for the same reason.
    app.include_router(architecture.router, tags=["architecture"])
    app.include_router(
        architecture.router,
        prefix="/api",
        tags=["architecture"],
        generate_unique_id_function=lambda route: f"api_{route.name}",
    )
    # Documentation intelligence routes, dual-registered for the same reason.
    app.include_router(
        documentation_intelligence.router, tags=["documentation-intelligence"]
    )
    app.include_router(
        documentation_intelligence.router,
        prefix="/api",
        tags=["documentation-intelligence"],
        generate_unique_id_function=lambda route: f"api_{route.name}",
    )
    # Supply-chain intelligence routes, dual-registered for the same reason.
    app.include_router(supply_chain.router, tags=["supply-chain"])
    app.include_router(
        supply_chain.router,
        prefix="/api",
        tags=["supply-chain"],
        generate_unique_id_function=lambda route: f"api_{route.name}",
    )
    # Test generation routes, dual-registered for the same reason.
    app.include_router(test_generation.router, tags=["test-generation"])
    app.include_router(
        test_generation.router,
        prefix="/api",
        tags=["test-generation"],
        generate_unique_id_function=lambda route: f"api_{route.name}",
    )
    # AI Developer Assistant routes, dual-registered for the same reason.
    app.include_router(assistant.router, tags=["assistant"])
    app.include_router(
        assistant.router,
        prefix="/api",
        tags=["assistant"],
        generate_unique_id_function=lambda route: f"api_{route.name}",
    )

    return app


app = create_app()