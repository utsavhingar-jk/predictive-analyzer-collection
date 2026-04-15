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
import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { PaymentBehaviorCard } from "@/components/dashboard/PaymentBehaviorCard";
import { DelayPredictionCard } from "@/components/dashboard/DelayPredictionCard";
import { StrategyCard } from "@/components/dashboard/StrategyCard";
import { BorrowerRiskCard } from "@/components/dashboard/BorrowerRiskCard";
import { AgentReasoningTrace } from "@/components/agent/AgentReasoningTrace";
import { AgentAskBox } from "@/components/agent/AgentAskBox";
import { ShapBarChart } from "@/components/charts/ShapBarChart";
import { api } from "@/lib/api";
import { mockInvoiceDetail } from "@/lib/mockData";
import { formatCurrency, formatPct, getPriorityColor } from "@/lib/utils";

function PaymentProbabilityBar({ label, value }) {
  const pct = Math.round(value * 100);
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

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const data = await api.getInvoice(invoiceId);
        if (!cancelled) setInvoice(data);
      } catch {
        if (!cancelled) {
          const fallback = mockInvoiceDetail[invoiceId] || mockInvoiceDetail["INV-2024-001"];
          setInvoice(fallback);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [invoiceId]);

  // Load borrower-level prediction when invoice loads
  useEffect(() => {
    if (!invoice) return;
    const customerId = String(invoice.customer_id || "1");
    api.getBorrowerPrediction(customerId)
      .then(setBorrowerPrediction)
      .catch(() => {/* borrower prediction unavailable — card stays hidden */});
  }, [invoice]);

  // Pre-populate agent result from mock data if present
  useEffect(() => {
    if (!invoice) return;
    if (invoice.payment_behavior || invoice.delay_prediction || invoice.strategy) {
      setAgentResult({
        payment_behavior: invoice.payment_behavior,
        delay_prediction: invoice.delay_prediction,
        strategy: invoice.strategy,
        business_summary: invoice.ai_recommendation?.reasoning,
        recommended_action: invoice.ai_recommendation?.recommended_action || invoice.recommended_action,
      });
    }
  }, [invoice]);

  async function runAgentAnalysis() {
    if (!invoice) return;
    setAgentLoading(true);
    try {
      // Coerce all values to the exact types the backend schema requires.
      // customer_id MUST be a string (Pydantic v2 won't coerce int→str).
      // All numeric fields default-guarded so null/undefined never reaches the API.
      const behaviorOnTimeRatio = invoice.payment_behavior?.on_time_ratio ?? 70;
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
        avg_delay_days: Number(invoice.payment_behavior?.avg_delay_days) || 10,
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

  if (!invoice) return null;

  const recommendation = agentResult?.strategy || invoice.strategy || invoice.ai_recommendation;

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
            <InfoRow label="Currency" value={invoice.currency || "USD"} />
            <InfoRow label="Issue Date" value={invoice.issue_date} />
            <InfoRow label="Due Date" value={invoice.due_date} />
            <InfoRow label="Status" value={invoice.status?.toUpperCase()} />
            <InfoRow label="Days Overdue" value={invoice.days_overdue > 0 ? `${invoice.days_overdue} days` : "Current"} />
            <div className="pt-3">
              <RiskBadge risk={invoice.risk_label} />
            </div>
          </CardContent>
        </Card>

        {/* Payment Probability */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-primary" />
              Payment Probability
            </CardTitle>
            <CardDescription>ML model predictions per time horizon</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5 pt-2">
            <PaymentProbabilityBar label="Within 7 Days" value={invoice.pay_7_days} />
            <PaymentProbabilityBar label="Within 15 Days" value={invoice.pay_15_days} />
            <PaymentProbabilityBar label="Within 30 Days" value={invoice.pay_30_days} />
            <div className="pt-2 text-xs text-muted-foreground space-y-1 border-t border-border">
              <p>Credit Score: <strong>{invoice.credit_score}</strong></p>
              <p>Avg. Days to Pay: <strong>{invoice.avg_days_to_pay}d</strong></p>
              <p>Late Payment History: <strong>{invoice.num_late_payments}</strong></p>
            </div>
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
              AI Recommendation
            </CardTitle>
            <CardDescription>GPT-4o powered collection strategy</CardDescription>
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

      {/* Row 2 — Behavior + Delay + Strategy + Borrower */}
      <div className="grid grid-cols-4 gap-4 mb-4">
        <PaymentBehaviorCard
          behavior={agentResult?.payment_behavior || invoice.payment_behavior}
        />
        <DelayPredictionCard
          prediction={agentResult?.delay_prediction || invoice.delay_prediction}
        />
        <StrategyCard
          strategy={agentResult?.strategy || invoice.strategy}
        />
        <BorrowerRiskCard borrower={borrowerPrediction} />
      </div>

      {/* Agent Analysis button + Reasoning Trace */}
      <div className="space-y-4 mb-4">
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground" />
          <Button
            onClick={runAgentAnalysis}
            disabled={agentLoading}
            className="gap-2"
          >
            <Bot className="h-4 w-4" />
            {agentLoading ? "Agent Thinking…" : "Run Full AI Analysis"}
          </Button>
        </div>

        {/* Reasoning trace — shows every tool GPT-4o called */}
        {agentResult?.reasoning_trace?.length > 0 && (
          <AgentReasoningTrace
            trace={agentResult.reasoning_trace}
            iterations={agentResult.agent_iterations}
            toolsCalled={agentResult.tools_called}
            summary={agentResult.business_summary}
          />
        )}

        {/* Fallback: plain summary when no trace (e.g. pre-computed mock data) */}
        {agentResult?.business_summary && !agentResult?.reasoning_trace?.length && (
          <div className="p-4 rounded-lg bg-muted/50 border border-border">
            <p className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wide">
              Agent Business Summary
            </p>
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
