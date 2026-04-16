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
  const [paymentPrediction, setPaymentPrediction] = useState(null);
  const [riskPrediction, setRiskPrediction] = useState(null);
  const [behaviorPrediction, setBehaviorPrediction] = useState(null);
  const [delayPrediction, setDelayPrediction] = useState(null);
  const [optimizedStrategy, setOptimizedStrategy] = useState(null);

  useEffect(() => {
    let cancelled = false;
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

  useEffect(() => {
    if (!invoice) return;
    let cancelled = false;

    const basePredictionPayload = {
      invoice_id: String(invoice.invoice_id),
      invoice_amount: Number(invoice.amount) || 1,
      days_overdue: Math.round(Number(invoice.days_overdue) || 0),
      customer_credit_score: Math.round(Number(invoice.credit_score) || 650),
      customer_avg_days_to_pay: Number(invoice.avg_days_to_pay) || 30,
      payment_terms: Math.round(Number(invoice.payment_terms) || 30),
      num_previous_invoices: Math.round(Number(invoice.num_previous_invoices) || 10),
      num_late_payments: Math.round(Number(invoice.num_late_payments) || 0),
      industry: invoice.industry || "unknown",
      customer_total_overdue: Number(invoice.customer_total_overdue) || 0,
    };

    const behaviorPayload = {
      customer_id: String(invoice.customer_id ?? invoice.customer_name),
      customer_name: String(invoice.customer_name),
      historical_on_time_ratio: Number(invoice.payment_behavior?.on_time_ratio ?? 70) / 100,
      avg_delay_days: Number(invoice.payment_behavior?.avg_delay_days) || Math.max(4, Number(invoice.days_overdue) * 0.45 || 10),
      repayment_consistency: 0.6,
      partial_payment_frequency: 0.1,
      prior_delayed_invoice_count: Math.round(Number(invoice.num_late_payments) || 0),
      payment_after_followup_count: Math.round(Number(invoice.num_late_payments) || 0),
      total_invoices: Math.round(Number(invoice.num_previous_invoices) || 10),
      deterioration_trend: 0.0,
      invoice_acknowledgement_behavior: "normal",
      transaction_success_failure_pattern: 0.05,
    };

    async function loadPredictions() {
      const [paymentRes, riskRes, behaviorRes] = await Promise.allSettled([
        api.predictPayment(basePredictionPayload),
        api.predictRisk(basePredictionPayload),
        api.analyzePaymentBehavior(behaviorPayload),
      ]);

      const paymentData = paymentRes.status === "fulfilled" ? paymentRes.value : null;
      const riskData = riskRes.status === "fulfilled" ? riskRes.value : null;
      const behaviorData = behaviorRes.status === "fulfilled" ? behaviorRes.value : null;

      if (!cancelled) {
        setPaymentPrediction(paymentData);
        setRiskPrediction(riskData);
        setBehaviorPrediction(behaviorData);
      }

      const delayPayload = {
        invoice_id: String(invoice.invoice_id),
        invoice_amount: Number(invoice.amount) || 1,
        days_overdue: Math.round(Number(invoice.days_overdue) || 0),
        payment_terms: Math.round(Number(invoice.payment_terms) || 30),
        customer_avg_invoice_amount: Number(invoice.amount) || 1,
        customer_credit_score: Math.round(Number(invoice.credit_score) || 650),
        customer_avg_days_to_pay: Number(invoice.avg_days_to_pay) || 30,
        num_late_payments: Math.round(Number(invoice.num_late_payments) || 0),
        num_previous_invoices: Math.round(Number(invoice.num_previous_invoices) || 10),
        industry: invoice.industry || "unknown",
        customer_total_overdue: Number(invoice.customer_total_overdue) || 0,
        behavior_type: behaviorData?.behavior_type,
        on_time_ratio: behaviorData?.on_time_ratio,
        avg_delay_days_historical: behaviorData?.avg_delay_days,
        behavior_risk_score: behaviorData?.behavior_risk_score,
        deterioration_trend:
          behaviorData?.trend === "Worsening"
            ? 0.3
            : behaviorData?.trend === "Improving"
            ? -0.2
            : 0.0,
        followup_dependency: behaviorData?.followup_dependency,
      };

      const delayRes = await api.predictDelay(delayPayload).catch(() => null);
      if (!cancelled) setDelayPrediction(delayRes);

      const strategyInput = {
        invoice_id: String(invoice.invoice_id),
        customer_name: String(invoice.customer_name),
        invoice_amount: Number(invoice.amount) || 1,
        days_overdue: Math.round(Number(invoice.days_overdue) || 0),
        delay_probability:
          Number(delayRes?.delay_probability ?? invoice.delay_prediction?.delay_probability) || 0,
        risk_tier:
          String(delayRes?.risk_tier ?? invoice.delay_prediction?.risk_tier ?? riskData?.risk_label ?? "Medium"),
        nach_applicable: Boolean(
          behaviorData?.nach_recommended ?? borrowerPrediction?.nach_recommended ?? false,
        ),
        behavior_type: behaviorData?.behavior_type,
        followup_dependency: behaviorData?.followup_dependency,
      };

      const strategyRes = await api.optimizeStrategy(strategyInput).catch(() => null);
      if (!cancelled) setOptimizedStrategy(strategyRes);
    }

    loadPredictions();
    return () => { cancelled = true; };
  }, [invoice, borrowerPrediction]);

  async function runAgentAnalysis() {
    if (!invoice) return;
    setAgentLoading(true);
    try {
      // Coerce all values to the exact types the backend schema requires.
      // customer_id MUST be a string (Pydantic v2 won't coerce int→str).
      // All numeric fields default-guarded so null/undefined never reaches the API.
      const activeBehavior = behaviorPrediction || invoice.payment_behavior;
      const behaviorOnTimeRatio = activeBehavior?.on_time_ratio ?? 70;
      const result = await api.analyzeCase({
        invoice_id: String(invoice.invoice_id),
        customer_id: String(invoice.customer_id ?? invoice.customer_name),
        customer_name: String(invoice.customer_name),
        invoice_amount: Number(invoice.amount) || 0,
        days_overdue: Math.round(Number(invoice.days_overdue) || 0),
        payment_terms: Math.round(Number(invoice.payment_terms) || 30),
        customer_credit_score: Math.round(Number(invoice.credit_score) || 650),
        customer_avg_days_to_pay: Number(invoice.avg_days_to_pay) || 30,
        num_late_payments: Math.round(Number(invoice.num_late_payments) || 0),
        customer_total_overdue: Number(invoice.customer_total_overdue) || 0,
        industry: invoice.industry || "unknown",
        historical_on_time_ratio: Number(behaviorOnTimeRatio) / 100,
        avg_delay_days: Number(activeBehavior?.avg_delay_days) || 10,
        repayment_consistency: 0.6,
        partial_payment_frequency: 0.1,
        payment_after_followup_count: Math.round(Number(invoice.num_late_payments) || 0),
        total_invoices: 10,
        deterioration_trend: 0.0,
        invoice_acknowledgement_behavior: "normal",
        transaction_success_failure_pattern: 0.05,
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

  const recommendation = agentResult?.strategy || optimizedStrategy || invoice.strategy || invoice.ai_recommendation;
  const displayedPayment = paymentPrediction || invoice;
  const displayedRisk = riskPrediction || invoice;
  const displayedBehavior = agentResult?.payment_behavior || behaviorPrediction || invoice.payment_behavior;
  const displayedDelay = agentResult?.delay_prediction || delayPrediction || invoice.delay_prediction;

  const paymentStatus = displayedPayment?.used_fallback
    ? { label: "Rule Fallback", variant: "warning" }
    : displayedPayment?.llm_refined
    ? { label: "ML + LLM", variant: "success" }
    : paymentPrediction
    ? { label: "ML Live", variant: "success" }
    : { label: "Seeded", variant: "outline" };

  const behaviorStatus = displayedBehavior?.used_fallback
    ? { label: "Rule Fallback", variant: "warning" }
    : displayedBehavior?.llm_refined
    ? { label: "ML + LLM", variant: "success" }
    : behaviorPrediction
    ? { label: "ML Live", variant: "success" }
    : { label: "Unavailable", variant: "outline" };

  const delayStatus = displayedDelay?.used_fallback
    ? { label: "Rule Fallback", variant: "warning" }
    : displayedDelay?.llm_refined
    ? { label: "ML + LLM", variant: "success" }
    : delayPrediction
    ? { label: "ML Live", variant: "success" }
    : { label: "Seeded", variant: "outline" };

  const strategyStatus = agentResult?.strategy
    ? { label: "Agent Output", variant: "success", description: "GPT-4o synthesis over the latest model results" }
    : optimizedStrategy
    ? { label: "Pipeline Live", variant: "success", description: "Generated from live behavior + delay predictions" }
    : invoice.strategy
    ? { label: "Seeded Rule", variant: "warning", description: "Precomputed fallback from invoice context" }
    : { label: "Unavailable", variant: "outline", description: "No strategy output available yet" };

  return (
    <PageLayout title="Invoice Detail" subtitle={`${invoice.invoice_number || invoice.invoice_id} · ${invoice.customer_name}`}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate("/worklist")}
        className="mb-4 gap-2 hover:-translate-x-1 transition-transform"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Worklist
      </Button>

      <div className="mb-6 flex flex-wrap items-center gap-2 border-b border-border/50 pb-4">
        <Badge variant={paymentStatus.variant}>Payment: {paymentStatus.label}</Badge>
        <Badge variant={behaviorStatus.variant}>Behavior: {behaviorStatus.label}</Badge>
        <Badge variant={delayStatus.variant}>Delay: {delayStatus.label}</Badge>
        <Badge variant={strategyStatus.variant}>Strategy: {strategyStatus.label}</Badge>
      </div>

      {/* Sentinel Alert — shown when external signals exist */}
      <div className="mb-6">
        <SentinelAlert customerId={invoice.customer_id} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* -------------------- LEFT COLUMN: Main Content -------------------- */}
        <div className="lg:col-span-2 space-y-6">
          {/* Invoice Info */}
          <Card className="hover:shadow-lg transition-all duration-300 border-border/60 hover:border-primary/20 bg-gradient-to-br from-card to-muted/10 overflow-hidden">
            <CardHeader className="bg-muted/10 border-b border-border/50 pb-4">
              <CardTitle className="flex items-center gap-2 text-base font-bold">
                <DollarSign className="h-4 w-4 text-primary" />
                Invoice Details
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2">
                <div className="space-y-1">
                  <InfoRow label="Invoice ID" value={invoice.invoice_id} mono />
                  <InfoRow label="Customer" value={invoice.customer_name} />
                  <InfoRow label="Industry" value={invoice.industry || "—"} />
                  <InfoRow label="Amount" value={formatCurrency(invoice.amount)} />
                  <InfoRow label="Currency" value={invoice.currency || "INR"} />
                </div>
                <div className="space-y-1">
                  <InfoRow label="Issue Date" value={invoice.issue_date} />
                  <InfoRow label="Due Date" value={invoice.due_date} />
                  <InfoRow label="Status" value={invoice.status?.toUpperCase()} />
                  <InfoRow label="Days Overdue" value={invoice.days_overdue > 0 ? `${invoice.days_overdue} days` : "Current"} />
                  <div className="pt-2 pb-1">
                    <RiskBadge risk={displayedRisk.risk_label || invoice.risk_label} />
                  </div>
                </div>
              </div>
              <div className="pt-4 mt-2 border-t border-border/50">
                <ExplainabilityPanel
                  explanation={displayedRisk.explanation}
                  drivers={displayedRisk.feature_drivers}
                  title="Why The Risk Label Looks Like This"
                />
              </div>
            </CardContent>
          </Card>

          {/* AI Collection Recommendation */}
          <Card className={`hover:shadow-lg transition-all duration-300 border-l-4 overflow-hidden ${
            (recommendation?.urgency === "Critical" || recommendation?.priority === "Critical")
              ? "border-l-red-500 hover:border-red-500/50"
              : (recommendation?.urgency === "High" || recommendation?.priority === "High")
              ? "border-l-orange-500 hover:border-orange-500/50"
              : "border-l-primary hover:border-primary/50"
          }`}>
            <CardHeader className="bg-muted/10 border-b border-border/50 pb-4">
              <CardTitle className="flex items-center gap-2 text-base font-bold">
                <Bot className="h-4 w-4 text-primary" />
                Collection Recommendation
                <Badge variant={strategyStatus.variant} className="ml-auto">
                  {strategyStatus.label}
                </Badge>
              </CardTitle>
              <CardDescription>{strategyStatus.description}</CardDescription>
            </CardHeader>
            <CardContent className="pt-5">
              {recommendation ? (
                <div className="space-y-5">
                  <div className="p-4 rounded-xl bg-primary/10 border border-primary/20">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Recommended Action</p>
                    <p className="text-lg font-bold text-primary">
                      {recommendation.recommended_action}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-4 bg-muted/30 p-4 rounded-xl border border-border/40">
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Urgency / Priority</p>
                      <p className={`font-bold text-sm ${getPriorityColor(recommendation.urgency || recommendation.priority)}`}>
                        {recommendation.urgency || recommendation.priority}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">SLA / Timeline</p>
                      <p className="font-bold text-sm text-foreground">
                        {recommendation.next_action_in_hours
                          ? `${recommendation.next_action_in_hours}h`
                          : recommendation.timeline}
                      </p>
                    </div>
                  </div>
                  {(recommendation.reason || recommendation.reasoning) && (
                    <div className="p-4 border border-border/50 rounded-xl bg-card">
                      <p className="text-xs font-semibold text-muted-foreground mb-2">Reasoning</p>
                      <p className="text-sm text-foreground leading-relaxed">
                        {recommendation.reason || recommendation.reasoning}
                      </p>
                    </div>
                  )}
                  {invoice.ai_recommendation?.additional_notes && (
                    <div className="p-3 rounded-lg bg-muted/50 text-xs text-muted-foreground">
                      {invoice.ai_recommendation.additional_notes}
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="animate-pulse h-4 bg-muted rounded-md" />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Interaction & Effectiveness */}
          <div className="grid grid-cols-1 gap-6">
            <ActionEffectivenessCard
              effectiveness={interactions?.action_effectiveness}
              bestAction={interactions?.best_action}
            />
            <InteractionTimeline invoiceId={invoice?.invoice_id} />
          </div>

          {/* AI Analysis Triggers & Ask Box */}
          <div className="space-y-6">
            {!agentResult?.reasoning_trace?.length && !agentLoading && (
              <div className="relative rounded-2xl border border-primary/25 bg-gradient-to-r from-primary/10 via-primary/5 to-background p-5 flex items-center justify-between overflow-hidden shadow-sm hover:shadow-md transition-shadow">
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-primary/5 to-transparent pointer-events-none" />
                <div className="relative flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-primary/20 border border-primary/30 flex items-center justify-center">
                    <Bot className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-foreground">Run Full AI Analysis</p>
                    <p className="text-xs text-muted-foreground">GPT-4o ReAct agent will analyze behavior, delays, and predict optimal strategies.</p>
                  </div>
                </div>
                <Button onClick={runAgentAnalysis} disabled={agentLoading} className="relative gap-2 shrink-0 hover:scale-105 transition-transform">
                  <Bot className="h-4 w-4" />
                  Analyze Case
                </Button>
              </div>
            )}

            {agentResult?.reasoning_trace?.length > 0 && !agentLoading && (
              <div className="flex justify-end">
                <Button variant="outline" onClick={runAgentAnalysis} size="sm" className="gap-2 text-xs hover:bg-primary/10 transition-colors">
                  <Bot className="h-3.5 w-3.5" />
                  Re-run Analysis
                </Button>
              </div>
            )}

            {agentLoading && <AgentThinkingLoader />}

            {!agentLoading && agentResult?.reasoning_trace?.length > 0 && (
              <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
                <AgentReasoningTrace
                  trace={agentResult.reasoning_trace}
                  iterations={agentResult.agent_iterations}
                  toolsCalled={agentResult.tools_called}
                  summary={agentResult.business_summary}
                />
              </div>
            )}

            {!agentLoading && agentResult?.business_summary && !agentResult?.reasoning_trace?.length && (
              <div className="p-5 rounded-2xl bg-gradient-to-br from-primary/10 to-primary/5 border border-primary/20 hover:shadow-md transition-all">
                <div className="flex items-center gap-2 mb-3">
                  <Bot className="h-4 w-4 text-primary" />
                  <p className="text-xs font-bold text-primary uppercase tracking-wide">Agent Summary</p>
                </div>
                <p className="text-sm text-foreground leading-relaxed">{agentResult.business_summary}</p>
              </div>
            )}

            <div className="hover:shadow-md transition-all duration-300 rounded-xl overflow-hidden border border-border/50">
              <AgentAskBox
                invoiceId={invoice.invoice_id}
                customerId={invoice.customer_id}
              />
            </div>
          </div>
        </div>

        {/* -------------------- RIGHT COLUMN: Analytics Sidebar -------------------- */}
        <div className="lg:col-span-1 space-y-6">
          {/* Payment Probability */}
          <Card className="hover:shadow-lg transition-all duration-300 border-border/60 hover:border-primary/20 overflow-hidden">
            <CardHeader className="bg-muted/10 border-b border-border/50 pb-3">
              <CardTitle className="flex items-center gap-2 text-sm font-bold">
                <Clock className="h-4 w-4 text-primary" />
                Payment Probability
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5 pt-4">
              <PaymentProbabilityBar label="Within 7 Days" value={displayedPayment.pay_7_days ?? invoice.pay_7_days ?? 0} />
              <PaymentProbabilityBar label="Within 15 Days" value={displayedPayment.pay_15_days ?? invoice.pay_15_days ?? 0} />
              <PaymentProbabilityBar label="Within 30 Days" value={displayedPayment.pay_30_days ?? invoice.pay_30_days ?? 0} />
              
              <div className="pt-3 text-xs text-muted-foreground space-y-1.5 border-t border-border/50 mt-4 outline-none">
                <p className="flex justify-between"><span>Credit Score:</span> <strong className="text-foreground">{invoice.credit_score}</strong></p>
                <p className="flex justify-between"><span>Avg. Days to Pay:</span> <strong className="text-foreground">{invoice.avg_days_to_pay}d</strong></p>
                <p className="flex justify-between"><span>Late Payment History:</span> <strong className="text-foreground">{invoice.num_late_payments}</strong></p>
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
                title="Probability Drivers"
              />
            </CardContent>
          </Card>

          {/* Core Analytics Cards */}
          <DelayPredictionCard prediction={displayedDelay} />
          <PaymentBehaviorCard behavior={displayedBehavior} />
          <StrategyCard strategy={agentResult?.strategy || invoice.strategy} />
          <BorrowerRiskCard borrower={borrowerPrediction} />

          {/* Conditional Analysis */}
          {displayedDelay && (
            <div className="space-y-6">
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

          <BorrowerEnrichmentCard customerId={invoice?.customer_id} />
          
          <div className="pb-4">
             <ShapBarChart explanation={invoice.shap_explanation} />
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
