import { useState, useEffect } from "react";
import { api } from "@/lib/api";

/**
 * Hook that loads the prioritized collector worklist.
 */
export function useWorklist() {
  const [worklist, setWorklist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("all");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const data = await api.getPrioritizedWorklist();
        if (!cancelled) setWorklist(data);
      } catch {
        if (!cancelled) setWorklist([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  const filtered = worklist.filter((inv) => {
    const matchSearch =
      search === "" ||
      inv.customer_name.toLowerCase().includes(search.toLowerCase()) ||
      inv.invoice_id.toLowerCase().includes(search.toLowerCase());
    const effectiveRisk = inv.risk_tier || inv.risk_label;
    const matchRisk = riskFilter === "all" || effectiveRisk === riskFilter;
    return matchSearch && matchRisk;
  });

  return { worklist: filtered, loading, search, setSearch, riskFilter, setRiskFilter };
}
