import { useState, useEffect } from "react";
import { api } from "@/lib/api";

/**
 * Hook that loads all data needed for the Executive Dashboard.
 */
export function useDashboard() {
  const [summary, setSummary] = useState(null);
  const [dso, setDso] = useState(null);
  const [cashflow, setCashflow] = useState(null);
  const [worklist, setWorklist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const [summaryData, dsoData, cashflowData, worklistData] = await Promise.all([
          api.getInvoiceSummary(),
          api.predictDSO(),
          api.getCashflowForecast(),
          api.getPrioritizedWorklist(),
        ]);
        if (!cancelled) {
          setSummary(summaryData);
          setDso(dsoData);
          setCashflow(cashflowData);
          setWorklist(Array.isArray(worklistData) ? worklistData : []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err?.message || "Failed to load dashboard data");
          setSummary(null);
          setDso(null);
          setCashflow(null);
          setWorklist([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { summary, dso, cashflow, worklist, loading, error };
}
