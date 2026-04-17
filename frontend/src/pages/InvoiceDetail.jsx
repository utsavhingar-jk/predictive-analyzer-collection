import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Bot,
  Clock,
  DollarSign,
} from "lucide-react";
import { PageLayout } from "@/components/layout/PageLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { PaymentBehaviorCard } from "@/components/dashboard/PaymentBehaviorCard";
import { DelayPredictionCard } from "@/components/dashboard/DelayPredictionCard";
import { StrategyCard } from "@/components/dashboard/StrategyCard";
import { BorrowerRiskCard } from "@/components/dashboard/BorrowerRiskCard";
import { AgentReasoningTrace } from "@/components/agent/AgentReasoningTrace";
import { AgentThinkingLoader } from "@/components/agent/AgentThinkingLoader";
import { AgentAskBox } from "@/components/agent/AgentAskBox";
import { ShapBarChart } from "@/components/charts/ShapBarChart";
import { SentinelAlert } from "@/components/dashboard/SentinelAlert";
import { CandidateActionsCard } from "@/components/dashboard/CandidateActionsCard";
import { ConfidenceIndicator } from "@/components/dashboard/ConfidenceIndicator";
import { InteractionTimeline } from "@/components/dashboard/InteractionTimeline";
import { ActionEffectivenessCard } from "@/components/dashboard/ActionEffectivenessCard";
import { BorrowerEnrichmentCard } from "@/components/dashboard/BorrowerEnrichmentCard";
import { ExplainabilityPanel } from "@/components/dashboard/ExplainabilityPanel";
import { api } from "@/lib/api";
import { formatCurrency, formatPct, getPriorityColor } from "@/lib/utils";

function PaymentProbabilityBar({ label, value }) {
  const pct = Math.round((Number(value) || 0) * 100);
  const color = pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold text-foreground">{pct}%</span>
      </div>
      <div className="h-2 rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function DefaultProbabilityBar({ label, value }) {
  const pct = Math.round((Number(value) || 0) * 100);
  const color = pct >= 70 ? "bg-red-500" : pct >= 40 ? "bg-amber-500" : "bg-green-500";
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold text-foreground">{pct}%</span>
      </div>
      <div className="h-2 rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function InfoRow({ label, value, mono }) {
  return (
    <div className="flex justify-between py-2 border-b border-border last:border-0">
      <span className="text-muted-foreground text-sm">{label}</span>
      <span className={`text-sm font-medium text-foreground ${mono ? "font-mono" : ""}`}>
        {value}
      </span>
    </div>
  );
}

