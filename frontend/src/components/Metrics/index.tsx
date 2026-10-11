import { useCallback, useEffect, useState } from "react";
import styles from "./index.module.scss";
import { fetchMetricsSummary, fetchRecentTurns } from "@/api/metrics";
import type { MetricsSummary, RecentTurn } from "@/types";

const WINDOWS = [
  { hours: 24, label: "Last 24 hours" },
  { hours: 168, label: "Last 7 days" },
  { hours: 720, label: "Last 30 days" },
];

const REFRESH_MS = 15_000;

const ms = (n: number | null | undefined) =>
  n == null ? "–" : n >= 1000 ? `${(n / 1000).toFixed(1)} s` : `${Math.round(n)} ms`;

const pct = (n: number | null | undefined) =>
  n == null ? "–" : `${(n * 100).toFixed(n > 0 && n < 0.1 ? 1 : 0)}%`;

const num = (n: number | null | undefined) =>
  n == null ? "–" : Math.round(n).toLocaleString();

interface CardProps {
  label: string;
  value: string;
  hint?: string;
  tone?: "good" | "bad";
}

const Card = ({ label, value, hint, tone }: CardProps) => (
  <div className={`${styles.card} ${tone ? styles[tone] : ""}`}>
    <div className={styles.cardLabel}>{label}</div>
    <div className={styles.cardValue}>{value}</div>
    {hint && <div className={styles.cardHint}>{hint}</div>}
  </div>
);

const Metrics = () => {
  const [hours, setHours] = useState(24);
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [recent, setRecent] = useState<RecentTurn[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([
        fetchMetricsSummary(hours),
        fetchRecentTurns(),
      ]);
      setSummary(s);
      setRecent(r);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load metrics");
    }
  }, [hours]);

  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  const maxTurns = Math.max(1, ...(summary?.series.map((p) => p.turns) ?? []));

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>System health</h1>
          <p className={styles.subtitle}>
            How the assistant is behaving in production, per answered question.
            Refreshes every {REFRESH_MS / 1000}s.
          </p>
        </div>
        <select
          className={styles.select}
          value={hours}
          onChange={(e) => setHours(Number(e.target.value))}
        >
          {WINDOWS.map((w) => (
            <option key={w.hours} value={w.hours}>
              {w.label}
            </option>
          ))}
        </select>
      </header>

      {error && <div className={styles.error}>Could not load metrics: {error}</div>}

      {summary && (
        <>
          <section className={styles.grid}>
            <Card label="Questions answered" value={num(summary.turns)} />
            <Card
              label="Error rate"
              value={pct(summary.error_rate)}
              hint={`${pct(summary.cancelled_rate)} stopped by user`}
              tone={
                summary.error_rate == null
                  ? undefined
                  : summary.error_rate > 0.02
                    ? "bad"
                    : "good"
              }
            />
            <Card
              label="Latency p50 / p95"
              value={`${ms(summary.latency_ms.p50)} / ${ms(summary.latency_ms.p95)}`}
              hint="question sent to answer complete"
            />
            <Card
              label="First token p50 / p95"
              value={`${ms(summary.ttft_ms.p50)} / ${ms(summary.ttft_ms.p95)}`}
              hint="what the user feels as 'fast'"
            />
            <Card
              label="Tokens per answer"
              value={`${num(summary.avg_tokens.prompt)} in / ${num(summary.avg_tokens.completion)} out`}
              hint="average; drives cost"
            />
            <Card
              label="Nothing relevant found"
              value={pct(summary.no_match_rate)}
              hint="of questions in chats that have documents"
            />
            <Card
              label="Tool calls blocked"
              value={num(summary.tools_blocked)}
              hint="destructive action the user didn't ask for"
              tone={summary.tools_blocked > 0 ? "bad" : undefined}
            />
            <Card
              label="Corpus"
              value={`${num(summary.totals.documents)} docs`}
              hint={`${num(summary.totals.indexed_chunks)} chunks · ${num(summary.totals.conversations)} chats`}
            />
          </section>

          <section className={styles.panel}>
            <h2 className={styles.panelTitle}>
              Questions per {hours <= 48 ? "hour" : "day"}
            </h2>
            {summary.series.length === 0 ? (
              <p className={styles.muted}>No traffic in this window yet.</p>
            ) : (
              <div className={styles.bars}>
                {summary.series.map((p) => (
                  <div
                    key={p.bucket}
                    className={styles.barSlot}
                    title={`${new Date(p.bucket).toLocaleString()}\n${p.turns} questions · ${p.errors} errors · p50 ${ms(p.p50_latency_ms)}`}
                  >
                    <div
                      className={`${styles.bar} ${p.errors > 0 ? styles.barError : ""}`}
                      style={{ height: `${(p.turns / maxTurns) * 100}%` }}
                    />
                  </div>
                ))}
              </div>
            )}
          </section>

          {Object.keys(summary.tools).length > 0 && (
            <section className={styles.panel}>
              <h2 className={styles.panelTitle}>Tool usage</h2>
              <ul className={styles.tools}>
                {Object.entries(summary.tools).map(([name, count]) => (
                  <li key={name}>
                    <code>{name}</code> <span>{count}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className={styles.panel}>
            <h2 className={styles.panelTitle}>Recent questions</h2>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Status</th>
                    <th>Latency</th>
                    <th>First token</th>
                    <th>Chunks</th>
                    <th>Best match</th>
                    <th>Tool</th>
                    <th>Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.length === 0 && (
                    <tr>
                      <td colSpan={8} className={styles.muted}>
                        Nothing yet - ask a question in a chat.
                      </td>
                    </tr>
                  )}
                  {recent.map((t) => (
                    <tr key={t.id} title={t.error ?? undefined}>
                      <td>{new Date(t.created_at).toLocaleTimeString()}</td>
                      <td>
                        <span className={`${styles.badge} ${styles[t.status]}`}>
                          {t.status}
                        </span>
                      </td>
                      <td>{ms(t.latency_ms)}</td>
                      <td>{ms(t.ttft_ms)}</td>
                      <td>{t.used_chunks}</td>
                      <td>
                        {t.top_distance == null ? "–" : t.top_distance.toFixed(2)}
                      </td>
                      <td>
                        {t.tool ?? "–"}
                        {t.tool_blocked ? " (blocked)" : ""}
                      </td>
                      <td>{num(t.tokens)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
};

export default Metrics;
