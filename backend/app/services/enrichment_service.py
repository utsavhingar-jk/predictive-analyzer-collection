"""
Borrower Enrichment Service — CredCheck Signal Layer.

Provides MCA compliance, GST filing health, EPFO workforce stability,
credit bureau summary, legal profile, and data availability flags.

In production: integrate with CredCheck API / CredServ enrichment tables.
Currently: realistic mock data per customer.
"""

import logging
from datetime import date

from app.schemas.enrichment import (
    BorrowerEnrichmentResponse,
    CreditBureauProfile,
    DataAvailabilityFlags,
    EPFOStabilityProfile,
    GSTComplianceProfile,
    LegalProfile,
    MCAComplianceProfile,
)
from app.utils.mock_data import MOCK_INVOICES

logger = logging.getLogger(__name__)

TODAY = date.today().isoformat()

# ── Mock enrichment data per customer_id ──────────────────────────────────────

_ENRICHMENT_DB: dict[str, dict] = {
    "1": {  # Apex Manufacturing Inc.
        "data_availability": DataAvailabilityFlags(
            has_bureau_data=True, has_gst_data=True, has_legal_data=False,
            has_mca_data=True, has_epfo_data=True, has_digitap_data=False,
            completeness_score=67,
        ),
        "mca": MCAComplianceProfile(
            mca_status="Active", company_age_years=12,
            last_filing_date="2024-09-30", filing_delay_days=15,
            compliance_score=72, flag=None,
        ),
        "gst": GSTComplianceProfile(
            gst_registered=True, filing_score=68,
            last_filed_date="2024-03-20", delay_band="1-30 days late",
            avg_turnover_band="₹10-100Cr", itc_health="Mismatch Risk",
        ),
        "epfo": EPFOStabilityProfile(
            epfo_registered=True, employee_count=340,
            pf_trend="Stable", pf_default_risk=False, stability_score=74,
        ),
        "bureau": CreditBureauProfile(
            total_borrowing=85_000_000.0, open_loan_count=4, overdue_count=2,
            cheque_dishonour_count=1, dpd_classification="Sub-standard",
            wilful_default=False, suits_filed=0, bureau_score=580,
            credit_health_label="Moderate",
        ),
        "legal": LegalProfile(
            total_cases=0, active_suits=0, cases_by_category={},
            high_court_cases=0, nclt_risk=False, legal_risk_label="Clean",
        ),
        "enrichment_score": 68,
        "risk_flags": ["GST filing delays", "2 bureau overdues", "Sub-standard DPD"],
    },
    "2": {  # BlueSky Logistics Ltd.
        "data_availability": DataAvailabilityFlags(
            has_bureau_data=True, has_gst_data=True, has_legal_data=False,
            has_mca_data=True, has_epfo_data=False, has_digitap_data=False,
            completeness_score=50,
        ),
        "mca": MCAComplianceProfile(
            mca_status="Active", company_age_years=8,
            last_filing_date="2024-09-30", filing_delay_days=5,
            compliance_score=85, flag=None,
        ),
        "gst": GSTComplianceProfile(
            gst_registered=True, filing_score=80,
            last_filed_date="2024-03-10", delay_band="Current",
            avg_turnover_band="₹1-10Cr", itc_health="Healthy",
        ),
        "epfo": EPFOStabilityProfile(
            epfo_registered=False, employee_count=None,
            pf_trend="Unknown", pf_default_risk=False, stability_score=50,
        ),
        "bureau": CreditBureauProfile(
            total_borrowing=28_000_000.0, open_loan_count=2, overdue_count=1,
            cheque_dishonour_count=0, dpd_classification="Standard",
            wilful_default=False, suits_filed=0, bureau_score=680,
            credit_health_label="Moderate",
        ),
        "legal": LegalProfile(
            total_cases=0, active_suits=0, cases_by_category={},
            nclt_risk=False, legal_risk_label="Clean",
        ),
        "enrichment_score": 74,
        "risk_flags": [],
    },
    "4": {  # TechNova Solutions — critical risk
        "data_availability": DataAvailabilityFlags(
            has_bureau_data=True, has_gst_data=True, has_legal_data=True,
            has_mca_data=True, has_epfo_data=True, has_digitap_data=False,
            completeness_score=83,
        ),
        "mca": MCAComplianceProfile(
            mca_status="Strike-off Notice", company_age_years=6,
            last_filing_date="2023-06-30", filing_delay_days=270,
            compliance_score=22, flag="Strike-off risk — non-compliant for 9 months",
        ),
        "gst": GSTComplianceProfile(
            gst_registered=True, filing_score=30,
            last_filed_date="2023-12-15", delay_band="31-90 days late",
            avg_turnover_band="₹10-100Cr", itc_health="Mismatch Risk",
        ),
        "epfo": EPFOStabilityProfile(
            epfo_registered=True, employee_count=89,
            pf_trend="Declining", pf_default_risk=True, stability_score=28,
        ),
        "bureau": CreditBureauProfile(
            total_borrowing=210_000_000.0, open_loan_count=7, overdue_count=5,
            cheque_dishonour_count=4, dpd_classification="Doubtful",
            wilful_default=False, suits_filed=2, bureau_score=480,
            credit_health_label="Distressed",
        ),
        "legal": LegalProfile(
            total_cases=3, active_suits=2, cases_by_category={"civil": 2, "tax": 1},
            high_court_cases=1, nclt_risk=True, legal_risk_label="Critical",
        ),
        "enrichment_score": 22,
        "risk_flags": [
            "MCA strike-off notice",
            "NCLT risk detected",
            "EPFO PF defaults",
            "Doubtful DPD classification",
            "5 bureau overdues",
            "GST filing suspended",
            "4 cheque dishonours",
        ],
    },
    "7": {  # Pacific Steel Works
        "data_availability": DataAvailabilityFlags(
            has_bureau_data=True, has_gst_data=True, has_legal_data=False,
            has_mca_data=True, has_epfo_data=True, has_digitap_data=False,
            completeness_score=67,
        ),
        "mca": MCAComplianceProfile(
            mca_status="Active", company_age_years=18,
            last_filing_date="2024-09-30", filing_delay_days=0,
            compliance_score=88, flag=None,
        ),
        "gst": GSTComplianceProfile(
            gst_registered=True, filing_score=72,
            last_filed_date="2024-03-15", delay_band="1-30 days late",
            avg_turnover_band="₹10-100Cr", itc_health="Healthy",
        ),
        "epfo": EPFOStabilityProfile(
            epfo_registered=True, employee_count=620,
            pf_trend="Declining", pf_default_risk=False, stability_score=62,
        ),
        "bureau": CreditBureauProfile(
            total_borrowing=145_000_000.0, open_loan_count=5, overdue_count=2,
            cheque_dishonour_count=1, dpd_classification="Sub-standard",
            wilful_default=False, suits_filed=1, bureau_score=610,
            credit_health_label="Moderate",
        ),
        "legal": LegalProfile(
            total_cases=1, active_suits=0, cases_by_category={"civil": 1},
            nclt_risk=False, legal_risk_label="Minor",
        ),
        "enrichment_score": 62,
        "risk_flags": ["Steel sector pressure", "EPFO headcount declining", "1 bureau overdue"],
    },
    "9": {  # Adani Infrastructure Ltd. — critical
        "data_availability": DataAvailabilityFlags(
            has_bureau_data=True, has_gst_data=False, has_legal_data=True,
            has_mca_data=True, has_epfo_data=True, has_digitap_data=False,
            completeness_score=67,
        ),
        "mca": MCAComplianceProfile(
            mca_status="Active", company_age_years=14,
            last_filing_date="2024-03-31", filing_delay_days=45,
            compliance_score=58, flag="Annual filing overdue",
        ),
        "gst": GSTComplianceProfile(
            gst_registered=True, filing_score=40,
            last_filed_date="2024-01-20", delay_band="31-90 days late",
            avg_turnover_band=">₹100Cr", itc_health="Unknown",
        ),
        "epfo": EPFOStabilityProfile(
            epfo_registered=True, employee_count=1200,
            pf_trend="Stable", pf_default_risk=False, stability_score=70,
        ),
        "bureau": CreditBureauProfile(
            total_borrowing=580_000_000.0, open_loan_count=12, overdue_count=4,
            cheque_dishonour_count=2, dpd_classification="Doubtful",
            wilful_default=False, suits_filed=3, bureau_score=510,
            credit_health_label="Weak",
        ),
        "legal": LegalProfile(
            total_cases=4, active_suits=3, cases_by_category={"civil": 2, "regulatory": 2},
            high_court_cases=2, nclt_risk=False, legal_risk_label="Significant",
        ),
        "enrichment_score": 38,
        "risk_flags": [
            "Regulatory inquiry active",
            "AP contact unreachable",
            "4 bureau overdues",
            "GST filing stale",
            "3 active legal suits",
        ],
    },
    "13": {  # HDFC Leasing Co.
        "data_availability": DataAvailabilityFlags(
            has_bureau_data=True, has_gst_data=True, has_legal_data=False,
            has_mca_data=True, has_epfo_data=False, has_digitap_data=False,
            completeness_score=50,
        ),
        "mca": MCAComplianceProfile(
            mca_status="Active", company_age_years=22,
            last_filing_date="2024-09-30", filing_delay_days=0,
            compliance_score=90, flag=None,
        ),
        "gst": GSTComplianceProfile(
            gst_registered=True, filing_score=85,
            last_filed_date="2024-03-28", delay_band="Current",
            avg_turnover_band=">₹100Cr", itc_health="Healthy",
        ),
        "epfo": EPFOStabilityProfile(
            epfo_registered=False, employee_count=None,
            pf_trend="Unknown", pf_default_risk=False, stability_score=60,
        ),
        "bureau": CreditBureauProfile(
            total_borrowing=1_200_000_000.0, open_loan_count=18, overdue_count=1,
            cheque_dishonour_count=0, dpd_classification="Standard",
            wilful_default=False, suits_filed=0, bureau_score=720,
            credit_health_label="Strong",
        ),
        "legal": LegalProfile(
            total_cases=0, active_suits=0, cases_by_category={},
            nclt_risk=False, legal_risk_label="Clean",
        ),
        "enrichment_score": 76,
        "risk_flags": ["New CFO — payment approval delay expected"],
    },
    "15": {  # Reliance Textiles Ltd.
        "data_availability": DataAvailabilityFlags(
            has_bureau_data=True, has_gst_data=True, has_legal_data=True,
            has_mca_data=True, has_epfo_data=True, has_digitap_data=False,
            completeness_score=83,
        ),
        "mca": MCAComplianceProfile(
            mca_status="Active", company_age_years=25,
            last_filing_date="2024-09-30", filing_delay_days=0,
            compliance_score=82, flag=None,
        ),
        "gst": GSTComplianceProfile(
            gst_registered=True, filing_score=45,
            last_filed_date="2024-02-10", delay_band="31-90 days late",
            avg_turnover_band="₹10-100Cr", itc_health="Mismatch Risk",
        ),
        "epfo": EPFOStabilityProfile(
            epfo_registered=True, employee_count=480,
            pf_trend="Stable", pf_default_risk=False, stability_score=68,
        ),
        "bureau": CreditBureauProfile(
            total_borrowing=320_000_000.0, open_loan_count=8, overdue_count=3,
            cheque_dishonour_count=2, dpd_classification="Sub-standard",
            wilful_default=False, suits_filed=1, bureau_score=570,
            credit_health_label="Weak",
        ),
        "legal": LegalProfile(
            total_cases=2, active_suits=1, cases_by_category={"tax": 2},
            high_court_cases=0, nclt_risk=False, legal_risk_label="Minor",
        ),
        "enrichment_score": 52,
        "risk_flags": ["GST audit dispute", "3 bureau overdues", "GST filing delays"],
    },
}

