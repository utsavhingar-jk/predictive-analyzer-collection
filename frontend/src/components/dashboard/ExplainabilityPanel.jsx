import { BrainCircuit, TrendingDown, TrendingUp } from "lucide-react";

function formatFeatureValue(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "—";
  if (Math.abs(num) >= 100000) return num.toLocaleString("en-IN", { maximumFractionDigits: 0 });
  if (Math.abs(num) >= 1000) return num.toLocaleString("en-IN", { maximumFractionDigits: 1 });
  if (Number.isInteger(num)) return num.toLocaleString("en-IN");
  return num.toLocaleString("en-IN", { maximumFractionDigits: 3 });
}

function formatContribution(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "—";
  return `${num >= 0 ? "+" : ""}${num.toFixed(3)}`;
}

function DriverRow({ driver, maxContribution }) {
  const contribution = Math.abs(Number(driver?.contribution) || 0);
  const width = maxContribution > 0 ? Math.max(14, Math.round((contribution / maxContribution) * 100)) : 0;
  const positive = driver?.direction === "increases_prediction";

  return (
    <div className="space-y-2 rounded-lg border border-border/70 bg-background/70 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{driver?.display_name || driver?.feature_name}</p>
          <p className="text-xs text-muted-foreground">Value: {formatFeatureValue(driver?.feature_value)}</p>
        </div>
        <div className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-semibold ${
          positive
            ? "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-300"
            : "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-300"
        }`}>
          {positive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
          {positive ? "Raises Output" : "Lowers Output"}
        </div>
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between text-[11px] text-muted-foreground">
          <span>Model contribution</span>
          <span className="font-mono">{formatContribution(driver?.contribution)}</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full ${positive ? "bg-red-500" : "bg-green-500"}`}
            style={{ width: `${width}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function DriverSection({ title, valueText, drivers }) {
  if (!drivers?.length) return null;
  const maxContribution = Math.max(...drivers.map((driver) => Math.abs(Number(driver?.contribution) || 0)), 0);

  return (
    <div className="space-y-2 rounded-xl border border-border/70 bg-muted/25 p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{title}</p>
        {valueText ? <p className="text-xs font-semibold text-foreground">{valueText}</p> : null}
      </div>
      <div className="space-y-2">
        {drivers.slice(0, 4).map((driver) => (
          <DriverRow
            key={`${title}-${driver.feature_name}-${driver.direction}`}
            driver={driver}
            maxContribution={maxContribution}
          />
        ))}
      </div>
    </div>
  );
}

export function ExplainabilityPanel({
  explanation,
  drivers = [],
  sections = [],
  title = "Why The Model Said This",
  className = "",
}) {
  const hasSections = sections.some((section) => section?.drivers?.length);
  const hasDrivers = drivers?.length > 0;
  if (!explanation && !hasSections && !hasDrivers) return null;

  return (
    <div className={`space-y-3 rounded-xl border border-border/70 bg-gradient-to-br from-muted/35 via-background to-background p-4 ${className}`}>
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <BrainCircuit className="h-4 w-4" />
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground">{title}</p>
          <p className="text-xs text-muted-foreground">Feature-level reasoning from the trained model</p>
        </div>
      </div>

      {explanation ? (
        <div className="rounded-lg border border-primary/15 bg-primary/5 p-3">
          <p className="text-sm leading-relaxed text-foreground">{explanation}</p>
        </div>
      ) : null}

      {hasSections ? (
        <div className="space-y-3">
          {sections.map((section) => (
            <DriverSection
              key={section.title}
              title={section.title}
              valueText={section.valueText}
              drivers={section.drivers}
            />
          ))}
        </div>
      ) : null}

      {!hasSections && hasDrivers ? (
        <DriverSection title="Top Feature Drivers" drivers={drivers} />
      ) : null}
    </div>
  );
}
