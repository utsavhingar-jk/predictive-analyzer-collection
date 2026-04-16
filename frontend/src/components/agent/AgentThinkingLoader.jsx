/**
 * AgentThinkingLoader
 *
 * Animated UI shown while GPT-4o's ReAct loop is executing.
 * Shows a pulsing neural animation + rotating status messages.
 */

import { useEffect, useState } from "react";
import { Brain, Cpu, Search, GitMerge, Sparkles } from "lucide-react";

const STEPS = [
  { icon: Search,    text: "Reading invoice context and borrower history…" },
  { icon: Brain,     text: "Analyzing payment behavior patterns…" },
  { icon: Cpu,       text: "Running delay probability prediction…" },
  { icon: GitMerge,  text: "Optimizing collection strategy…" },
  { icon: Sparkles,  text: "Synthesizing GPT-4o business insights…" },
];

export function AgentThinkingLoader() {
  const [activeStep, setActiveStep] = useState(0);
  const [dots, setDots] = useState("");

  useEffect(() => {
    const stepTimer = setInterval(() => {
      setActiveStep((s) => (s + 1) % STEPS.length);
    }, 1800);
    const dotTimer = setInterval(() => {
      setDots((d) => (d.length >= 3 ? "" : d + "."));
    }, 400);
    return () => { clearInterval(stepTimer); clearInterval(dotTimer); };
  }, []);

  const ActiveIcon = STEPS[activeStep].icon;

  return (
    <div className="relative overflow-hidden rounded-xl border border-primary/30 bg-gradient-to-br from-background via-primary/5 to-background p-6">
      {/* Animated background pulse rings */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-64 h-64 rounded-full border border-primary/5 animate-ping" style={{ animationDuration: "3s" }} />
        <div className="absolute w-48 h-48 rounded-full border border-primary/8 animate-ping" style={{ animationDuration: "2.2s", animationDelay: "0.4s" }} />
        <div className="absolute w-32 h-32 rounded-full border border-primary/10 animate-ping" style={{ animationDuration: "1.8s", animationDelay: "0.8s" }} />
      </div>

      <div className="relative z-10">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="relative">
            <div className="w-10 h-10 rounded-xl bg-primary/15 border border-primary/30 flex items-center justify-center">
              <Brain className="h-5 w-5 text-primary animate-pulse" />
            </div>
            <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-green-500 border-2 border-background animate-pulse" />
          </div>
          <div>
            <p className="text-sm font-bold text-foreground">GPT-4o ReAct Loop</p>
            <p className="text-xs text-muted-foreground">Autonomous agent reasoning{dots}</p>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <span className="text-xs text-primary font-semibold bg-primary/10 px-2.5 py-1 rounded-full border border-primary/20">
              Running
            </span>
          </div>
        </div>

        {/* Step indicators */}
        <div className="space-y-2.5 mb-6">
          {STEPS.map((step, idx) => {
            const Icon = step.icon;
            const isDone = idx < activeStep;
            const isActive = idx === activeStep;
            return (
              <div
                key={idx}
                className={`flex items-center gap-3 p-2.5 rounded-lg transition-all duration-500 ${
                  isActive
                    ? "bg-primary/10 border border-primary/25"
                    : isDone
                    ? "opacity-50"
                    : "opacity-20"
                }`}
              >
                <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${
                  isDone ? "bg-green-500/20 text-green-500" :
                  isActive ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"
                }`}>
                  {isDone ? (
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    <Icon className={`w-3 h-3 ${isActive ? "animate-pulse" : ""}`} />
                  )}
                </div>
                <span className={`text-xs ${isActive ? "text-foreground font-medium" : "text-muted-foreground"}`}>
                  {step.text}
                </span>
                {isActive && (
                  <div className="ml-auto flex gap-0.5">
                    {[0, 1, 2].map((i) => (
                      <div
                        key={i}
                        className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce"
                        style={{ animationDelay: `${i * 150}ms` }}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Token stream simulation */}
        <div className="p-3 rounded-lg bg-muted/40 border border-border font-mono text-xs text-muted-foreground leading-relaxed">
          <span className="text-green-500 font-semibold">{'>'} </span>
          <span className="text-primary/80">tool_call:</span>
          <span className="text-foreground/60"> {STEPS[activeStep].text.toLowerCase().replace("…", "")}</span>
          <span className="inline-block w-1.5 h-3.5 bg-primary/60 ml-0.5 animate-pulse align-middle" />
        </div>
      </div>
    </div>
  );
}
