import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  ListChecks,
  FileText,
  FlaskConical,
  Users,
  Zap,
  Radio,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Executive Dashboard" },
  { to: "/worklist", icon: ListChecks, label: "Collector Worklist" },
  { to: "/borrowers", icon: Users, label: "Borrower Portfolio" },
  { to: "/watchlist", icon: Radio, label: "Sentinel Watchlist", badge: "AI" },
  { to: "/invoices/INV-2024-001", icon: FileText, label: "Invoice Detail" },
  { to: "/simulator", icon: FlaskConical, label: "Scenario Simulator" },
];

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-50 w-64 border-r border-border bg-card flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-border">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
          <Zap className="h-5 w-5 text-primary-foreground" />
        </div>
        <div>
          <p className="text-sm font-bold text-foreground leading-tight">AI Collector</p>
          <p className="text-xs text-muted-foreground">Predictive AR Platform</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <p className="px-3 mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Analytics
        </p>
        {navItems.map(({ to, icon: Icon, label, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )
            }
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            <span className="flex-1">{label}</span>
            {badge && (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-primary/15 text-primary border border-primary/25">
                {badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-border">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-muted-foreground">All systems operational</span>
        </div>
      </div>
    </aside>
  );
}