export function InvoiceDetail() {
  const { invoiceId } = useParams();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentResult, setAgentResult] = useState(null);
  const [borrowerPrediction, setBorrowerPrediction] = useState(null);
  const [interactions, setInteractions] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setInvoice(null);
    setAgentResult(null);
    setBorrowerPrediction(null);
    setInteractions(null);
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getInvoice(invoiceId);
        if (!cancelled) setInvoice(data);
      } catch (err) {
        if (!cancelled) {
          setInvoice(null);
          setError(err?.message || "Failed to load invoice detail");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [invoiceId]);

  // Load borrower-level prediction and interaction history when invoice loads
  useEffect(() => {
    if (!invoice) return;
    const customerId = String(invoice.customer_id || "1");
    api.getBorrowerPrediction(customerId)
      .then(setBorrowerPrediction)
      .catch(() => {});
    api.getInteractions(invoice.invoice_id)
      .then(setInteractions)
      .catch(() => {});
  }, [invoice]);

  async function runAgentAnalysis() {
    if (!invoice) return;
    setAgentLoading(true);
    try {
      const canonicalPaymentInput = invoice.model_inputs?.payment || {};
      const canonicalBehaviorInput = invoice.model_inputs?.behavior || {};
      const activeBehavior = invoice.payment_behavior;
      const historicalOnTimeRatio =
        canonicalBehaviorInput.historical_on_time_ratio ?? ((Number(activeBehavior?.on_time_ratio) || 70) / 100);
      const avgDelayDays =
        canonicalBehaviorInput.avg_delay_days ?? activeBehavior?.avg_delay_days ?? 10;
      const repaymentConsistency =
        canonicalBehaviorInput.repayment_consistency ?? 0.6;
      const partialPaymentFrequency =
        canonicalBehaviorInput.partial_payment_frequency ?? 0.1;
      const paymentAfterFollowupCount =
        canonicalBehaviorInput.payment_after_followup_count ?? invoice.num_late_payments ?? 0;
      const totalInvoices =
        canonicalBehaviorInput.total_invoices ?? invoice.num_previous_invoices ?? 10;
      const deteriorationTrend =
        canonicalBehaviorInput.deterioration_trend ?? 0;
      const transactionFailurePattern =
        canonicalBehaviorInput.transaction_success_failure_pattern ?? 0.05;
      const result = await api.analyzeCase({
        invoice_id: String(invoice.invoice_id),
        customer_id: String(invoice.customer_id ?? invoice.customer_name),
        customer_name: String(invoice.customer_name),
        invoice_amount: Number(invoice.amount) || 0,
        days_overdue: Math.round(Number(invoice.days_overdue) || 0),
        payment_terms: Math.round(Number(canonicalPaymentInput.payment_terms ?? invoice.payment_terms) || 30),
        customer_credit_score: Math.round(Number(canonicalPaymentInput.customer_credit_score ?? invoice.credit_score) || 650),
        customer_avg_days_to_pay: Number(canonicalPaymentInput.customer_avg_days_to_pay ?? invoice.avg_days_to_pay) || 30,
        num_late_payments: Math.round(Number(invoice.num_late_payments) || 0),
        customer_total_overdue: Number(canonicalPaymentInput.customer_total_overdue ?? invoice.customer_total_overdue) || 0,
        industry: canonicalPaymentInput.industry || invoice.industry || "unknown",
        historical_on_time_ratio: Number(historicalOnTimeRatio),
        avg_delay_days: Number(avgDelayDays),
        repayment_consistency: Number(repaymentConsistency),
        partial_payment_frequency: Number(partialPaymentFrequency),
        payment_after_followup_count: Math.round(Number(paymentAfterFollowupCount) || 0),
        total_invoices: Math.round(Number(totalInvoices) || 10),
        deterioration_trend: Number(deteriorationTrend),
        invoice_acknowledgement_behavior: canonicalBehaviorInput.invoice_acknowledgement_behavior || "normal",
        transaction_success_failure_pattern: Number(transactionFailurePattern),
      });
      setAgentResult(result);
    } catch {
      // Keep existing pre-computed result
    } finally {
      setAgentLoading(false);
    }
  }

  if (loading) {
    return (
      <PageLayout title="Invoice Detail" subtitle="Loading…">
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="animate-pulse rounded-xl bg-muted h-48" />
          ))}
        </div>
      </PageLayout>
    );
  }

  if (!invoice) {
    return (
      <PageLayout title="Invoice Detail" subtitle="Unavailable">
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {error || "Invoice not found."}
          </CardContent>
        </Card>
      </PageLayout>
    );
  }

  const recommendation = agentResult?.strategy || invoice.strategy || invoice.ai_recommendation;
  const canonicalPayment = {
    ...(invoice.payment_prediction || {}),
    pay_7_days: invoice.pay_7_days ?? invoice.payment_prediction?.pay_7_days ?? 0,
    pay_15_days: invoice.pay_15_days ?? invoice.payment_prediction?.pay_15_days ?? 0,
    pay_30_days: invoice.pay_30_days ?? invoice.payment_prediction?.pay_30_days ?? 0,
  };
  const canonicalDefault = {
    ...(invoice.default_prediction || {}),
    default_probability:
      invoice.default_probability
      ?? invoice.default_prediction?.default_probability
      ?? Math.max(0, 1 - (canonicalPayment.pay_30_days ?? 0)),
    default_risk_tier:
      invoice.default_risk_tier
      || invoice.default_prediction?.default_risk_tier
      || "Medium",
  };
  const displayedPayment = agentResult?.payment_prediction || canonicalPayment;
  const displayedDefault = agentResult?.default_prediction || canonicalDefault;
  const displayedRisk = invoice.risk_prediction || invoice.delay_prediction || invoice;
  const displayedBehavior = agentResult?.payment_behavior || invoice.payment_behavior;
  const displayedDelay = agentResult?.delay_prediction || invoice.delay_prediction;

  const paymentStatus = displayedPayment?.used_fallback
    ? { label: "Rule Fallback", variant: "warning" }
    : displayedPayment?.llm_refined
    ? { label: "ML + LLM", variant: "success" }
    : displayedPayment
    ? { label: "Canonical Pipeline", variant: "success" }
    : { label: "Unavailable", variant: "outline" };

  const behaviorStatus = displayedBehavior?.used_fallback
    ? { label: "Rule Fallback", variant: "warning" }
    : displayedBehavior?.llm_refined
    ? { label: "ML + LLM", variant: "success" }
    : displayedBehavior
    ? { label: "Canonical Pipeline", variant: "success" }
    : { label: "Unavailable", variant: "outline" };

  const delayStatus = displayedDelay?.used_fallback
    ? { label: "Rule Fallback", variant: "warning" }
    : displayedDelay?.llm_refined
    ? { label: "ML + LLM", variant: "success" }
    : displayedDelay
    ? { label: "Canonical Pipeline", variant: "success" }
    : { label: "Unavailable", variant: "outline" };

  const defaultStatus = displayedDefault?.used_fallback
    ? { label: "Rule Fallback", variant: "warning" }
    : displayedDefault
    ? { label: "Canonical Pipeline", variant: "success" }
    : { label: "Unavailable", variant: "outline" };

  const strategyStatus = agentResult?.strategy
    ? { label: "Agent Output", variant: "success", description: "GPT-4o synthesis over the latest model results" }
    : invoice.strategy
    ? { label: "Canonical Pipeline", variant: "success", description: "Generated from the shared portfolio intelligence pipeline" }
    : { label: "Unavailable", variant: "outline", description: "No strategy output available yet" };

  return (
    <PageLayout title="Invoice Detail" subtitle={`${invoice.invoice_number || invoice.invoice_id} · ${invoice.customer_name}`}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate("/worklist")}
        className="mb-4 gap-2"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Worklist
      </Button>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Badge variant={paymentStatus.variant}>Payment: {paymentStatus.label}</Badge>
        <Badge variant={defaultStatus.variant}>Default: {defaultStatus.label}</Badge>
        <Badge variant={behaviorStatus.variant}>Behavior: {behaviorStatus.label}</Badge>
        <Badge variant={delayStatus.variant}>Delay: {delayStatus.label}</Badge>
        <Badge variant={strategyStatus.variant}>Strategy: {strategyStatus.label}</Badge>
      </div>

      {/* Row 1 — Invoice info + Payment probability + AI rec */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        {/* Invoice Info */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-primary" />
              Invoice Details
            </CardTitle>
          </CardHeader>
          <CardContent>
            <InfoRow label="Invoice ID" value={invoice.invoice_id} mono />
            <InfoRow label="Customer" value={invoice.customer_name} />
            <InfoRow label="Industry" value={invoice.industry || "—"} />
            <InfoRow label="Amount" value={formatCurrency(invoice.amount)} />
            <InfoRow label="Currency" value={invoice.currency || "INR"} />
            <InfoRow label="Issue Date" value={invoice.issue_date} />
            <InfoRow label="Due Date" value={invoice.due_date} />
            <InfoRow label="Status" value={invoice.status?.toUpperCase()} />
            <InfoRow label="Days Overdue" value={invoice.days_overdue > 0 ? `${invoice.days_overdue} days` : "Current"} />
            <div className="pt-3">
              <RiskBadge risk={displayedRisk.risk_label || invoice.risk_label} />
            </div>
            <div className="pt-3">
              <ExplainabilityPanel
                explanation={displayedRisk.explanation}
                drivers={displayedRisk.feature_drivers}
                title="Why The Risk Label Looks Like This"
              />
            </div>
          </CardContent>
        </Card>

        {/* Payment Probability */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-primary" />
              Payment Probability
              <Badge variant={paymentStatus.variant} className="ml-auto">
                {paymentStatus.label}
              </Badge>
            </CardTitle>
            <CardDescription>
              Canonical payment predictions reused across the portfolio, worklist, and forecasts
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5 pt-2">
            <PaymentProbabilityBar label="Within 7 Days" value={displayedPayment.pay_7_days ?? invoice.pay_7_days ?? 0} />
            <PaymentProbabilityBar label="Within 15 Days" value={displayedPayment.pay_15_days ?? invoice.pay_15_days ?? 0} />
            <PaymentProbabilityBar label="Within 30 Days" value={displayedPayment.pay_30_days ?? invoice.pay_30_days ?? 0} />
            <div className="rounded-lg border border-red-200/70 bg-red-50/40 p-3 space-y-3">
              <DefaultProbabilityBar
                label="Still Unpaid After 30 Days"
                value={displayedDefault.default_probability ?? invoice.default_probability ?? 0}
              />
              <div className="flex justify-between gap-4 text-xs text-muted-foreground">
                <span>Default Tier: <strong>{displayedDefault.default_risk_tier || "—"}</strong></span>
                <span>Confidence: <strong>{formatPct(displayedDefault.confidence ?? 0)}</strong></span>
              </div>
            </div>
            <div className="pt-2 text-xs text-muted-foreground space-y-1 border-t border-border">
              <p>Credit Score: <strong>{invoice.credit_score}</strong></p>
              <p>Avg. Days to Pay: <strong>{invoice.avg_days_to_pay}d</strong></p>
              <p>Late Payment History: <strong>{invoice.num_late_payments}</strong></p>
            </div>
            <ExplainabilityPanel
              explanation={displayedPayment.explanation}
              sections={(displayedPayment.feature_drivers_by_horizon || []).map((section) => ({
                title:
                  section.output_name === "pay_7_days"
                    ? "Within 7 Days"
                    : section.output_name === "pay_15_days"
                    ? "Within 15 Days"
                    : "Within 30 Days",
                valueText: formatPct(section.predicted_value),
                drivers: section.drivers,
              }))}
              title="Why These Payment Probabilities Were Predicted"
            />
            <ExplainabilityPanel
              explanation={displayedDefault.explanation}
              drivers={displayedDefault.feature_drivers}
              title="Why This Default Probability Was Predicted"
            />
          </CardContent>
        </Card>

        {/* AI Recommendation / Strategy */}
        <Card className={`border-l-4 ${
          (recommendation?.urgency === "Critical" || recommendation?.priority === "Critical")
            ? "border-l-red-500"
            : (recommendation?.urgency === "High" || recommendation?.priority === "High")
            ? "border-l-orange-500"
            : "border-l-primary"
        }`}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-primary" />
              Collection Recommendation
              <Badge variant={strategyStatus.variant} className="ml-auto">
                {strategyStatus.label}
              </Badge>
            </CardTitle>
            <CardDescription>{strategyStatus.description}</CardDescription>
          </CardHeader>
          <CardContent>
            {recommendation ? (
              <div className="space-y-4">
                <div className="p-3 rounded-lg bg-primary/10">
                  <p className="text-xs text-muted-foreground mb-1">Recommended Action</p>
                  <p className="font-semibold text-primary">
                    {recommendation.recommended_action}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Urgency / Priority</p>
                    <p className={`font-semibold text-sm ${getPriorityColor(recommendation.urgency || recommendation.priority)}`}>
                      {recommendation.urgency || recommendation.priority}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">SLA / Timeline</p>
                    <p className="font-medium text-sm text-foreground">
                      {recommendation.next_action_in_hours
                        ? `${recommendation.next_action_in_hours}h`
                        : recommendation.timeline}
                    </p>
                  </div>
                </div>
                {(recommendation.reason || recommendation.reasoning) && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Reasoning</p>
                    <p className="text-sm text-foreground leading-relaxed">
                      {recommendation.reason || recommendation.reasoning}
                    </p>
                  </div>
                )}
                {invoice.ai_recommendation?.additional_notes && (
                  <div className="p-3 rounded-lg bg-muted/50">
                    <p className="text-xs text-muted-foreground">{invoice.ai_recommendation.additional_notes}</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="animate-pulse h-4 bg-muted rounded" />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Sentinel Alert — shown when external signals exist */}
      <div className="mb-4">
        <SentinelAlert customerId={invoice.customer_id} />
      </div>

      {/* Row 2 — Behavior + Delay + Strategy + Borrower */}
      <div className="grid grid-cols-4 gap-4 mb-4">
        <PaymentBehaviorCard
          behavior={displayedBehavior}
        />
        <DelayPredictionCard
          prediction={displayedDelay}
        />
        <StrategyCard
          strategy={agentResult?.strategy || invoice.strategy}
        />
        <BorrowerRiskCard borrower={borrowerPrediction} />
      </div>

      {/* Row 2b — Confidence Indicator + Candidate Actions */}
      {displayedDelay && (
        <div className="grid grid-cols-2 gap-4 mb-4">
          <ConfidenceIndicator
            prediction={displayedDelay}
            learningBoost={interactions?.learning_confidence_boost}
          />
          <CandidateActionsCard
            candidates={(agentResult?.strategy || invoice.strategy)?.candidate_actions}
            selectionRationale={(agentResult?.strategy || invoice.strategy)?.selection_rationale}
            urgency={(agentResult?.strategy || invoice.strategy)?.urgency}
          />
        </div>
      )}

      {/* Row 3 — Interaction history + action effectiveness + enrichment */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="col-span-1">
          <ActionEffectivenessCard
            effectiveness={interactions?.action_effectiveness}
            bestAction={interactions?.best_action}
          />
        </div>
        <div className="col-span-1">
          <InteractionTimeline invoiceId={invoice?.invoice_id} />
        </div>
        <div className="col-span-1">
          <BorrowerEnrichmentCard customerId={invoice?.customer_id} />
        </div>
      </div>

      {/* Agent Analysis button + Reasoning Trace */}
      <div className="space-y-4 mb-4">
        {/* Run button — full-width gradient when not yet run */}
        {!agentResult?.reasoning_trace?.length && !agentLoading && (
          <div className="relative rounded-xl border border-primary/25 bg-gradient-to-r from-primary/8 via-primary/5 to-background p-4 flex items-center justify-between overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-primary/3 to-transparent pointer-events-none" />
            <div className="relative flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-primary/15 border border-primary/25 flex items-center justify-center">
                <Bot className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">Run Full AI Analysis</p>
                <p className="text-xs text-muted-foreground">GPT-4o ReAct agent · behavior → delay → strategy → synthesis</p>
              </div>
            </div>
            <Button onClick={runAgentAnalysis} disabled={agentLoading} className="relative gap-2 shrink-0">
              <Bot className="h-4 w-4" />
              Analyze with GPT-4o
            </Button>
          </div>
        )}

        {/* Re-run button (compact) when result already showing */}
        {agentResult?.reasoning_trace?.length > 0 && !agentLoading && (
          <div className="flex justify-end">
            <Button variant="outline" onClick={runAgentAnalysis} size="sm" className="gap-2 text-xs">
              <Bot className="h-3.5 w-3.5" />
              Re-run Analysis
            </Button>
          </div>
        )}

        {/* Animated thinking loader */}
        {agentLoading && <AgentThinkingLoader />}

        {/* Reasoning trace — shows every tool GPT-4o called */}
        {!agentLoading && agentResult?.reasoning_trace?.length > 0 && (
          <AgentReasoningTrace
            trace={agentResult.reasoning_trace}
            iterations={agentResult.agent_iterations}
            toolsCalled={agentResult.tools_called}
            summary={agentResult.business_summary}
          />
        )}

        {/* Fallback: plain summary when no trace (e.g. pre-computed mock data) */}
        {!agentLoading && agentResult?.business_summary && !agentResult?.reasoning_trace?.length && (
          <div className="p-4 rounded-xl bg-gradient-to-br from-primary/8 to-primary/3 border border-primary/20">
            <div className="flex items-center gap-2 mb-2">
              <Bot className="h-4 w-4 text-primary" />
              <p className="text-xs font-bold text-primary uppercase tracking-wide">Agent Summary</p>
            </div>
            <p className="text-sm text-foreground leading-relaxed">{agentResult.business_summary}</p>
          </div>
        )}
      </div>

      {/* Free-form Agent Ask Box */}
      <div className="mb-4">
        <AgentAskBox
          invoiceId={invoice.invoice_id}
          customerId={invoice.customer_id}
        />
      </div>

      {/* Row 3 — SHAP Explanation */}
      <div>
        <ShapBarChart explanation={invoice.shap_explanation} />
      </div>
    </PageLayout>
  );
}
