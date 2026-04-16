"""
Mock Collections Interaction History.

Simulates real-world call logs, email trails, PTP records, and field visit notes
for each invoice in the portfolio.

In production, this data would come from the collections CRM / operations table.
"""

# ── Interaction history per invoice ──────────────────────────────────────────
# outcome values: collected_full | collected_partial | ptp_given | broken_ptp
#                 no_answer | refused | dispute_raised | no_response | escalated

MOCK_INTERACTIONS: list[dict] = [

    # ── INV-2024-001 · Apex Manufacturing (₹28.5L, 45 DPD, chronic payer) ────

    {"interaction_id": "INT-001-01", "invoice_id": "INV-2024-001", "customer_id": "1",
     "customer_name": "Apex Manufacturing Inc.", "action_type": "Email",
     "channel": "email", "outcome": "no_response", "date": "2024-03-01",
     "collector_name": "Priya Sharma", "notes": "Automated reminder sent. No reply after 4 days.",
     "amount_recovered": None, "ptp_amount": None, "ptp_date": None, "broken_ptp": False},

    {"interaction_id": "INT-001-02", "invoice_id": "INV-2024-001", "customer_id": "1",
     "customer_name": "Apex Manufacturing Inc.", "action_type": "Call",
     "channel": "phone", "outcome": "ptp_given", "date": "2024-03-06",
     "collector_name": "Priya Sharma", "ptp_amount": 1_425_000.0, "ptp_date": "2024-03-20",
     "notes": "Spoke to AP manager. Promised 50% payment by March 20.", "broken_ptp": False},

    {"interaction_id": "INT-001-03", "invoice_id": "INV-2024-001", "customer_id": "1",
     "customer_name": "Apex Manufacturing Inc.", "action_type": "Call",
     "channel": "phone", "outcome": "broken_ptp", "date": "2024-03-22",
     "collector_name": "Priya Sharma", "ptp_amount": 1_425_000.0,
     "notes": "PTP of ₹14.25L not honoured. AP claims factory shutdown delayed payments.", "broken_ptp": True},

    {"interaction_id": "INT-001-04", "invoice_id": "INV-2024-001", "customer_id": "1",
     "customer_name": "Apex Manufacturing Inc.", "action_type": "Legal Notice",
     "channel": "legal", "outcome": "collected_partial", "date": "2024-03-28",
     "collector_name": "Rahul Verma", "amount_recovered": 855_000.0,
     "notes": "Formal demand letter triggered ₹8.55L partial payment. Balance pending.", "broken_ptp": False},

    {"interaction_id": "INT-001-05", "invoice_id": "INV-2024-001", "customer_id": "1",
     "customer_name": "Apex Manufacturing Inc.", "action_type": "Call",
     "channel": "phone", "outcome": "no_answer", "date": "2024-04-05",
     "collector_name": "Priya Sharma", "notes": "3 call attempts. Voicemail left.", "broken_ptp": False},

    # ── INV-2024-002 · BlueSky Logistics (₹14.25L, 20 DPD, reminder-driven) ─

    {"interaction_id": "INT-002-01", "invoice_id": "INV-2024-002", "customer_id": "2",
     "customer_name": "BlueSky Logistics Ltd.", "action_type": "Email",
     "channel": "email", "outcome": "no_response", "date": "2024-03-15",
     "collector_name": "Anjali Patel", "notes": "Standard overdue reminder.", "broken_ptp": False},

    {"interaction_id": "INT-002-02", "invoice_id": "INV-2024-002", "customer_id": "2",
     "customer_name": "BlueSky Logistics Ltd.", "action_type": "Call",
     "channel": "phone", "outcome": "ptp_given", "date": "2024-03-19",
     "collector_name": "Anjali Patel", "ptp_amount": 712_500.0, "ptp_date": "2024-03-28",
     "notes": "Customer responsive. Committed to 50% by month end.", "broken_ptp": False},

    {"interaction_id": "INT-002-03", "invoice_id": "INV-2024-002", "customer_id": "2",
     "customer_name": "BlueSky Logistics Ltd.", "action_type": "Call",
     "channel": "phone", "outcome": "collected_partial", "date": "2024-03-29",
     "collector_name": "Anjali Patel", "amount_recovered": 712_500.0,
     "notes": "PTP honoured. ₹7.125L received. Balance in next cycle.", "broken_ptp": False},

    # ── INV-2024-003 · Greenfield Pharma (₹18.75L, 5 DPD, reliable payer) ────

    {"interaction_id": "INT-003-01", "invoice_id": "INV-2024-003", "customer_id": "3",
     "customer_name": "Greenfield Pharma Ltd.", "action_type": "Email",
     "channel": "email", "outcome": "ptp_given", "date": "2024-04-02",
     "collector_name": "Anjali Patel", "ptp_amount": 1_875_000.0, "ptp_date": "2024-04-10",
     "notes": "Customer acknowledged invoice. Full payment committed within 5 days.", "broken_ptp": False},

    # ── INV-2024-004 · TechNova Solutions (₹42.5L, 80 DPD, critical risk) ────

    {"interaction_id": "INT-004-01", "invoice_id": "INV-2024-004", "customer_id": "4",
     "customer_name": "TechNova Solutions", "action_type": "Email",
     "channel": "email", "outcome": "no_response", "date": "2024-02-15",
     "collector_name": "Rohit Mehta", "notes": "Sent overdue notice. No reply.", "broken_ptp": False},

    {"interaction_id": "INT-004-02", "invoice_id": "INV-2024-004", "customer_id": "4",
     "customer_name": "TechNova Solutions", "action_type": "Call",
     "channel": "phone", "outcome": "no_answer", "date": "2024-02-22",
     "collector_name": "Rohit Mehta", "notes": "5 attempts over 3 days. No connection.", "broken_ptp": False},

    {"interaction_id": "INT-004-03", "invoice_id": "INV-2024-004", "customer_id": "4",
     "customer_name": "TechNova Solutions", "action_type": "Call",
     "channel": "phone", "outcome": "refused", "date": "2024-03-01",
     "collector_name": "Rohit Mehta", "notes": "Reached accounts manager who stated invoice is disputed.", "broken_ptp": False},

    {"interaction_id": "INT-004-04", "invoice_id": "INV-2024-004", "customer_id": "4",
     "customer_name": "TechNova Solutions", "action_type": "Legal Notice",
     "channel": "legal", "outcome": "dispute_raised", "date": "2024-03-10",
     "collector_name": "Legal Team", "notes": "Formal demand letter issued. Customer raised formal dispute via registered post.", "broken_ptp": False},

    {"interaction_id": "INT-004-05", "invoice_id": "INV-2024-004", "customer_id": "4",
     "customer_name": "TechNova Solutions", "action_type": "Field Visit",
     "channel": "in_person", "outcome": "ptp_given", "date": "2024-03-20",
     "collector_name": "Field Team", "ptp_amount": 21_250_000.0, "ptp_date": "2024-04-01",
     "notes": "Met CFO in person. Dispute acknowledged as billing error. 50% PTP given.", "broken_ptp": False},

    {"interaction_id": "INT-004-06", "invoice_id": "INV-2024-004", "customer_id": "4",
     "customer_name": "TechNova Solutions", "action_type": "Call",
     "channel": "phone", "outcome": "broken_ptp", "date": "2024-04-03",
     "collector_name": "Rohit Mehta", "ptp_amount": 21_250_000.0,
     "notes": "PTP not honoured. Company claims CFO resignation delayed payment authorization.", "broken_ptp": True},

    # ── INV-2024-005 · Sunrise Healthcare (₹33.5L, 0 DPD, open) ─────────────

    {"interaction_id": "INT-005-01", "invoice_id": "INV-2024-005", "customer_id": "5",
     "customer_name": "Sunrise Healthcare Systems", "action_type": "Email",
     "channel": "email", "outcome": "no_response", "date": "2024-04-01",
     "collector_name": "Anjali Patel", "notes": "Pre-due reminder sent. Awaiting confirmation.", "broken_ptp": False},

    # ── INV-2024-006 · Metro Retail Chain (₹19.5L, 30 DPD) ────────────────────

    {"interaction_id": "INT-006-01", "invoice_id": "INV-2024-006", "customer_id": "6",
     "customer_name": "Metro Retail Chain", "action_type": "Email",
     "channel": "email", "outcome": "no_response", "date": "2024-03-20",
     "collector_name": "Priya Sharma", "notes": "Reminder sent. No reply.", "broken_ptp": False},

    {"interaction_id": "INT-006-02", "invoice_id": "INV-2024-006", "customer_id": "6",
     "customer_name": "Metro Retail Chain", "action_type": "Call",
     "channel": "phone", "outcome": "ptp_given", "date": "2024-03-25",
     "collector_name": "Priya Sharma", "ptp_amount": 975_000.0, "ptp_date": "2024-04-05",
     "notes": "AP confirmed seasonal cash crunch. PTP ₹9.75L by April 5.", "broken_ptp": False},

    # ── INV-2024-007 · Pacific Steel Works (₹28.5L, 60 DPD) ─────────────────

    {"interaction_id": "INT-007-01", "invoice_id": "INV-2024-007", "customer_id": "7",
     "customer_name": "Pacific Steel Works", "action_type": "Email",
     "channel": "email", "outcome": "no_response", "date": "2024-02-20",
     "collector_name": "Rohit Mehta", "notes": "First reminder. No response.", "broken_ptp": False},

    {"interaction_id": "INT-007-02", "invoice_id": "INV-2024-007", "customer_id": "7",
     "customer_name": "Pacific Steel Works", "action_type": "Call",
     "channel": "phone", "outcome": "ptp_given", "date": "2024-03-01",
     "collector_name": "Rohit Mehta", "ptp_amount": 1_425_000.0, "ptp_date": "2024-03-15",
     "notes": "Spoke to finance manager. 50% PTP.", "broken_ptp": False},

    {"interaction_id": "INT-007-03", "invoice_id": "INV-2024-007", "customer_id": "7",
     "customer_name": "Pacific Steel Works", "action_type": "Call",
     "channel": "phone", "outcome": "broken_ptp", "date": "2024-03-17",
     "collector_name": "Rohit Mehta", "notes": "PTP not met. Steel export ban impacted cash flow.", "broken_ptp": True},

    {"interaction_id": "INT-007-04", "invoice_id": "INV-2024-007", "customer_id": "7",
     "customer_name": "Pacific Steel Works", "action_type": "Legal Notice",
     "channel": "legal", "outcome": "collected_partial", "date": "2024-03-28",
     "collector_name": "Legal Team", "amount_recovered": 855_000.0,
     "notes": "Demand notice triggered ₹8.55L. Still ₹19.95L outstanding.", "broken_ptp": False},

    # ── INV-2024-008 · Coastal Constructions (₹8.5L, 0 DPD) ─────────────────

    {"interaction_id": "INT-008-01", "invoice_id": "INV-2024-008", "customer_id": "8",
     "customer_name": "Coastal Constructions Ltd.", "action_type": "Email",
     "channel": "email", "outcome": "ptp_given", "date": "2024-04-08",
     "collector_name": "Anjali Patel", "ptp_amount": 850_000.0, "ptp_date": "2024-04-15",
     "notes": "Payment confirmed in advance. Strong payer.", "broken_ptp": False},

    # ── INV-2024-009 · Adani Infrastructure (₹38.5L, 55 DPD, critical) ───────

    {"interaction_id": "INT-009-01", "invoice_id": "INV-2024-009", "customer_id": "9",
     "customer_name": "Adani Infrastructure Ltd.", "action_type": "Email",
     "channel": "email", "outcome": "no_response", "date": "2024-02-25",
     "collector_name": "Rohit Mehta", "notes": "No response to 3 email reminders over 10 days.", "broken_ptp": False},

    {"interaction_id": "INT-009-02", "invoice_id": "INV-2024-009", "customer_id": "9",
     "customer_name": "Adani Infrastructure Ltd.", "action_type": "Call",
     "channel": "phone", "outcome": "no_answer", "date": "2024-03-05",
     "collector_name": "Rohit Mehta", "notes": "AP contact number consistently unreachable.", "broken_ptp": False},

    {"interaction_id": "INT-009-03", "invoice_id": "INV-2024-009", "customer_id": "9",
     "customer_name": "Adani Infrastructure Ltd.", "action_type": "Field Visit",
     "channel": "in_person", "outcome": "escalated", "date": "2024-03-15",
     "collector_name": "Field Team",
     "notes": "Office visited. Security confirmed management is unavailable. Case escalated to lender.", "broken_ptp": False},

    # ── INV-2024-010 · Digital Dreams Media (₹12.5L, 15 DPD) ─────────────────

    {"interaction_id": "INT-010-01", "invoice_id": "INV-2024-010", "customer_id": "10",
     "customer_name": "Digital Dreams Media", "action_type": "Email",
     "channel": "email", "outcome": "ptp_given", "date": "2024-04-01",
     "collector_name": "Anjali Patel", "ptp_amount": 625_000.0, "ptp_date": "2024-04-12",
     "notes": "Responsive. Said payment processing will complete within 10 days.", "broken_ptp": False},

    # ── INV-2024-011 · National Foods Corp (₹22.5L, 38 DPD) ──────────────────

    {"interaction_id": "INT-011-01", "invoice_id": "INV-2024-011", "customer_id": "11",
     "customer_name": "National Foods Corp.", "action_type": "Email",
     "channel": "email", "outcome": "no_response", "date": "2024-03-10",
     "collector_name": "Priya Sharma", "notes": "Reminder sent. No reply.", "broken_ptp": False},

    {"interaction_id": "INT-011-02", "invoice_id": "INV-2024-011", "customer_id": "11",
     "customer_name": "National Foods Corp.", "action_type": "Call",
     "channel": "phone", "outcome": "collected_partial", "date": "2024-03-18",
     "collector_name": "Priya Sharma", "amount_recovered": 562_500.0,
     "notes": "25% payment received. Rest to follow next week.", "broken_ptp": False},

    {"interaction_id": "INT-011-03", "invoice_id": "INV-2024-011", "customer_id": "11",
     "customer_name": "National Foods Corp.", "action_type": "Call",
     "channel": "phone", "outcome": "ptp_given", "date": "2024-03-28",
     "collector_name": "Priya Sharma", "ptp_amount": 1_125_000.0, "ptp_date": "2024-04-08",
     "notes": "Balance PTP confirmed.", "broken_ptp": False},

    # ── INV-2024-012 · QuickServe Restaurants (₹9.75L, 10 DPD) ──────────────

    {"interaction_id": "INT-012-01", "invoice_id": "INV-2024-012", "customer_id": "12",
     "customer_name": "QuickServe Restaurants Pvt Ltd.", "action_type": "WhatsApp",
     "channel": "whatsapp", "outcome": "ptp_given", "date": "2024-04-07",
     "collector_name": "Anjali Patel", "ptp_amount": 487_500.0, "ptp_date": "2024-04-14",
     "notes": "Owner responded on WhatsApp. 50% PTP confirmed.", "broken_ptp": False},

    # ── INV-2024-013 · HDFC Leasing (₹32.5L, 25 DPD) ─────────────────────────

    {"interaction_id": "INT-013-01", "invoice_id": "INV-2024-013", "customer_id": "13",
     "customer_name": "HDFC Leasing Co.", "action_type": "Email",
     "channel": "email", "outcome": "no_response", "date": "2024-03-25",
     "collector_name": "Rohit Mehta", "notes": "Reminder not acknowledged. Delayed email responses.", "broken_ptp": False},

    {"interaction_id": "INT-013-02", "invoice_id": "INV-2024-013", "customer_id": "13",
     "customer_name": "HDFC Leasing Co.", "action_type": "Call",
     "channel": "phone", "outcome": "ptp_given", "date": "2024-04-02",
     "collector_name": "Rohit Mehta", "ptp_amount": 1_625_000.0, "ptp_date": "2024-04-18",
     "notes": "New CFO's team confirmed payment in new cycle. PTP ₹16.25L.", "broken_ptp": False},

    # ── INV-2024-014 · Jain Agro Products (₹15.75L, 42 DPD) ─────────────────

    {"interaction_id": "INT-014-01", "invoice_id": "INV-2024-014", "customer_id": "14",
     "customer_name": "Jain Agro Products", "action_type": "Call",
     "channel": "phone", "outcome": "no_answer", "date": "2024-03-05",
     "collector_name": "Priya Sharma", "notes": "No answer on 2 calls.", "broken_ptp": False},

    {"interaction_id": "INT-014-02", "invoice_id": "INV-2024-014", "customer_id": "14",
     "customer_name": "Jain Agro Products", "action_type": "Call",
     "channel": "phone", "outcome": "ptp_given", "date": "2024-03-12",
     "collector_name": "Priya Sharma", "ptp_amount": 787_500.0, "ptp_date": "2024-03-25",
     "notes": "Connected with owner. Crop season delay. PTP ₹7.875L.", "broken_ptp": False},

    {"interaction_id": "INT-014-03", "invoice_id": "INV-2024-014", "customer_id": "14",
     "customer_name": "Jain Agro Products", "action_type": "Call",
     "channel": "phone", "outcome": "broken_ptp", "date": "2024-03-27",
     "collector_name": "Priya Sharma", "notes": "PTP missed. Kharif season delay cited.", "broken_ptp": True},

    # ── INV-2024-015 · Reliance Textiles (₹42.5L, 70 DPD, critical) ──────────

    {"interaction_id": "INT-015-01", "invoice_id": "INV-2024-015", "customer_id": "15",
     "customer_name": "Reliance Textiles Ltd.", "action_type": "Email",
     "channel": "email", "outcome": "no_response", "date": "2024-02-10",
     "collector_name": "Rohit Mehta", "notes": "Three reminders sent. No response.", "broken_ptp": False},

    {"interaction_id": "INT-015-02", "invoice_id": "INV-2024-015", "customer_id": "15",
     "customer_name": "Reliance Textiles Ltd.", "action_type": "Call",
     "channel": "phone", "outcome": "refused", "date": "2024-02-20",
     "collector_name": "Rohit Mehta", "notes": "Accounts head claims GST audit freeze on payments.", "broken_ptp": False},

    {"interaction_id": "INT-015-03", "invoice_id": "INV-2024-015", "customer_id": "15",
     "customer_name": "Reliance Textiles Ltd.", "action_type": "Legal Notice",
     "channel": "legal", "outcome": "collected_partial", "date": "2024-03-05",
     "collector_name": "Legal Team", "amount_recovered": 2_125_000.0,
     "notes": "Legal notice triggered ₹21.25L. Balance disputed. Case ongoing.", "broken_ptp": False},

    {"interaction_id": "INT-015-04", "invoice_id": "INV-2024-015", "customer_id": "15",
     "customer_name": "Reliance Textiles Ltd.", "action_type": "Payment Plan",
     "channel": "phone", "outcome": "ptp_given", "date": "2024-03-20",
     "collector_name": "Rohit Mehta", "ptp_amount": 2_125_000.0, "ptp_date": "2024-04-10",
     "notes": "Structured plan agreed: ₹21.25L in 3 instalments.", "broken_ptp": False},
]
