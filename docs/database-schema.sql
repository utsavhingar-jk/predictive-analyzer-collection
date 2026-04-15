-- =============================================================================
-- AI COLLECTOR — Full Database Schema
-- PostgreSQL 14+
--
-- Tables:
--   1. customers              — borrower master record
--   2. customer_behavior      — payment personality profile (AI Pillar 1)
--   3. invoices               — receivable invoices
--   4. invoice_predictions    — ML prediction outputs per invoice (Pillar 2)
--   5. collection_strategies  — optimized collection strategy per invoice (Pillar 3)
--   6. cashflow_snapshots     — daily cashflow forecast snapshots (Pillar 4)
--   7. agent_case_results     — full agent pipeline output per invoice (Pillar 5)
--   8. payment_transactions   — raw transaction-level payment history
--
-- To connect:
--   Set DATABASE_URL in backend/.env (see bottom of this file)
-- =============================================================================

-- ─── Extensions ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- 1. CUSTOMERS
-- Master record for every borrower/debtor.
-- =============================================================================

CREATE TABLE IF NOT EXISTS customers (
    id                      BIGSERIAL PRIMARY KEY,
    external_id             VARCHAR(100) UNIQUE,          -- your ERP/TMS customer ID
    name                    VARCHAR(255)    NOT NULL,
    industry                VARCHAR(100),
    borrower_type           VARCHAR(50)     DEFAULT 'corporate', -- corporate | sme | individual
    credit_score            SMALLINT        CHECK (credit_score BETWEEN 300 AND 850),
    payment_terms           SMALLINT        DEFAULT 30,   -- standard payment terms (days)
    avg_days_to_pay         NUMERIC(6,2)    DEFAULT 0,    -- rolling average
    total_invoiced          NUMERIC(14,2)   DEFAULT 0,
    total_overdue           NUMERIC(14,2)   DEFAULT 0,
    num_invoices            INTEGER         DEFAULT 0,
    num_late_payments       INTEGER         DEFAULT 0,
    num_disputes            INTEGER         DEFAULT 0,
    nach_mandate_active     BOOLEAN         DEFAULT FALSE,
    anchor_linked           BOOLEAN         DEFAULT FALSE,  -- supply-chain finance anchor
    created_at              TIMESTAMPTZ     DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customers_external_id ON customers(external_id);
CREATE INDEX IF NOT EXISTS idx_customers_industry    ON customers(industry);

COMMENT ON TABLE customers IS 'Master borrower/debtor records';
COMMENT ON COLUMN customers.external_id IS 'ID from your ERP, TMS or banking system';
COMMENT ON COLUMN customers.nach_mandate_active IS 'True if NACH/auto-debit mandate is registered';


-- =============================================================================
-- 2. CUSTOMER_BEHAVIOR
-- AI Pillar 1: Payment personality profile.
-- One row per customer, updated whenever the behavior engine runs.
-- =============================================================================

CREATE TABLE IF NOT EXISTS customer_behavior (
    id                              BIGSERIAL PRIMARY KEY,
    customer_id                     BIGINT REFERENCES customers(id) ON DELETE CASCADE,

    -- Computed behavior signals
    historical_on_time_ratio        NUMERIC(5,4)   NOT NULL DEFAULT 0.70,  -- 0.00–1.00
    avg_delay_days                  NUMERIC(6,2)   NOT NULL DEFAULT 0,
    repayment_consistency           NUMERIC(5,4)   DEFAULT 0.60,           -- variance-based score
    partial_payment_frequency       NUMERIC(5,4)   DEFAULT 0,              -- % invoices paid partially
    prior_delayed_invoice_count     INTEGER        DEFAULT 0,
    payment_after_followup_count    INTEGER        DEFAULT 0,
    deterioration_trend             NUMERIC(5,4)   DEFAULT 0,              -- -1 to +1
    invoice_acknowledgement_behavior VARCHAR(30)   DEFAULT 'normal',       -- normal|delayed|ignored|disputed
    transaction_success_failure_pattern NUMERIC(5,4) DEFAULT 0,

    -- AI output
    behavior_type                   VARCHAR(60)    NOT NULL,
    -- Consistent Payer | Occasional Late Payer | Reminder Driven Payer |
    -- Partial Payment Payer | Chronic Delayed Payer | High Risk Defaulter
    payment_style                   VARCHAR(80),
    behavior_risk_score             NUMERIC(5,1)   CHECK (behavior_risk_score BETWEEN 0 AND 100),
    trend                           VARCHAR(20)    DEFAULT 'Stable',       -- Improving|Stable|Worsening
    followup_dependency             BOOLEAN        DEFAULT FALSE,
    nach_recommended                BOOLEAN        DEFAULT FALSE,
    behavior_summary                TEXT,

    model_version                   VARCHAR(50)    DEFAULT 'rule-engine-v1',
    computed_at                     TIMESTAMPTZ    DEFAULT NOW(),

    UNIQUE (customer_id)  -- one active profile per customer
);

CREATE INDEX IF NOT EXISTS idx_behavior_customer     ON customer_behavior(customer_id);
CREATE INDEX IF NOT EXISTS idx_behavior_type         ON customer_behavior(behavior_type);
CREATE INDEX IF NOT EXISTS idx_behavior_risk_score   ON customer_behavior(behavior_risk_score DESC);

COMMENT ON TABLE customer_behavior IS 'AI Pillar 1 — Payment personality profile per customer';


-- =============================================================================
-- 3. INVOICES
-- Core receivable invoice ledger.
-- =============================================================================

CREATE TABLE IF NOT EXISTS invoices (
    id                      BIGSERIAL PRIMARY KEY,
    invoice_number          VARCHAR(50)     UNIQUE NOT NULL,  -- e.g. INV-2024-001
    customer_id             BIGINT          REFERENCES customers(id) NOT NULL,

    -- Financial
    amount                  NUMERIC(14,2)   NOT NULL CHECK (amount > 0),
    currency                CHAR(3)         DEFAULT 'USD',
    outstanding_amount      NUMERIC(14,2),  -- remaining unpaid (for partial payments)

    -- Dates
    issue_date              DATE            NOT NULL,
    due_date                DATE            NOT NULL,
    paid_date               DATE,
    extended_due_date       DATE,           -- after renegotiation

    -- Status
    status                  VARCHAR(20)     DEFAULT 'open',
    -- open | overdue | paid | partial | disputed | written_off
    days_overdue            SMALLINT        DEFAULT 0,  -- recomputed daily
    dpd_bucket              VARCHAR(20),
    -- current | 1-30 | 31-60 | 61-90 | 90+

    -- Context flags
    nach_applicable         BOOLEAN         DEFAULT FALSE,
    is_anchor_invoice       BOOLEAN         DEFAULT FALSE,
    dispute_reason          VARCHAR(255),

    notes                   TEXT,
    created_at              TIMESTAMPTZ     DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoices_customer     ON invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status       ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_due_date     ON invoices(due_date);
CREATE INDEX IF NOT EXISTS idx_invoices_days_overdue ON invoices(days_overdue DESC);

COMMENT ON TABLE invoices IS 'Core receivable invoice ledger';
COMMENT ON COLUMN invoices.dpd_bucket IS 'Days-past-due aging bucket — recomputed nightly';


-- =============================================================================
-- 4. INVOICE_PREDICTIONS
-- AI Pillar 2: ML prediction outputs per invoice.
-- New row on every prediction run; latest row = current prediction.
-- =============================================================================

CREATE TABLE IF NOT EXISTS invoice_predictions (
    id                      BIGSERIAL PRIMARY KEY,
    invoice_id              BIGINT REFERENCES invoices(id) ON DELETE CASCADE,

    -- Payment probability
    pay_7_days              NUMERIC(5,4)   CHECK (pay_7_days  BETWEEN 0 AND 1),
    pay_15_days             NUMERIC(5,4)   CHECK (pay_15_days BETWEEN 0 AND 1),
    pay_30_days             NUMERIC(5,4)   CHECK (pay_30_days BETWEEN 0 AND 1),

    -- Delay prediction (enriched with behavior)
    delay_probability       NUMERIC(5,4)   CHECK (delay_probability BETWEEN 0 AND 1),
    risk_score              SMALLINT       CHECK (risk_score BETWEEN 0 AND 100),
    risk_tier               VARCHAR(10),   -- High | Medium | Low
    risk_label              VARCHAR(10),   -- alias of risk_tier for legacy compat

    -- SHAP top drivers (stored as JSONB array)
    top_drivers             JSONB,
    -- Example: ["45 days overdue", "5 prior delays", "Credit score 580"]
    shap_values             JSONB,
    -- Example: [{"feature":"days_overdue","value":45,"shap":0.32,"impact":"negative"}]

    model_version           VARCHAR(50),
    predicted_at            TIMESTAMPTZ    DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_invoice   ON invoice_predictions(invoice_id);
CREATE INDEX IF NOT EXISTS idx_predictions_date      ON invoice_predictions(predicted_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_risk_tier ON invoice_predictions(risk_tier);

COMMENT ON TABLE invoice_predictions IS 'AI Pillar 2 — ML prediction outputs per invoice run';
COMMENT ON COLUMN invoice_predictions.shap_values IS 'JSONB array of SHAP feature attribution objects';


-- =============================================================================
-- 5. COLLECTION_STRATEGIES
-- AI Pillar 3: Optimized collection strategy per invoice.
-- New row on every strategy run; latest row = active strategy.
-- =============================================================================

CREATE TABLE IF NOT EXISTS collection_strategies (
    id                      BIGSERIAL PRIMARY KEY,
    invoice_id              BIGINT REFERENCES invoices(id) ON DELETE CASCADE,

    priority_score          SMALLINT       CHECK (priority_score BETWEEN 0 AND 100),
    priority_rank           INTEGER,       -- rank within current portfolio run
    urgency                 VARCHAR(20),   -- Critical | High | Medium | Low
    recommended_action      VARCHAR(120),
    channel                 VARCHAR(50),   -- Call | Email | Legal | NACH | Field Visit | Anchor Escalation
    reason                  TEXT,
    automation_flag         BOOLEAN        DEFAULT FALSE,
    next_action_in_hours    SMALLINT,

    -- Outcome tracking (filled after action taken)
    action_taken            VARCHAR(120),
    action_taken_at         TIMESTAMPTZ,
    outcome                 VARCHAR(50),   -- paid | promised | escalated | no_response | disputed
    outcome_recorded_at     TIMESTAMPTZ,

    computed_at             TIMESTAMPTZ    DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategies_invoice    ON collection_strategies(invoice_id);
CREATE INDEX IF NOT EXISTS idx_strategies_priority   ON collection_strategies(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_strategies_urgency    ON collection_strategies(urgency);

COMMENT ON TABLE collection_strategies IS 'AI Pillar 3 — Optimized collection action per invoice';


-- =============================================================================
-- 6. CASHFLOW_SNAPSHOTS
-- AI Pillar 4: Daily cashflow forecast runs.
-- =============================================================================

CREATE TABLE IF NOT EXISTS cashflow_snapshots (
    id                              BIGSERIAL PRIMARY KEY,
    snapshot_date                   DATE           NOT NULL,  -- date forecast was generated

    -- Summary signals
    expected_7_day_collections      NUMERIC(14,2),
    expected_30_day_collections     NUMERIC(14,2),
    amount_at_risk                  NUMERIC(14,2),  -- outstanding with delay_prob > 0.60
    shortfall_signal                BOOLEAN        DEFAULT FALSE,
    borrower_concentration_risk     VARCHAR(10),    -- Low | Medium | High
    overdue_carry_forward           NUMERIC(14,2),  -- uncollected overdue expected in 30d
    confidence                      NUMERIC(4,3),

    -- Daily breakdown stored as JSONB
    daily_breakdown                 JSONB,
    -- Example: [{"date":"2024-04-16","predicted_inflow":12500,"lower_bound":9375,"upper_bound":15625}]

    created_at                      TIMESTAMPTZ    DEFAULT NOW(),

    UNIQUE (snapshot_date)  -- one snapshot per calendar day
);

CREATE INDEX IF NOT EXISTS idx_cashflow_date ON cashflow_snapshots(snapshot_date DESC);

COMMENT ON TABLE cashflow_snapshots IS 'AI Pillar 4 — Daily cashflow forecast snapshots';


-- =============================================================================
-- 7. AGENT_CASE_RESULTS
-- AI Pillar 5: Full orchestrated agent pipeline output per invoice.
-- =============================================================================

CREATE TABLE IF NOT EXISTS agent_case_results (
    id                      BIGSERIAL PRIMARY KEY,
    invoice_id              BIGINT REFERENCES invoices(id) ON DELETE CASCADE,

    -- Linked pillar outputs (FK to latest rows)
    behavior_snapshot       JSONB,   -- snapshot of customer_behavior at time of run
    delay_snapshot          JSONB,   -- snapshot of invoice_predictions at time of run
    strategy_snapshot       JSONB,   -- snapshot of collection_strategies at time of run

    -- GPT-4o output
    business_summary        TEXT,
    recommended_action      VARCHAR(120),
    model_used              VARCHAR(50)    DEFAULT 'gpt-4o',

    ran_at                  TIMESTAMPTZ    DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_invoice ON agent_case_results(invoice_id);
CREATE INDEX IF NOT EXISTS idx_agent_ran_at  ON agent_case_results(ran_at DESC);

COMMENT ON TABLE agent_case_results IS 'AI Pillar 5 — Full orchestrated agent pipeline results';


-- =============================================================================
-- 8. PAYMENT_TRANSACTIONS
-- Raw payment-level history. Source of truth for computing behavior signals.
-- =============================================================================

CREATE TABLE IF NOT EXISTS payment_transactions (
    id                      BIGSERIAL PRIMARY KEY,
    invoice_id              BIGINT REFERENCES invoices(id) ON DELETE CASCADE,
    customer_id             BIGINT REFERENCES customers(id),

    amount_paid             NUMERIC(14,2)   NOT NULL,
    payment_date            DATE            NOT NULL,
    expected_date           DATE,           -- original due date at time of payment
    delay_days              SMALLINT        DEFAULT 0,  -- payment_date - expected_date
    is_partial              BOOLEAN         DEFAULT FALSE,
    is_after_followup       BOOLEAN         DEFAULT FALSE,  -- TRUE if payment came after reminder
    transaction_ref         VARCHAR(100),
    payment_mode            VARCHAR(50),    -- NEFT | RTGS | NACH | Cheque | UPI | Wire
    transaction_status      VARCHAR(20)     DEFAULT 'success',  -- success | failed | bounced | reversed
    failure_reason          VARCHAR(255),

    created_at              TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_invoice    ON payment_transactions(invoice_id);
CREATE INDEX IF NOT EXISTS idx_transactions_customer   ON payment_transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date       ON payment_transactions(payment_date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_status     ON payment_transactions(transaction_status);

COMMENT ON TABLE payment_transactions IS 'Raw payment history — source for behavior signal computation';


-- =============================================================================
-- VIEWS — pre-joined for fast API reads
-- =============================================================================

-- Collector worklist view: joins latest prediction + strategy per invoice
CREATE OR REPLACE VIEW v_collector_worklist AS
SELECT
    i.invoice_number                                    AS invoice_id,
    i.id                                                AS invoice_pk,
    c.name                                              AS customer_name,
    c.id                                                AS customer_pk,
    c.industry,
    i.amount,
    i.currency,
    i.due_date,
    i.days_overdue,
    i.status,
    cb.behavior_type,
    cb.behavior_risk_score,
    cb.trend                                            AS behavior_trend,
    cb.nach_recommended,
    cb.followup_dependency,
    ip.delay_probability,
    ip.risk_score,
    ip.risk_tier,
    ip.pay_7_days,
    ip.pay_15_days,
    ip.pay_30_days,
    ip.top_drivers,
    cs.priority_score,
    cs.priority_rank,
    cs.urgency,
    cs.recommended_action,
    cs.channel,
    cs.next_action_in_hours,
    cs.automation_flag
FROM invoices i
JOIN customers c ON c.id = i.customer_id
LEFT JOIN customer_behavior cb ON cb.customer_id = c.id
-- Latest prediction only
LEFT JOIN LATERAL (
    SELECT * FROM invoice_predictions
    WHERE invoice_id = i.id
    ORDER BY predicted_at DESC LIMIT 1
) ip ON TRUE
-- Latest strategy only
LEFT JOIN LATERAL (
    SELECT * FROM collection_strategies
    WHERE invoice_id = i.id
    ORDER BY computed_at DESC LIMIT 1
) cs ON TRUE
WHERE i.status IN ('open', 'overdue')
ORDER BY cs.priority_score DESC NULLS LAST;

COMMENT ON VIEW v_collector_worklist IS 'Prioritized collector worklist — latest prediction + strategy per open invoice';


-- Portfolio summary view
CREATE OR REPLACE VIEW v_portfolio_summary AS
SELECT
    COUNT(*)                                            AS total_invoices,
    SUM(i.amount)                                       AS total_outstanding,
    SUM(CASE WHEN i.status = 'overdue' THEN i.amount ELSE 0 END)
                                                        AS overdue_amount,
    COUNT(CASE WHEN i.status = 'overdue' THEN 1 END)   AS overdue_count,
    SUM(CASE WHEN ip.delay_probability > 0.60 THEN i.amount ELSE 0 END)
                                                        AS amount_at_risk,
    COUNT(CASE WHEN ip.risk_tier = 'High' THEN 1 END)  AS high_risk_count,
    COUNT(CASE WHEN ip.risk_tier = 'Medium' THEN 1 END) AS medium_risk_count,
    COUNT(CASE WHEN ip.risk_tier = 'Low' THEN 1 END)   AS low_risk_count
FROM invoices i
LEFT JOIN LATERAL (
    SELECT delay_probability, risk_tier
    FROM invoice_predictions
    WHERE invoice_id = i.id
    ORDER BY predicted_at DESC LIMIT 1
) ip ON TRUE
WHERE i.status IN ('open', 'overdue');

COMMENT ON VIEW v_portfolio_summary IS 'Portfolio-level AR health summary for Executive Dashboard';


-- =============================================================================
-- SEED DATA — mirrors the application mock data (8 customers + invoices)
-- Run this after CREATE TABLE statements to populate your dev/test DB.
-- =============================================================================

-- Customers
INSERT INTO customers (id, external_id, name, industry, credit_score, payment_terms, avg_days_to_pay, total_overdue, num_late_payments)
VALUES
    (1, 'CUST-001', 'Apex Manufacturing Inc.',  'Manufacturing', 580, 30, 52.0, 145000, 5),
    (2, 'CUST-002', 'BlueSky Logistics Ltd.',   'Logistics',     680, 30, 38.0, 42500,  2),
    (3, 'CUST-003', 'GreenField Retail Corp.',  'Retail',        760, 30, 29.0, 18750,  0),
    (4, 'CUST-004', 'TechNova Solutions',        'Technology',    540, 30, 72.0, 210000, 8),
    (5, 'CUST-005', 'Solaris Energy Partners',   'Energy',        710, 60, 33.0, 0,      1),
    (6, 'CUST-006', 'NorthStar Healthcare',      'Healthcare',    645, 30, 44.0, 31400,  3),
    (7, 'CUST-007', 'Pacific Steel Works',       'Manufacturing', 600, 30, 58.0, 52800,  6),
    (8, 'CUST-008', 'Clearwater Financial',      'Finance',       800, 30, 22.0, 0,      0)
ON CONFLICT (id) DO NOTHING;

SELECT setval('customers_id_seq', 8);

-- Customer behavior profiles
INSERT INTO customer_behavior (
    customer_id, historical_on_time_ratio, avg_delay_days, repayment_consistency,
    partial_payment_frequency, prior_delayed_invoice_count, payment_after_followup_count,
    deterioration_trend, invoice_acknowledgement_behavior, transaction_success_failure_pattern,
    behavior_type, payment_style, behavior_risk_score, trend, followup_dependency, nach_recommended, behavior_summary
)
VALUES
    (1, 0.31, 22.0, 0.40, 0.20, 5, 4, 0.30, 'delayed',  0.05, 'Chronic Delayed Payer',  'Chronic Late + High DPD',       82.0, 'Worsening', TRUE,  TRUE,  'Chronic delayed payer; on-time ratio 31%, avg delay 22d, worsening trend.'),
    (2, 0.68, 12.0, 0.65, 0.10, 2, 1, 0.05, 'normal',   0.02, 'Occasional Late Payer',  'Mostly On-Time',                42.0, 'Stable',    FALSE, FALSE, 'Occasional late payer; on-time ratio 68%, avg delay 12d, stable trend.'),
    (3, 0.92, 3.0,  0.90, 0.02, 0, 0, -0.10,'normal',   0.01, 'Consistent Payer',       'Prompt + Autonomous',           8.0,  'Improving', FALSE, FALSE, 'Consistent payer; on-time ratio 92%, avg delay 3d, improving trend.'),
    (4, 0.18, 38.0, 0.20, 0.35, 8, 7, 0.45, 'ignored',  0.15, 'High Risk Defaulter',    'Erratic + Non-Responsive',      94.0, 'Worsening', TRUE,  TRUE,  'High risk defaulter; on-time ratio 18%, avg delay 38d, worsening trend.'),
    (5, 0.72, 8.0,  0.70, 0.05, 1, 0, 0.00, 'normal',   0.02, 'Occasional Late Payer',  'Mostly On-Time',                28.0, 'Stable',    FALSE, FALSE, 'Occasional late payer; on-time ratio 72%, avg delay 8d, stable trend.'),
    (6, 0.52, 18.0, 0.50, 0.15, 3, 4, 0.10, 'delayed',  0.03, 'Reminder Driven Payer',  'Requires Follow-Up',            58.0, 'Stable',    TRUE,  TRUE,  'Reminder driven payer; on-time ratio 52%, avg delay 18d, stable trend.'),
    (7, 0.28, 32.0, 0.35, 0.28, 6, 5, 0.35, 'delayed',  0.08, 'Chronic Delayed Payer',  'Partial + Reminder Driven',     79.0, 'Worsening', TRUE,  TRUE,  'Chronic delayed payer; on-time ratio 28%, avg delay 32d, worsening trend.'),
    (8, 0.96, 1.0,  0.95, 0.01, 0, 0, -0.15,'normal',   0.00, 'Consistent Payer',       'Prompt + Autonomous',           4.0,  'Improving', FALSE, FALSE, 'Consistent payer; on-time ratio 96%, avg delay 1d, improving trend.')
ON CONFLICT (customer_id) DO NOTHING;

-- Invoices (dates computed relative to NOW() for always-fresh data)
INSERT INTO invoices (
    invoice_number, customer_id, amount, currency,
    issue_date, due_date, status, days_overdue, nach_applicable
)
VALUES
    ('INV-2024-001', 1, 85000.00,  'USD', NOW()::DATE - 75, NOW()::DATE - 45, 'overdue', 45, TRUE),
    ('INV-2024-002', 2, 42500.00,  'USD', NOW()::DATE - 50, NOW()::DATE - 20, 'overdue', 20, FALSE),
    ('INV-2024-003', 3, 18750.00,  'USD', NOW()::DATE - 35, NOW()::DATE - 5,  'overdue', 5,  FALSE),
    ('INV-2024-004', 4, 125000.00, 'USD', NOW()::DATE - 110,NOW()::DATE - 80, 'overdue', 80, TRUE),
    ('INV-2024-005', 5, 67200.00,  'USD', NOW()::DATE - 45, NOW()::DATE + 15, 'open',    0,  FALSE),
    ('INV-2024-006', 6, 31400.00,  'USD', NOW()::DATE - 60, NOW()::DATE - 30, 'overdue', 30, TRUE),
    ('INV-2024-007', 7, 52800.00,  'USD', NOW()::DATE - 90, NOW()::DATE - 60, 'overdue', 60, TRUE),
    ('INV-2024-008', 8, 9800.00,   'USD', NOW()::DATE - 20, NOW()::DATE + 10, 'open',    0,  FALSE)
ON CONFLICT (invoice_number) DO NOTHING;

-- Invoice predictions (latest ML output)
INSERT INTO invoice_predictions (
    invoice_id, pay_7_days, pay_15_days, pay_30_days,
    delay_probability, risk_score, risk_tier, risk_label,
    top_drivers, model_version
)
SELECT
    i.id,
    p.pay_7,
    p.pay_15,
    p.pay_30,
    ROUND((1 - p.pay_30)::NUMERIC, 4),
    ROUND(((1 - p.pay_30) * 100)::NUMERIC)::SMALLINT,
    CASE WHEN (1 - p.pay_30) >= 0.65 THEN 'High'
         WHEN (1 - p.pay_30) >= 0.35 THEN 'Medium'
         ELSE 'Low' END,
    CASE WHEN (1 - p.pay_30) >= 0.65 THEN 'High'
         WHEN (1 - p.pay_30) >= 0.35 THEN 'Medium'
         ELSE 'Low' END,
    p.drivers::JSONB,
    'seed-v1'
FROM invoices i
JOIN (VALUES
    ('INV-2024-001', 0.08, 0.18, 0.32, '["45 days overdue","5 prior delays","Credit score 580"]'),
    ('INV-2024-002', 0.22, 0.45, 0.71, '["20 days overdue","2 prior delays"]'),
    ('INV-2024-003', 0.55, 0.80, 0.94, '["Good credit score 760","0 late payments"]'),
    ('INV-2024-004', 0.03, 0.07, 0.18, '["80 days overdue","8 prior delays","Credit score 540","High risk defaulter"]'),
    ('INV-2024-005', 0.15, 0.62, 0.88, '["Due in 15 days","1 prior delay"]'),
    ('INV-2024-006', 0.18, 0.38, 0.61, '["30 days overdue","Reminder driven payer","3 prior delays"]'),
    ('INV-2024-007', 0.05, 0.12, 0.26, '["60 days overdue","6 prior delays","Chronic delayed payer"]'),
    ('INV-2024-008', 0.30, 0.85, 0.97, '["Good credit score 800","0 late payments"]')
) AS p(inv_num, pay_7, pay_15, pay_30, drivers)
ON i.invoice_number = p.inv_num;

-- Collection strategies
INSERT INTO collection_strategies (
    invoice_id, priority_score, priority_rank, urgency,
    recommended_action, channel, automation_flag, next_action_in_hours,
    reason
)
SELECT
    i.id, s.score, s.rank, s.urgency, s.action, s.channel, s.auto, s.hours, s.reason
FROM invoices i
JOIN (VALUES
    ('INV-2024-001', 88, 2, 'Critical', 'Formal Demand Letter',       'Legal',              FALSE, 12,  'High delay risk + 45 DPD + chronic payer'),
    ('INV-2024-002', 42, 5, 'Medium',   'Collection Call',            'Call',               TRUE,  48,  'Moderate delay risk + 20 DPD'),
    ('INV-2024-003', 10, 7, 'Low',      'Automated Reminder',         'Email',              TRUE,  72,  'Low delay risk, consistent payer'),
    ('INV-2024-004', 97, 1, 'Critical', 'Escalate to Anchor',         'Anchor Escalation',  FALSE, 4,   'Highest priority: 82% delay + 80 DPD + high risk defaulter'),
    ('INV-2024-005', 28, 6, 'Medium',   'Automated Payment Reminder', 'Email',              TRUE,  24,  'Due soon, occasional late payer'),
    ('INV-2024-006', 55, 4, 'High',     'Follow-up Email + Call',     'Call',               FALSE, 48,  'Reminder-driven payer + 30 DPD'),
    ('INV-2024-007', 83, 3, 'Critical', 'Collection Call + Email',    'Call',               FALSE, 8,   'Chronic payer + 60 DPD + NACH recommended'),
    ('INV-2024-008', 5,  8, 'Low',      'No Action Required',         'Email',              TRUE,  72,  'Consistent payer, not yet due')
) AS s(inv_num, score, rank, urgency, action, channel, auto, hours, reason)
ON i.invoice_number = s.inv_num;


-- =============================================================================
-- USEFUL QUERIES FOR YOUR API LAYER
-- Replace mock_data.py functions with these when wiring up the DB.
-- =============================================================================

-- Get full worklist (replaces get_prioritized_worklist):
-- SELECT * FROM v_collector_worklist;

-- Get portfolio summary (replaces get_portfolio_summary):
-- SELECT * FROM v_portfolio_summary;

-- Get invoice detail by number:
-- SELECT i.*, c.name AS customer_name, c.industry, c.credit_score,
--        c.avg_days_to_pay, c.num_late_payments,
--        cb.behavior_type, cb.behavior_risk_score, cb.trend,
--        ip.delay_probability, ip.risk_tier, ip.top_drivers, ip.shap_values,
--        cs.priority_score, cs.recommended_action, cs.urgency
-- FROM invoices i
-- JOIN customers c ON c.id = i.customer_id
-- LEFT JOIN customer_behavior cb ON cb.customer_id = c.id
-- LEFT JOIN LATERAL (SELECT * FROM invoice_predictions WHERE invoice_id=i.id ORDER BY predicted_at DESC LIMIT 1) ip ON TRUE
-- LEFT JOIN LATERAL (SELECT * FROM collection_strategies WHERE invoice_id=i.id ORDER BY computed_at DESC LIMIT 1) cs ON TRUE
-- WHERE i.invoice_number = 'INV-2024-001';

-- Compute deterioration_trend for a customer (slide over last 6 vs prior invoices):
-- SELECT
--     customer_id,
--     AVG(delay_days) FILTER (WHERE payment_date >= NOW() - INTERVAL '90 days') AS recent_avg,
--     AVG(delay_days) FILTER (WHERE payment_date <  NOW() - INTERVAL '90 days') AS historical_avg,
--     CASE WHEN AVG(delay_days) FILTER (WHERE payment_date < NOW() - INTERVAL '90 days') > 0
--          THEN ROUND(
--             (AVG(delay_days) FILTER (WHERE payment_date >= NOW() - INTERVAL '90 days')
--              - AVG(delay_days) FILTER (WHERE payment_date < NOW() - INTERVAL '90 days'))
--             / AVG(delay_days) FILTER (WHERE payment_date < NOW() - INTERVAL '90 days'), 4
--          )
--          ELSE 0
--     END AS deterioration_trend
-- FROM payment_transactions
-- GROUP BY customer_id;
