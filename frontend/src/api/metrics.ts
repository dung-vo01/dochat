import type { MetricsSummary, RecentTurn } from "@/types";
import { extractErrorDetail } from "@/api/http";

const BASE_URL = import.meta.env.VITE_API_URL;

export async function fetchMetricsSummary(
  hours: number,
): Promise<MetricsSummary> {
  const res = await fetch(`${BASE_URL}/api/metrics/summary?hours=${hours}`);
  if (!res.ok) throw new Error(await extractErrorDetail(res));
  return res.json();
}

export async function fetchRecentTurns(limit = 15): Promise<RecentTurn[]> {
  const res = await fetch(`${BASE_URL}/api/metrics/recent?limit=${limit}`);
  if (!res.ok) throw new Error(await extractErrorDetail(res));
  return res.json();
}
