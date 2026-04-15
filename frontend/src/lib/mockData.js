/**
 * Client-side mock data for development without a running backend.
 * Mirrors the shape of actual API responses exactly.
 */

export const mockSummary = {
  total_invoices: 8,
  total_outstanding: 484650,
  overdue_count: 6,
  risk_breakdown: { High: 3, Medium: 3, Low: 2 },
};

export const mockDSO = {
  predicted_dso: 52.3,
  current_dso: 48.5,
  dso_trend: "worsening",
  benchmark_dso: 45.0,
};

export const mockCashflow = {
  next_7_days_inflow: 48200,
  next_30_days_inflow: 187400,
  confidence: 0.82,
  daily_breakdown: Array.from({ length: 30 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() + i);
    const base = 4000 + Math.random() * 8000;
    return {
      date: d.toISOString().split("T")[0],
      predicted_inflow: Math.round(base),
      lower_bound: Math.round(base * 0.75),
      upper_bound: Math.round(base * 1.25),
    };
  }),
};

export const mockWorklist = [
  {
    invoice_id: "INV-2024-004",
    customer_name: "TechNova Solutions",
    amount: 125000,
    days_overdue: 80,
    risk_label: "High",
    delay_probability: 0.82,
    priority_score: 102500,
    recommended_action: "Escalate to Collections Agency",
  },
  {
    invoice_id: "INV-2024-001",
    customer_name: "Apex Manufacturing Inc.",
    amount: 85000,
    days_overdue: 45,
    risk_label: "High",
    delay_probability: 0.68,
    priority_score: 57800,
    recommended_action: "Send Formal Demand Letter",
  },
  {
    invoice_id: "INV-2024-007",
    customer_name: "Pacific Steel Works",
    amount: 52800,
    days_overdue: 60,
    risk_label: "High",
    delay_probability: 0.74,
    priority_score: 39072,
    recommended_action: "Make Collection Call",
  },
  {
    invoice_id: "INV-2024-002",
    customer_name: "BlueSky Logistics Ltd.",
    amount: 42500,
    days_overdue: 20,
    risk_label: "Medium",
    delay_probability: 0.29,
    priority_score: 12325,
    recommended_action: "Make Collection Call",
  },
  {
    invoice_id: "INV-2024-005",
    customer_name: "Solaris Energy Partners",
    amount: 67200,
    days_overdue: 0,
    risk_label: "Medium",
    delay_probability: 0.12,
    priority_score: 8064,
    recommended_action: "Send Payment Reminder Email",
  },
  {
    invoice_id: "INV-2024-006",
    customer_name: "NorthStar Healthcare",
    amount: 31400,
    days_overdue: 30,
    risk_label: "Medium",
    delay_probability: 0.39,
    priority_score: 12246,
    recommended_action: "Schedule Payment Plan Discussion",
  },
  {
    invoice_id: "INV-2024-003",
    customer_name: "GreenField Retail Corp.",
    amount: 18750,
    days_overdue: 5,
    risk_label: "Low",
    delay_probability: 0.06,
    priority_score: 1125,
    recommended_action: "Send Payment Reminder Email",
  },
  {
    invoice_id: "INV-2024-008",
    customer_name: "Clearwater Financial",
    amount: 9800,
    days_overdue: 0,
    risk_label: "Low",
    delay_probability: 0.03,
    priority_score: 294,
    recommended_action: "No Action Required",
  },
];

export const mockInvoiceDetail = {
  "INV-2024-001": {
    invoice_id: "INV-2024-001",
    invoice_number: "INV-2024-001",
    customer_name: "Apex Manufacturing Inc.",
    industry: "Manufacturing",
    amount: 85000,
    currency: "USD",
    issue_date: "2024-02-01",
    due_date: "2024-03-01",
    status: "overdue",
    days_overdue: 45,
    risk_label: "High",
    credit_score: 580,
    avg_days_to_pay: 52,
    num_late_payments: 5,
    pay_7_days: 0.08,
    pay_15_days: 0.18,
    pay_30_days: 0.32,
    recommended_action: "Send Formal Demand Letter",
    shap_explanation: {
      top_features: [
        { feature_name: "days_overdue", feature_value: 45, shap_value: 0.32, impact: "negative" },
        { feature_name: "customer_credit_score", feature_value: 580, shap_value: -0.18, impact: "positive" },
        { feature_name: "num_late_payments", feature_value: 5, shap_value: 0.22, impact: "negative" },
        { feature_name: "invoice_amount", feature_value: 85000, shap_value: 0.08, impact: "negative" },
        { feature_name: "avg_days_to_pay", feature_value: 52, shap_value: 0.06, impact: "negative" },
      ],
      base_value: 0.45,
      prediction_value: 0.72,
    },
    ai_recommendation: {
      recommended_action: "Send Formal Demand Letter",
      priority: "Critical",
      timeline: "Within 24 Hours",
      reasoning:
        "High-value invoice ($85K) is 45 days overdue with only 32% probability of payment in 30 days. Customer has 5 historical late payments and a low credit score of 580.",
      additional_notes: "Consider escalating to legal review if no response within 72 hours.",
    },
  },
};

export const mockWhatIfBaseline = {
  predicted_recovery_pct: 68.0,
  cashflow_shift: 0,
  dso_shift: 0,
  baseline_recovery_pct: 68.0,
  baseline_cashflow: 320000,
  baseline_dso: 48.5,
  scenario_summary: "Baseline scenario — no changes applied.",
};
