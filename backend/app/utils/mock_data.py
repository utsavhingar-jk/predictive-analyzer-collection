"""
Mock invoice portfolio used as a development/demo dataset.

In production, replace with live database queries. The same invoice IDs
are referenced across prediction, prioritization, and forecast services.
"""

from datetime import date, timedelta

today = date.today()


MOCK_INVOICES = [
    {
        "invoice_id": "INV-2024-001",
        "invoice_number": "INV-2024-001",
        "customer_name": "Apex Manufacturing Inc.",
        "customer_id": 1,
        "industry": "Manufacturing",
        "amount": 2_850_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=75),
        "due_date": today - timedelta(days=45),
        "status": "overdue",
        "days_overdue": 45,
        "risk_label": "High",
        "credit_score": 580,
        "avg_days_to_pay": 52.0,
        "num_late_payments": 5,
        "payment_terms": 30,
        "customer_total_overdue": 4_875_000.0,
        "pay_7_days": 0.08,
        "pay_15_days": 0.18,
        "pay_30_days": 0.32,
        "recommended_action": "Send Formal Demand Letter",
    },
    {
        "invoice_id": "INV-2024-002",
        "invoice_number": "INV-2024-002",
        "customer_name": "BlueSky Logistics Ltd.",
        "customer_id": 2,
        "industry": "Logistics",
        "amount": 1_425_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=50),
        "due_date": today - timedelta(days=20),
        "status": "overdue",
        "days_overdue": 20,
        "risk_label": "Medium",
        "credit_score": 680,
        "avg_days_to_pay": 38.0,
        "num_late_payments": 2,
        "payment_terms": 30,
        "customer_total_overdue": 1_425_000.0,
        "pay_7_days": 0.22,
        "pay_15_days": 0.45,
        "pay_30_days": 0.71,
        "recommended_action": "Make Collection Call",
    },
    {
        "invoice_id": "INV-2024-003",
        "invoice_number": "INV-2024-003",
        "customer_name": "GreenField Retail Corp.",
        "customer_id": 3,
        "industry": "Retail",
        "amount": 625_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=35),
        "due_date": today - timedelta(days=5),
        "status": "overdue",
        "days_overdue": 5,
        "risk_label": "Low",
        "credit_score": 760,
        "avg_days_to_pay": 29.0,
        "num_late_payments": 0,
        "payment_terms": 30,
        "customer_total_overdue": 625_000.0,
        "pay_7_days": 0.55,
        "pay_15_days": 0.80,
        "pay_30_days": 0.94,
        "recommended_action": "Send Payment Reminder Email",
    },
    {
        "invoice_id": "INV-2024-004",
        "invoice_number": "INV-2024-004",
        "customer_name": "TechNova Solutions",
        "customer_id": 4,
        "industry": "Technology",
        "amount": 4_250_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=110),
        "due_date": today - timedelta(days=80),
        "status": "overdue",
        "days_overdue": 80,
        "risk_label": "High",
        "credit_score": 540,
        "avg_days_to_pay": 72.0,
        "num_late_payments": 8,
        "payment_terms": 30,
        "customer_total_overdue": 7_250_000.0,
        "pay_7_days": 0.03,
        "pay_15_days": 0.07,
        "pay_30_days": 0.18,
        "recommended_action": "Escalate to Collections Agency",
    },
    {
        "invoice_id": "INV-2024-005",
        "invoice_number": "INV-2024-005",
        "customer_name": "Solaris Energy Partners",
        "customer_id": 5,
        "industry": "Energy",
        "amount": 2_250_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=45),
        "due_date": today + timedelta(days=15),
        "status": "open",
        "days_overdue": 0,
        "risk_label": "Medium",
        "credit_score": 710,
        "avg_days_to_pay": 33.0,
        "num_late_payments": 1,
        "payment_terms": 60,
        "customer_total_overdue": 0.0,
        "pay_7_days": 0.15,
        "pay_15_days": 0.62,
        "pay_30_days": 0.88,
        "recommended_action": "Send Payment Reminder Email",
    },
    {
        "invoice_id": "INV-2024-006",
        "invoice_number": "INV-2024-006",
        "customer_name": "NorthStar Healthcare",
        "customer_id": 6,
        "industry": "Healthcare",
        "amount": 1_050_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=60),
        "due_date": today - timedelta(days=30),
        "status": "overdue",
        "days_overdue": 30,
        "risk_label": "Medium",
        "credit_score": 645,
        "avg_days_to_pay": 44.0,
        "num_late_payments": 3,
        "payment_terms": 30,
        "customer_total_overdue": 1_050_000.0,
        "pay_7_days": 0.18,
        "pay_15_days": 0.38,
        "pay_30_days": 0.61,
        "recommended_action": "Schedule Payment Plan Discussion",
    },
    {
        "invoice_id": "INV-2024-007",
        "invoice_number": "INV-2024-007",
        "customer_name": "Pacific Steel Works",
        "customer_id": 7,
        "industry": "Manufacturing",
        "amount": 1_750_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=90),
        "due_date": today - timedelta(days=60),
        "status": "overdue",
        "days_overdue": 60,
        "risk_label": "High",
        "credit_score": 600,
        "avg_days_to_pay": 58.0,
        "num_late_payments": 6,
        "payment_terms": 30,
        "customer_total_overdue": 1_750_000.0,
        "pay_7_days": 0.05,
        "pay_15_days": 0.12,
        "pay_30_days": 0.26,
        "recommended_action": "Make Collection Call",
    },
    {
        "invoice_id": "INV-2024-008",
        "invoice_number": "INV-2024-008",
        "customer_name": "Clearwater Financial",
        "customer_id": 8,
        "industry": "Finance",
        "amount": 325_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=20),
        "due_date": today + timedelta(days=10),
        "status": "open",
        "days_overdue": 0,
        "risk_label": "Low",
        "credit_score": 800,
        "avg_days_to_pay": 22.0,
        "num_late_payments": 0,
        "payment_terms": 30,
        "customer_total_overdue": 0.0,
        "pay_7_days": 0.30,
        "pay_15_days": 0.85,
        "pay_30_days": 0.97,
        "recommended_action": "No Action Required",
    },
    {
        "invoice_id": "INV-2024-009",
        "invoice_number": "INV-2024-009",
        "customer_name": "Adani Infrastructure Ltd.",
        "customer_id": 9,
        "industry": "Infrastructure",
        "amount": 4_500_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=120),
        "due_date": today - timedelta(days=90),
        "status": "overdue",
        "days_overdue": 90,
        "risk_label": "High",
        "credit_score": 520,
        "avg_days_to_pay": 85.0,
        "num_late_payments": 9,
        "payment_terms": 30,
        "customer_total_overdue": 8_500_000.0,
        "pay_7_days": 0.02,
        "pay_15_days": 0.05,
        "pay_30_days": 0.14,
        "recommended_action": "Field Collection Visit",
    },
    {
        "invoice_id": "INV-2024-010",
        "invoice_number": "INV-2024-010",
        "customer_name": "Mahindra Auto Parts",
        "customer_id": 10,
        "industry": "Automotive",
        "amount": 875_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=42),
        "due_date": today - timedelta(days=12),
        "status": "overdue",
        "days_overdue": 12,
        "risk_label": "Medium",
        "credit_score": 670,
        "avg_days_to_pay": 36.0,
        "num_late_payments": 2,
        "payment_terms": 30,
        "customer_total_overdue": 875_000.0,
        "pay_7_days": 0.25,
        "pay_15_days": 0.52,
        "pay_30_days": 0.74,
        "recommended_action": "Collection Call",
    },
    {
        "invoice_id": "INV-2024-011",
        "invoice_number": "INV-2024-011",
        "customer_name": "Tata Chemicals Ltd.",
        "customer_id": 11,
        "industry": "Chemicals",
        "amount": 3_200_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=25),
        "due_date": today + timedelta(days=5),
        "status": "open",
        "days_overdue": 0,
        "risk_label": "Low",
        "credit_score": 780,
        "avg_days_to_pay": 27.0,
        "num_late_payments": 0,
        "payment_terms": 30,
        "customer_total_overdue": 0.0,
        "pay_7_days": 0.48,
        "pay_15_days": 0.79,
        "pay_30_days": 0.95,
        "recommended_action": "Automated Reminder",
    },
    {
        "invoice_id": "INV-2024-012",
        "invoice_number": "INV-2024-012",
        "customer_name": "Infosys Consulting Pvt. Ltd.",
        "customer_id": 12,
        "industry": "Technology",
        "amount": 525_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=52),
        "due_date": today - timedelta(days=22),
        "status": "overdue",
        "days_overdue": 22,
        "risk_label": "Medium",
        "credit_score": 720,
        "avg_days_to_pay": 40.0,
        "num_late_payments": 1,
        "payment_terms": 30,
        "customer_total_overdue": 525_000.0,
        "pay_7_days": 0.20,
        "pay_15_days": 0.44,
        "pay_30_days": 0.68,
        "recommended_action": "Follow-up Email + Call",
    },
    {
        "invoice_id": "INV-2024-013",
        "invoice_number": "INV-2024-013",
        "customer_name": "HDFC Leasing Co.",
        "customer_id": 13,
        "industry": "Finance",
        "amount": 1_250_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=85),
        "due_date": today - timedelta(days=55),
        "status": "overdue",
        "days_overdue": 55,
        "risk_label": "High",
        "credit_score": 595,
        "avg_days_to_pay": 62.0,
        "num_late_payments": 7,
        "payment_terms": 30,
        "customer_total_overdue": 2_750_000.0,
        "pay_7_days": 0.06,
        "pay_15_days": 0.14,
        "pay_30_days": 0.29,
        "recommended_action": "Collection Call + Email",
    },
    {
        "invoice_id": "INV-2024-014",
        "invoice_number": "INV-2024-014",
        "customer_name": "Sun Pharma Distributors",
        "customer_id": 14,
        "industry": "Healthcare",
        "amount": 975_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=18),
        "due_date": today + timedelta(days=12),
        "status": "open",
        "days_overdue": 0,
        "risk_label": "Low",
        "credit_score": 755,
        "avg_days_to_pay": 28.0,
        "num_late_payments": 0,
        "payment_terms": 30,
        "customer_total_overdue": 0.0,
        "pay_7_days": 0.35,
        "pay_15_days": 0.72,
        "pay_30_days": 0.93,
        "recommended_action": "Automated Payment Reminder",
    },
    {
        "invoice_id": "INV-2024-015",
        "invoice_number": "INV-2024-015",
        "customer_name": "Reliance Textiles Ltd.",
        "customer_id": 15,
        "industry": "Manufacturing",
        "amount": 1_850_000.0,
        "currency": "INR",
        "issue_date": today - timedelta(days=65),
        "due_date": today - timedelta(days=35),
        "status": "overdue",
        "days_overdue": 35,
        "risk_label": "High",
        "credit_score": 612,
        "avg_days_to_pay": 48.0,
        "num_late_payments": 4,
        "payment_terms": 30,
        "customer_total_overdue": 1_850_000.0,
        "pay_7_days": 0.10,
        "pay_15_days": 0.22,
        "pay_30_days": 0.40,
        "recommended_action": "Formal Demand Letter",
    },
]


