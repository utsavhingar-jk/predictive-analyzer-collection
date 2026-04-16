"""
Pydantic schemas for Borrower Enrichment (CredCheck signals).

Maps to: MCA compliance, GST filing health, EPFO stability,
credit bureau health, legal profile, and data availability flags.
"""

from typing import Optional
from pydantic import BaseModel, Field


class DataAvailabilityFlags(BaseModel):
    """Indicates which data families are present for this borrower."""

    has_bureau_data: bool = False
    has_gst_data: bool = False
    has_legal_data: bool = False
    has_mca_data: bool = False
    has_epfo_data: bool = False
    has_digitap_data: bool = False
    consent_available: bool = True
    fetch_failed: bool = False
    completeness_score: int = Field(default=0, ge=0, le=100)  # % of data families present


class MCAComplianceProfile(BaseModel):
    """Ministry of Corporate Affairs compliance signals."""

    mca_status: str              # "Active" | "Strike-off Notice" | "Inactive" | "Unknown"
    company_age_years: int
    last_filing_date: Optional[str] = None
    filing_delay_days: Optional[int] = None
    compliance_score: int = Field(..., ge=0, le=100)
    flag: Optional[str] = None  # e.g. "Strike-off risk" | "Director disqualification"


class GSTComplianceProfile(BaseModel):
    """GST filing health and discipline signals."""

    gst_registered: bool
    filing_score: int = Field(..., ge=0, le=100)   # 0=chronic defaulter, 100=always on time
    last_filed_date: Optional[str] = None
    delay_band: str  # "Current" | "1-30 days late" | "31-90 days late" | "Defaulter" | "Suspended"
    avg_turnover_band: Optional[str] = None        # "< ₹1Cr" | "₹1-10Cr" | "₹10-100Cr" | ">₹100Cr"
    itc_health: Optional[str] = None               # "Healthy" | "Mismatch Risk" | "Unknown"


class EPFOStabilityProfile(BaseModel):
    """Employee Provident Fund Organisation signals — workforce stability proxy."""

    epfo_registered: bool
    employee_count: Optional[int] = None
    pf_trend: str  # "Growing" | "Stable" | "Declining" | "Unknown"
    pf_default_risk: bool = False
    stability_score: int = Field(..., ge=0, le=100)


class CreditBureauProfile(BaseModel):
    """Credit health summary from bureau / CredCheck report."""

    total_borrowing: float            # INR
    open_loan_count: int
    overdue_count: int
    cheque_dishonour_count: int
    dpd_classification: str          # "Standard" | "Sub-standard" | "Doubtful" | "Loss"
    wilful_default: bool = False
    suits_filed: int = 0
    bureau_score: Optional[int] = None  # CIBIL / Equifax / Experian score
    credit_health_label: str         # "Strong" | "Moderate" | "Weak" | "Distressed"


class LegalProfile(BaseModel):
    """Legal case summary from CredCheck."""

    total_cases: int
    active_suits: int
    cases_by_category: dict          # {"civil": 2, "tax": 1}
    high_court_cases: int = 0
    nclt_risk: bool = False
    legal_risk_label: str           # "Clean" | "Minor" | "Significant" | "Critical"


class BorrowerEnrichmentResponse(BaseModel):
    """Full CredCheck enrichment profile for a borrower."""

    customer_id: str
    customer_name: str
    industry: str

    data_availability: DataAvailabilityFlags
    mca: MCAComplianceProfile
    gst: GSTComplianceProfile
    epfo: EPFOStabilityProfile
    bureau: CreditBureauProfile
    legal: LegalProfile

    # Overall enrichment health
    enrichment_score: int = Field(..., ge=0, le=100)
    enrichment_label: str   # "Data-Rich" | "Moderate" | "Sparse"
    risk_flags: list[str]   # Active flags from all data families combined
    last_enriched: str      # ISO date
