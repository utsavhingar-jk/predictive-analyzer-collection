"""
Collection prioritization API routes.

Endpoints:
  GET  /prioritize/invoices   — sorted collector worklist
  POST /whatif/simulate       — what-if scenario simulation
"""

from fastapi import APIRouter

from app.schemas.prediction import PrioritizedInvoice
from app.schemas.whatif import WhatIfRequest, WhatIfResponse
from app.services.prioritization_service import PrioritizationService
from app.services.whatif_service import WhatIfService

router = APIRouter(tags=["Prioritization & Simulation"])

priority_svc = PrioritizationService()
whatif_svc = WhatIfService()


@router.get(
    "/prioritize/invoices",
    response_model=list[PrioritizedInvoice],
    summary="Priority-sorted collector worklist",
    description=(
        "Returns all open/overdue invoices sorted by priority score "
        "(amount × delay_probability) descending."
    ),
)
async def get_worklist() -> list[PrioritizedInvoice]:
    return await priority_svc.get_prioritized_worklist()


@router.post(
    "/whatif/simulate",
    response_model=WhatIfResponse,
    summary="What-if scenario simulation",
    description=(
        "Simulates the impact of collection strategy changes "
        "(efficiency %, discount %, follow-up timing) on recovery, cashflow, and DSO."
    ),
)
async def simulate_whatif(request: WhatIfRequest) -> WhatIfResponse:
    return await whatif_svc.simulate(request)