def get_invoice_by_id(invoice_id: str) -> dict | None:
    return next((inv for inv in MOCK_INVOICES if inv["invoice_id"] == invoice_id), None)


def get_portfolio_summary() -> dict:
    total_outstanding = sum(
        inv["amount"] for inv in MOCK_INVOICES if inv["status"] in ("open", "overdue")
    )
    overdue_count = sum(1 for inv in MOCK_INVOICES if inv["status"] == "overdue")
    overdue_amount = sum(
        inv["amount"] for inv in MOCK_INVOICES if inv["status"] == "overdue"
    )
    # Amount at risk: invoices with delay_prob > 0.60
    amount_at_risk = sum(
        inv["amount"]
        for inv in MOCK_INVOICES
        if inv["status"] in ("open", "overdue") and (1 - inv.get("pay_30_days", 0.5)) > 0.60
    )
    risk_breakdown = {"High": 0, "Medium": 0, "Low": 0}
    for inv in MOCK_INVOICES:
        risk_breakdown[inv.get("risk_label", "Medium")] += 1

    high_risk_count = risk_breakdown["High"]

    return {
        "total_invoices": len(MOCK_INVOICES),
        "total_outstanding": total_outstanding,
        "overdue_count": overdue_count,
        "overdue_amount": overdue_amount,
        "amount_at_risk": amount_at_risk,
        "high_risk_count": high_risk_count,
        "risk_breakdown": risk_breakdown,
    }


