import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Bot,
  AlertTriangle,
  CheckCircle,
  Clock,
  DollarSign,
} from "lucide-react";
import { PageLayout } from "@/components/layout/PageLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RiskBadge } from "@/components/dashboard/RiskBadge";
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
  const [recLoading, setRecLoading] = useState(false);
  const [recommendation, setRecommendation] = useState(null);

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

  useEffect(() => {
    if (!invoice) return;
    // Use pre-computed recommendation from mock data if available
    if (invoice.ai_recommendation) {
      setRecommendation(invoice.ai_recommendation);
      return;
    }
    // Otherwise fetch from backend
    async function fetchRecommendation() {
      setRecLoading(true);
      try {
        const rec = await api.getRecommendation({
          invoice_id: invoice.invoice_id,
          invoice_amount: invoice.amount,
          days_overdue: invoice.days_overdue,
          risk_label: invoice.risk_label,
          pay_7_days: invoice.pay_7_days,
          pay_15_days: invoice.pay_15_days,
          pay_30_days: invoice.pay_30_days,
          customer_history: {
            customer_name: invoice.customer_name,
            avg_days_to_pay: invoice.avg_days_to_pay || 30,
            num_late_payments: invoice.num_late_payments || 0,
            num_disputes: 0,
            total_outstanding: invoice.amount,
            credit_score: invoice.credit_score || 650,
            industry: invoice.industry || "unknown",
          },
        });
        setRecommendation(rec);
      } catch {
        setRecommendation({
          recommended_action: invoice.recommended_action,
          priority: "High",
          timeline: "Within 48 Hours",
          reasoning: "Based on risk classification and payment probability.",
        });
      } finally {
        setRecLoading(false);
      }
    }
    fetchRecommendation();
  }, [invoice]);

  if (loading) {
    return (
      <PageLayout title="Invoice Detail" subtitle="Loading…">
        <div className="grid grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="animate-pulse rounded-xl bg-muted h-48" />
          ))}
        </div>
      </PageLayout>
    );
  }

  if (!invoice) return null;

  const priorityLevel =
    invoice.days_overdue > 60 || invoice.risk_label === "High"
      ? "Critical"
      : invoice.days_overdue > 30
      ? "High"
      : "Medium";

  return (
    <PageLayout title="Invoice Detail" subtitle={`${invoice.invoice_number} · ${invoice.customer_name}`}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate("/worklist")}
        className="mb-4 gap-2"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Worklist
      </Button>

      <div className="grid grid-cols-3 gap-4">
        {/* Invoice Info */}
        <Card className="col-span-1">
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
        <Card className="col-span-1">
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

        {/* AI Recommendation */}
        <Card className={`col-span-1 border-l-4 ${
          recommendation?.priority === "Critical" ? "border-l-red-500" :
          recommendation?.priority === "High" ? "border-l-orange-500" :
          "border-l-primary"
        }`}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-primary" />
              AI Recommendation
            </CardTitle>
            <CardDescription>GPT-4o powered collection strategy</CardDescription>
          </CardHeader>
          <CardContent>
            {recLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="animate-pulse h-4 bg-muted rounded" />
                ))}
              </div>
            ) : recommendation ? (
              <div className="space-y-4">
                <div className="p-3 rounded-lg bg-primary/10">
                  <p className="text-xs text-muted-foreground mb-1">Recommended Action</p>
                  <p className="font-semibold text-primary">{recommendation.recommended_action}</p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Priority</p>
                    <p className={`font-semibold text-sm ${getPriorityColor(recommendation.priority)}`}>
                      {recommendation.priority}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Timeline</p>
                    <p className="font-medium text-sm text-foreground">{recommendation.timeline}</p>
                  </div>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Reasoning</p>
                  <p className="text-sm text-foreground leading-relaxed">{recommendation.reasoning}</p>
                </div>
                {recommendation.additional_notes && (
                  <div className="p-3 rounded-lg bg-muted/50">
                    <p className="text-xs text-muted-foreground">{recommendation.additional_notes}</p>
                  </div>
                )}
              </div>
            ) : null}
          </CardContent>
        </Card>

        {/* SHAP Explanation */}
        <div className="col-span-3">
          <ShapBarChart explanation={invoice.shap_explanation} />
        </div>
      </div>
    </PageLayout>
  );
}
