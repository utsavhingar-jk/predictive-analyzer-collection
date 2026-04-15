"""
Orchestrated Agent API routes.

Endpoints:
  POST /agent/analyze-case  — full intelligence pipeline (behavior → delay → strategy → GPT-4o)
"""

from fastapi import APIRouter

from app.schemas.agent import AgentCaseRequest, AgentCaseResponse
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agent", tags=["AI Agent"])

agent_svc = AgentService()


@router.post(
    "/analyze-case",
    response_model=AgentCaseResponse,
    summary="Full AI intelligence pipeline for one invoice case",
    description=(
        "Runs the complete connected pipeline:\n"
        "1. Analyze payment behavior\n"
        "2. Predict delay probability (enriched with behavior)\n"
        "3. Optimize collection strategy\n"
        "4. Generate GPT-4o business summary\n\n"
        "Returns a unified case analysis with all four outputs."
    ),
)
async def analyze_case(request: AgentCaseRequest) -> AgentCaseResponse:
    return await agent_svc.analyze_case(request)
