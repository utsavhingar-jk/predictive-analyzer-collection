import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { mockWorklist } from "@/lib/mockData";

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
        if (!cancelled) setWorklist(mockWorklist);
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
    const matchRisk = riskFilter === "all" || inv.risk_label === riskFilter;
    return matchSearch && matchRisk;
  });

  return { worklist: filtered, loading, search, setSearch, riskFilter, setRiskFilter };
}
