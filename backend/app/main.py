import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services import document_repository, insight_repository, learning_repository, review_repository, user_repository, webhook_repository, workflow_repository
from app.services.config import settings
from app.services.database import close_db
from app.routers import auth, dashboard, documents, feedback_learning, github, health, insights, reviews, webhook, workflows

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await user_repository.ensure_indexes()
        await review_repository.ensure_indexes()
        await document_repository.ensure_indexes()
        await insight_repository.ensure_indexes()
        await learning_repository.ensure_indexes()
        await workflow_repository.ensure_indexes()
        await webhook_repository.ensure_indexes()
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
    app.include_router(webhook.router, tags=["webhook"])
    app.include_router(feedback_learning.router, tags=["feedback"])
    app.include_router(workflows.router, tags=["workflows"])
    app.include_router(dashboard.router, tags=["dashboard"])
    app.include_router(documents.router, tags=["documents"])
    app.include_router(insights.router, tags=["insights"])

    return app


app = create_app()