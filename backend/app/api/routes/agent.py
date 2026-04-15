"""
Agentic AI routes — OpenAI function calling with ReAct loop.

Endpoints:
  POST /agent/analyze-case  — structured invoice analysis (GPT-4o drives tool calls)
  POST /agent/ask           — free-form natural language question (fully autonomous)
"""

from fastapi import APIRouter

from app.schemas.agent import (
    AgentAskRequest,
    AgentAskResponse,
    AgentCaseRequest,
    AgentCaseResponse,
)
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agent", tags=["AI Agent"])

agent_svc = AgentService()


@router.post(
    "/analyze-case",
    response_model=AgentCaseResponse,
    summary="Agentic invoice analysis — GPT-4o drives tool calls",
    description=(
        "True agentic analysis: GPT-4o autonomously decides which tools to call "
        "and in what order (behavior → delay → strategy), reasons over results, "
        "and returns a unified analysis with full reasoning_trace.\n\n"
        "Tools available to the agent:\n"
        "- analyze_payment_behavior\n"
        "- predict_invoice_delay\n"
        "- optimize_collection_strategy\n"
        "- get_borrower_risk\n"
        "- get_invoice_details\n"
        "- get_portfolio_summary"
    ),
)
async def analyze_case(request: AgentCaseRequest) -> AgentCaseResponse:
    return await agent_svc.analyze_case(request)


@router.post(
    "/ask",
    response_model=AgentAskResponse,
    summary="Free-form agentic question",
    description=(
        "Ask any collections-related question in natural language. "
        "The agent autonomously calls tools to gather what it needs, "
        "then returns a complete answer with its full reasoning trace.\n\n"
        "Examples:\n"
        "- 'Which invoices are at highest risk today?'\n"
        "- 'Should I escalate TechNova Solutions?'\n"
        "- 'Analyze INV-2024-004 and tell me what to do'\n"
        "- 'What is our cash flow risk this month?'"
    ),
)
async def ask_agent(request: AgentAskRequest) -> AgentAskResponse:
    return await agent_svc.ask(request)
