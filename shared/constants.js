/**
 * Cross-service constants shared between frontend and backend documentation.
 * Import these in any JS/JSX file that needs domain constants.
 */

export const RISK_LEVELS = /** @type {const} */ (["High", "Medium", "Low"]);

export const PRIORITY_LEVELS = /** @type {const} */ (["Critical", "High", "Medium", "Low"]);

export const INVOICE_STATUSES = /** @type {const} */ (["open", "overdue", "paid", "disputed"]);

export const COLLECTION_ACTIONS = [
  "Send Payment Reminder Email",
  "Make Collection Call",
  "Send Formal Demand Letter",
  "Offer Early Payment Discount",
  "Escalate to Collections Agency",
  "Initiate Legal Action Review",
  "Put Account on Credit Hold",
  "Schedule Payment Plan Discussion",
  "Send Final Notice",
  "No Action Required",
];

export const INDUSTRY_OPTIONS = [
  "Manufacturing",
  "Logistics",
  "Retail",
  "Technology",
  "Energy",
  "Healthcare",
  "Finance",
  "Other",
];

/** Priority score thresholds for colour-coding. */
export const PRIORITY_THRESHOLDS = {
  CRITICAL: 50_000,
  HIGH: 20_000,
  MEDIUM: 5_000,
};

/** DSO benchmark in days. */
export const DSO_BENCHMARK = 45;
