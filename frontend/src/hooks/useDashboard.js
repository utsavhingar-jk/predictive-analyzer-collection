import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { mockSummary, mockDSO, mockCashflow } from "@/lib/mockData";

/**
 * Hook that loads all data needed for the Executive Dashboard.
 * Falls back to mock data if the backend is unreachable.
 */
export function useDashboard() {
  const [summary, setSummary] = useState(null);
  const [dso, setDso] = useState(null);
  const [cashflow, setCashflow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const [summaryData, dsoData, cashflowData] = await Promise.all([
          api.getInvoiceSummary(),
          api.predictDSO(),
          api.getCashflowForecast(),
        ]);
        if (!cancelled) {
          setSummary(summaryData);
          setDso(dsoData);
          setCashflow(cashflowData);
        }
      } catch (err) {
        console.warn("Backend unavailable, using mock data:", err.message);
        if (!cancelled) {
          setSummary(mockSummary);
          setDso(mockDSO);
          setCashflow(mockCashflow);
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

  return { summary, dso, cashflow, loading, error };
}
