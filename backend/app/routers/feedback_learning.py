from fastapi import APIRouter, Depends

from app.schemas.feedback_learning import FeedbackLearningResponse
from app.services import feedback_learning_service
from app.services.security import get_current_user

router = APIRouter()


@router.post("/feedback/learning/recalculate", response_model=FeedbackLearningResponse)
async def recalculate_learning(user: dict = Depends(get_current_user)):
    return await feedback_learning_service.recalculate_learning(user["github_id"])


@router.get("/feedback/learning", response_model=FeedbackLearningResponse)
async def list_feedback_learning(user: dict = Depends(get_current_user)):
    return await feedback_learning_service.get_learning(user["github_id"])


@router.get("/feedback/learning/{owner}/{repository}", response_model=FeedbackLearningResponse)
async def list_repository_feedback_learning(
    owner: str,
    repository: str,
    user: dict = Depends(get_current_user),
):
    return await feedback_learning_service.get_learning(user["github_id"], owner, repository)