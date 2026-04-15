"""
OpenAI recommendation API routes.

Endpoints:
  POST /recommend/action — GPT-4o powered collection strategy recommendation
"""

from fastapi import APIRouter

from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommend", tags=["AI Recommendations"])

rec_svc = RecommendationService()


@router.post(
    "/action",
    response_model=RecommendationResponse,
    summary="AI-powered collection recommendation",
    description=(
        "Sends invoice context, ML predictions, and customer history to a "
        "GPT-4o agent that returns a structured collection strategy with reasoning."
    ),
)
async def recommend_action(request: RecommendationRequest) -> RecommendationResponse:
    return await rec_svc.recommend(request)