# ─── Payment Behavior Profiles (pre-computed for demo customers) ──────────────

MOCK_BEHAVIOR_PROFILES = [
    {
        "customer_id": "1",
        "customer_name": "Apex Manufacturing Inc.",
        "behavior_type": "Chronic Delayed Payer",
        "on_time_ratio": 31.0,
        "avg_delay_days": 22.0,
        "trend": "Worsening",
        "payment_style": "Chronic Late + High DPD",
        "behavior_risk_score": 82.0,
        "followup_dependency": True,
        "nach_recommended": True,
        "behavior_summary": (
            "Apex Manufacturing Inc. is classified as a 'Chronic Delayed Payer'. "
            "On-time payment ratio is 31% with an average delay of 22 days. "
            "Payment trend is worsening. NACH/auto-debit is recommended. "
            "Behavior risk score: 82/100."
        ),
    },
    {
        "customer_id": "2",
        "customer_name": "BlueSky Logistics Ltd.",
        "behavior_type": "Occasional Late Payer",
        "on_time_ratio": 68.0,
        "avg_delay_days": 12.0,
        "trend": "Stable",
        "payment_style": "Mostly On-Time",
        "behavior_risk_score": 42.0,
        "followup_dependency": False,
        "nach_recommended": False,
        "behavior_summary": (
            "BlueSky Logistics Ltd. is classified as an 'Occasional Late Payer'. "
            "On-time payment ratio is 68% with an average delay of 12 days. "
            "Payment trend is stable. Behavior risk score: 42/100."
        ),
    },
    {
        "customer_id": "3",
        "customer_name": "GreenField Retail Corp.",
        "behavior_type": "Consistent Payer",
        "on_time_ratio": 92.0,
        "avg_delay_days": 3.0,
        "trend": "Improving",
        "payment_style": "Prompt + Autonomous",
        "behavior_risk_score": 8.0,
        "followup_dependency": False,
        "nach_recommended": False,
        "behavior_summary": (
            "GreenField Retail Corp. is classified as a 'Consistent Payer'. "
            "On-time payment ratio is 92% with an average delay of 3 days. "
            "Payment trend is improving. Behavior risk score: 8/100."
        ),
    },
    {
        "customer_id": "4",
        "customer_name": "TechNova Solutions",
        "behavior_type": "High Risk Defaulter",
        "on_time_ratio": 18.0,
        "avg_delay_days": 38.0,
        "trend": "Worsening",
        "payment_style": "Erratic + Non-Responsive",
        "behavior_risk_score": 94.0,
        "followup_dependency": True,
        "nach_recommended": True,
        "behavior_summary": (
            "TechNova Solutions is classified as a 'High Risk Defaulter'. "
            "On-time payment ratio is 18% with an average delay of 38 days. "
            "Payment trend is worsening. NACH/auto-debit is recommended. "
            "Behavior risk score: 94/100."
        ),
    },
    {
        "customer_id": "5",
        "customer_name": "Solaris Energy Partners",
        "behavior_type": "Occasional Late Payer",
        "on_time_ratio": 72.0,
        "avg_delay_days": 8.0,
        "trend": "Stable",
        "payment_style": "Mostly On-Time",
        "behavior_risk_score": 28.0,
        "followup_dependency": False,
        "nach_recommended": False,
        "behavior_summary": (
            "Solaris Energy Partners is classified as an 'Occasional Late Payer'. "
            "On-time payment ratio is 72% with an average delay of 8 days. "
            "Payment trend is stable. Behavior risk score: 28/100."
        ),
    },
    {
        "customer_id": "6",
        "customer_name": "NorthStar Healthcare",
        "behavior_type": "Reminder Driven Payer",
        "on_time_ratio": 52.0,
        "avg_delay_days": 18.0,
        "trend": "Stable",
        "payment_style": "Requires Follow-Up",
        "behavior_risk_score": 58.0,
        "followup_dependency": True,
        "nach_recommended": True,
        "behavior_summary": (
            "NorthStar Healthcare is classified as a 'Reminder Driven Payer'. "
            "On-time payment ratio is 52% with an average delay of 18 days. "
            "Payment trend is stable. NACH/auto-debit is recommended. "
            "Behavior risk score: 58/100."
        ),
    },
    {
        "customer_id": "7",
        "customer_name": "Pacific Steel Works",
        "behavior_type": "Chronic Delayed Payer",
        "on_time_ratio": 28.0,
        "avg_delay_days": 32.0,
        "trend": "Worsening",
        "payment_style": "Partial + Reminder Driven",
        "behavior_risk_score": 79.0,
        "followup_dependency": True,
        "nach_recommended": True,
        "behavior_summary": (
            "Pacific Steel Works is classified as a 'Chronic Delayed Payer'. "
            "On-time payment ratio is 28% with an average delay of 32 days. "
            "Payment trend is worsening. NACH/auto-debit is recommended. "
            "Behavior risk score: 79/100."
        ),
    },
    {
        "customer_id": "8",
        "customer_name": "Clearwater Financial",
        "behavior_type": "Consistent Payer",
        "on_time_ratio": 96.0,
        "avg_delay_days": 1.0,
        "trend": "Improving",
        "payment_style": "Prompt + Autonomous",
        "behavior_risk_score": 4.0,
        "followup_dependency": False,
        "nach_recommended": False,
        "behavior_summary": (
            "Clearwater Financial is classified as a 'Consistent Payer'. "
            "On-time payment ratio is 96% with an average delay of 1 day. "
            "Payment trend is improving. Behavior risk score: 4/100."
        ),
    },
    {
        "customer_id": "9",
        "customer_name": "Adani Infrastructure Ltd.",
        "behavior_type": "High Risk Defaulter",
        "on_time_ratio": 12.0,
        "avg_delay_days": 55.0,
        "trend": "Worsening",
        "payment_style": "Erratic + Non-Responsive",
        "behavior_risk_score": 96.0,
        "followup_dependency": True,
        "nach_recommended": True,
        "behavior_summary": (
            "Adani Infrastructure Ltd. is classified as a 'High Risk Defaulter'. "
            "On-time payment ratio is 12% with an average delay of 55 days. "
            "Payment trend is worsening. NACH/auto-debit is recommended. "
            "Behavior risk score: 96/100."
        ),
    },
    {
        "customer_id": "10",
        "customer_name": "Mahindra Auto Parts",
        "behavior_type": "Occasional Late Payer",
        "on_time_ratio": 65.0,
        "avg_delay_days": 14.0,
        "trend": "Stable",
        "payment_style": "Mostly On-Time",
        "behavior_risk_score": 38.0,
        "followup_dependency": False,
        "nach_recommended": False,
        "behavior_summary": (
            "Mahindra Auto Parts is classified as an 'Occasional Late Payer'. "
            "On-time payment ratio is 65% with an average delay of 14 days. "
            "Payment trend is stable. Behavior risk score: 38/100."
        ),
    },
    {
        "customer_id": "11",
        "customer_name": "Tata Chemicals Ltd.",
        "behavior_type": "Consistent Payer",
        "on_time_ratio": 94.0,
        "avg_delay_days": 2.0,
        "trend": "Stable",
        "payment_style": "Prompt + Autonomous",
        "behavior_risk_score": 6.0,
        "followup_dependency": False,
        "nach_recommended": False,
        "behavior_summary": (
            "Tata Chemicals Ltd. is classified as a 'Consistent Payer'. "
            "On-time payment ratio is 94% with an average delay of 2 days. "
            "Payment trend is stable. Behavior risk score: 6/100."
        ),
    },
    {
        "customer_id": "12",
        "customer_name": "Infosys Consulting Pvt. Ltd.",
        "behavior_type": "Reminder Driven Payer",
        "on_time_ratio": 55.0,
        "avg_delay_days": 16.0,
        "trend": "Stable",
        "payment_style": "Requires Follow-Up",
        "behavior_risk_score": 45.0,
        "followup_dependency": True,
        "nach_recommended": False,
        "behavior_summary": (
            "Infosys Consulting Pvt. Ltd. is classified as a 'Reminder Driven Payer'. "
            "On-time payment ratio is 55% with an average delay of 16 days. "
            "Payment trend is stable. Behavior risk score: 45/100."
        ),
    },
    {
        "customer_id": "13",
        "customer_name": "HDFC Leasing Co.",
        "behavior_type": "Chronic Delayed Payer",
        "on_time_ratio": 24.0,
        "avg_delay_days": 42.0,
        "trend": "Worsening",
        "payment_style": "Chronic Late + High DPD",
        "behavior_risk_score": 88.0,
        "followup_dependency": True,
        "nach_recommended": True,
        "behavior_summary": (
            "HDFC Leasing Co. is classified as a 'Chronic Delayed Payer'. "
            "On-time payment ratio is 24% with an average delay of 42 days. "
            "Payment trend is worsening. NACH/auto-debit is recommended. "
            "Behavior risk score: 88/100."
        ),
    },
    {
        "customer_id": "14",
        "customer_name": "Sun Pharma Distributors",
        "behavior_type": "Consistent Payer",
        "on_time_ratio": 89.0,
        "avg_delay_days": 4.0,
        "trend": "Improving",
        "payment_style": "Prompt + Autonomous",
        "behavior_risk_score": 11.0,
        "followup_dependency": False,
        "nach_recommended": False,
        "behavior_summary": (
            "Sun Pharma Distributors is classified as a 'Consistent Payer'. "
            "On-time payment ratio is 89% with an average delay of 4 days. "
            "Payment trend is improving. Behavior risk score: 11/100."
        ),
    },
    {
        "customer_id": "15",
        "customer_name": "Reliance Textiles Ltd.",
        "behavior_type": "Chronic Delayed Payer",
        "on_time_ratio": 35.0,
        "avg_delay_days": 28.0,
        "trend": "Worsening",
        "payment_style": "Partial + Reminder Driven",
        "behavior_risk_score": 76.0,
        "followup_dependency": True,
        "nach_recommended": True,
        "behavior_summary": (
            "Reliance Textiles Ltd. is classified as a 'Chronic Delayed Payer'. "
            "On-time payment ratio is 35% with an average delay of 28 days. "
            "Payment trend is worsening. NACH/auto-debit is recommended. "
            "Behavior risk score: 76/100."
        ),
    },
]


def get_behavior_by_customer_id(customer_id: str) -> dict | None:
    return next(
        (p for p in MOCK_BEHAVIOR_PROFILES if p["customer_id"] == customer_id), None
    )
