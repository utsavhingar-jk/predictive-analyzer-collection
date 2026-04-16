import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { ExecutiveDashboard } from "@/pages/ExecutiveDashboard";
import { CollectorWorklist } from "@/pages/CollectorWorklist";
import { InvoiceDetail } from "@/pages/InvoiceDetail";
import { InvoiceLanding } from "@/pages/InvoiceLanding";
import { ScenarioSimulator } from "@/pages/ScenarioSimulator";
import { BorrowerPortfolio } from "@/pages/BorrowerPortfolio";
import { Watchlist } from "@/pages/Watchlist";

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-background overflow-hidden">
        <Sidebar />
        <div className="flex-1 ml-64 flex flex-col min-h-0 overflow-hidden">
          <Routes>
            <Route path="/" element={<ExecutiveDashboard />} />
            <Route path="/worklist" element={<CollectorWorklist />} />
            <Route path="/invoices" element={<InvoiceLanding />} />
            <Route path="/invoices/:invoiceId" element={<InvoiceDetail />} />
            <Route path="/simulator" element={<ScenarioSimulator />} />
            <Route path="/borrowers" element={<BorrowerPortfolio />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
