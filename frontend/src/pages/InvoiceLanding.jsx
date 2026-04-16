import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageLayout } from "@/components/layout/PageLayout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export function InvoiceLanding() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function resolveInvoice() {
      setLoading(true);
      setError(null);
      try {
        const data = await api.listInvoices({ limit: 1 });
        const first = data?.invoices?.[0];
        if (!cancelled && first?.invoice_id) {
          navigate(`/invoices/${first.invoice_id}`, { replace: true });
          return;
        }
        if (!cancelled) {
          setError("No invoices available yet.");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err?.message || "Failed to load invoices.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    resolveInvoice();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  return (
    <PageLayout title="Invoice Detail" subtitle={loading ? "Loading..." : "Unavailable"}>
      <Card>
        <CardContent className="py-10 text-center space-y-3">
          <p className="text-sm text-muted-foreground">
            {loading ? "Opening the latest invoice..." : error || "Invoice data is unavailable."}
          </p>
          {!loading && (
            <Button variant="outline" onClick={() => navigate("/worklist")}>
              Go to Collector Worklist
            </Button>
          )}
        </CardContent>
      </Card>
    </PageLayout>
  );
}
