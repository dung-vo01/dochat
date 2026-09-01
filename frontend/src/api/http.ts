export async function extractErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // response wasn't JSON will fall through to the generic message
  }
  return `Request failed: ${res.status}`;
}
