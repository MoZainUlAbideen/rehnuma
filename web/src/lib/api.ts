// Typed client for the Rehnuma API (FastAPI on Render). Shapes mirror src/rehnuma/api/views.py.

export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "https://rehnuma-api-3e5t.onrender.com"
).replace(/\/$/, "");

export type Lang = "ur" | "en";

export interface SampleCard {
  id: string;
  disco: string;
  month: string;
  connection_type: "conventional" | "net_metering";
  layout: string;
  payable: number;
}

export interface Finding {
  check: string;
  status: "PASS" | "FAIL" | "SKIP";
  message: string;
  expected: string | null;
  actual: string | null;
}

export interface BillView {
  bill: { bill_id: string; disco: string; bill_month: string; connection_type: string };
  audit: { passed: number; failed: number; skipped: number; findings: Finding[] };
  summary: Record<Lang, string[]>;
}

export interface UploadView extends BillView {
  bill_token: string;
  extraction: { verified: boolean; attempts: number; failed_checks: string[]; seconds: number };
}

export interface Citation {
  tag: string;
  label: string;
  document: string;
  clause: string;
  page: number;
  url: string;
  repealed: boolean;
  savings_for: string | null;
}

export interface AskReply {
  route: "bill" | "policy" | "both" | "needs_bill";
  lang: Lang;
  text: string;
  bill: { text: string; source: string } | null;
  policy: {
    status: string;
    text: string;
    citations: Citation[];
    sources_considered: string[];
  } | null;
  cached: boolean;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(0, "Could not reach the Rehnuma server. Check your connection and try again.");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  samples: () => call<SampleCard[]>("/api/samples"),
  sample: (id: string) => call<BillView>(`/api/samples/${encodeURIComponent(id)}`),
  ask: (body: { question: string; sample_id?: string; bill_token?: string; lang: Lang }) =>
    call<AskReply>("/api/ask", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }),
  extract: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return call<UploadView>("/api/bills/extract", { method: "POST", body: form });
  },
};
