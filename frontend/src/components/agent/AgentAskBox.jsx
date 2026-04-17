/**
 * AgentAskBox
 *
 * Free-form natural language question input for the autonomous agent.
 * Lives on the Invoice Detail page and Executive Dashboard.
 * Shows the reasoning trace after the agent answers.
 */

import { useEffect, useState } from "react";
import { Bot, Send, Loader2, Sparkles, Brain } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { AgentReasoningTrace } from "./AgentReasoningTrace";
import { api } from "@/lib/api";

const EXAMPLE_QUESTIONS = [
  "Should I escalate this invoice?",
  "What is the payment behavior of this customer?",
  "What collection action should I take next?",
  "Is this borrower a credit risk?",
];

export function AgentAskBox({ invoiceId, customerId }) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setQuestion("");
    setResult(null);
    setError(null);
    setLoading(false);
  }, [invoiceId, customerId]);

  async function handleAsk(q) {
    const text = q || question;
    if (!text.trim()) return;

    setLoading(true);
    setResult(null);
    setError(null);

    try {
      const data = await api.askAgent({
        question: text,
        invoice_id: invoiceId || null,
        customer_id: customerId ? String(customerId) : null,
      });
      setResult(data);
    } catch (err) {
      setError("Agent unavailable. Make sure your OpenAI API key is set in backend/.env");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-background to-primary/5">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-primary" />
          Ask the AI Agent
        </CardTitle>
        <CardDescription>
          Ask anything in plain English — the agent will call tools to answer autonomously
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Input row */}
        <div className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && handleAsk()}
            placeholder="e.g. Should I escalate this invoice?"
            className="flex-1 px-3 py-2 text-sm rounded-lg border border-border bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
            disabled={loading}
          />
          <button
            onClick={() => handleAsk()}
            disabled={loading || !question.trim()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <Send className="h-4 w-4" />
            }
            {loading ? "Thinking…" : "Ask"}
          </button>
        </div>

        {/* Example questions */}
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => { setQuestion(q); handleAsk(q); }}
              disabled={loading}
              className="text-xs px-2.5 py-1 rounded-full border border-border text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors disabled:opacity-40"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Thinking indicator */}
        {loading && (
          <div className="flex items-center gap-3 p-3 rounded-lg bg-primary/8 border border-primary/20">
            <div className="w-7 h-7 rounded-lg bg-primary/15 border border-primary/25 flex items-center justify-center shrink-0">
              <Brain className="h-3.5 w-3.5 text-primary animate-pulse" />
            </div>
            <div className="flex-1">
              <p className="text-xs font-medium text-primary">Agent is reasoning autonomously…</p>
              <p className="text-xs text-muted-foreground">Calling tools and analyzing data</p>
            </div>
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <div key={i} className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: `${i * 150}ms` }} />
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Agent answer */}
        {result && !loading && (
          <div className="space-y-3 pt-2">
            {/* Final answer */}
            <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                <span className="text-xs font-semibold text-primary">Agent Answer</span>
                <span className="text-xs text-muted-foreground ml-auto">
                  {result.iterations} iteration{result.iterations !== 1 ? "s" : ""} · {result.tools_called?.length || 0} tools
                </span>
              </div>
              <p className="text-sm text-foreground leading-relaxed">{result.answer}</p>
            </div>

            {/* Reasoning trace */}
            <AgentReasoningTrace
              trace={result.reasoning_trace}
              iterations={result.iterations}
              toolsCalled={result.tools_called}
              summary=""
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