# Default for customers not in the enrichment DB
_DEFAULT_ENRICHMENT_SCORE = 55
_DEFAULT_DATA_FLAGS = DataAvailabilityFlags(
    has_bureau_data=True, has_gst_data=True,
    has_mca_data=True, has_epfo_data=False, has_digitap_data=False,
    completeness_score=50,
)


class EnrichmentService:

    def get_enrichment(self, customer_id: str) -> BorrowerEnrichmentResponse:
        """Return the CredCheck enrichment profile for a customer."""
        customer_id = str(customer_id)

        inv = next(
            (i for i in MOCK_INVOICES if str(i["customer_id"]) == customer_id),
            None,
        )
        customer_name = inv["customer_name"] if inv else f"Customer {customer_id}"
        industry = inv.get("industry", "unknown") if inv else "unknown"

        data = _ENRICHMENT_DB.get(customer_id)

        if data:
            label = (
                "Data-Rich" if data["enrichment_score"] >= 70
                else "Moderate" if data["enrichment_score"] >= 45
                else "Sparse"
            )
            return BorrowerEnrichmentResponse(
                customer_id=customer_id,
                customer_name=customer_name,
                industry=industry,
                data_availability=data["data_availability"],
                mca=data["mca"],
                gst=data["gst"],
                epfo=data["epfo"],
                bureau=data["bureau"],
                legal=data["legal"],
                enrichment_score=data["enrichment_score"],
                enrichment_label=label,
                risk_flags=data["risk_flags"],
                last_enriched=TODAY,
            )

        # Fallback for customers without detailed enrichment
        return BorrowerEnrichmentResponse(
            customer_id=customer_id,
            customer_name=customer_name,
            industry=industry,
            data_availability=_DEFAULT_DATA_FLAGS,
            mca=MCAComplianceProfile(
                mca_status="Active", company_age_years=5,
                last_filing_date=TODAY, filing_delay_days=0,
                compliance_score=75,
            ),
            gst=GSTComplianceProfile(
                gst_registered=True, filing_score=75,
                last_filed_date=TODAY, delay_band="Current",
                avg_turnover_band="₹1-10Cr",
            ),
            epfo=EPFOStabilityProfile(
                epfo_registered=False, pf_trend="Unknown", stability_score=55,
            ),
            bureau=CreditBureauProfile(
                total_borrowing=0, open_loan_count=0, overdue_count=0,
                cheque_dishonour_count=0, dpd_classification="Standard",
                credit_health_label="Unknown",
            ),
            legal=LegalProfile(
                total_cases=0, active_suits=0, cases_by_category={},
                legal_risk_label="Clean",
            ),
            enrichment_score=_DEFAULT_ENRICHMENT_SCORE,
            enrichment_label="Moderate",
            risk_flags=[],
            last_enriched=TODAY,
        )
