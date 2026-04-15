/**
 * AI Collector API Client
 *
 * Thin wrapper around fetch that reads VITE_API_BASE_URL from the environment
 * and provides typed helpers for every backend endpoint.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`API ${res.status}: ${errorBody}`);
  }

  return res.json();
}

// ─── Health ──────────────────────────────────────────────────────────────────

export const api = {
  health: () => request("/health"),

  // ─── Invoices ──────────────────────────────────────────────────────────────

  getInvoiceSummary: () => request("/invoices/summary"),

  listInvoices: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/invoices/?${qs}`);
  },

  getInvoice: (invoiceId) => request(`/invoices/${invoiceId}`),

  // ─── Predictions ───────────────────────────────────────────────────────────

  predictPayment: (payload) =>
    request("/predict/payment", { method: "POST", body: JSON.stringify(payload) }),

  predictRisk: (payload) =>
    request("/predict/risk", { method: "POST", body: JSON.stringify(payload) }),

  predictDSO: () => request("/predict/dso"),

  explainPrediction: (invoiceId, features) =>
    request("/predict/explain", {
      method: "POST",
      body: JSON.stringify({ invoice_id: invoiceId, features }),
    }),

  // ─── Forecasting ───────────────────────────────────────────────────────────

  getCashflowForecast: () => request("/forecast/cashflow"),

  // ─── Prioritization ────────────────────────────────────────────────────────

  getPrioritizedWorklist: () => request("/prioritize/invoices"),

  // ─── AI Recommendation ─────────────────────────────────────────────────────

  getRecommendation: (payload) =>
    request("/recommend/action", { method: "POST", body: JSON.stringify(payload) }),

  // ─── What-If Simulation ────────────────────────────────────────────────────

  simulateWhatIf: (payload) =>
    request("/whatif/simulate", { method: "POST", body: JSON.stringify(payload) }),

  // ─── Payment Behavior Analysis ─────────────────────────────────────────────

  analyzePaymentBehavior: (payload) =>
    request("/analyze/payment-behavior", { method: "POST", body: JSON.stringify(payload) }),

  getCustomerBehavior: (customerId) =>
    request(`/analyze/payment-behavior/${customerId}`),

  // ─── Enhanced Delay Prediction ─────────────────────────────────────────────

  predictDelay: (payload) =>
    request("/predict/delay", { method: "POST", body: JSON.stringify(payload) }),

  // ─── Collection Strategy Optimization ─────────────────────────────────────

  optimizeStrategy: (payload) =>
    request("/optimize/collection-strategy", { method: "POST", body: JSON.stringify(payload) }),

  getPortfolioStrategy: () =>
    request("/optimize/portfolio-strategy"),

  // ─── Orchestrated Agent ────────────────────────────────────────────────────

  analyzeCase: (payload) =>
    request("/agent/analyze-case", { method: "POST", body: JSON.stringify(payload) }),
};
