// Typed client for the report API (contract: 10-PRODUCT-DESIGN.md). Every call returns data or throws an
// ApiError whose message is safe to show.

export type Stamp = "problem_found" | "looks_right" | "cannot_be_determined";

export interface Card {
  check: string;
  title: string;
  title_ur: string;
  status: Stamp;
  lines: string[];
  lines_ur?: string[];
  clauses: string[];
}

export interface ReadingField {
  key: string;
  label: string;
  value: unknown;
  text?: string | null;
  held?: string | null;
  corrected?: boolean;
  from_previous_bill?: boolean;
}

export interface Question {
  id: "snapshot" | "stamp" | "mco";
  en: string;
  ur: string;
}

export interface NextStep {
  en: string;
  ur: string;
  clause?: string;
  checks?: string[];
}

export interface Bill {
  id: string;
  photo_name?: string;
  status: "queued" | "reading" | "done" | "failed";
  error?: string | null;
  error_ur?: string | null;
  retake?: boolean;
  billing_month?: string | null;
  stamp?: Stamp;
  reading: ReadingField[];
  cards: Card[];
  questions: Question[];
  next_steps: { utility?: NextStep[]; retake?: NextStep[]; user?: NextStep[]; limit?: NextStep[] };
  complaint?: { en: string; ur: string; problem_count: number } | null;
  cost_usd?: number;
  photo_urls?: string[];
  headline?: { en: string; ur: string };
  counts?: { problem: number; cannot_be_determined: number; looks_right: number };
  photo_agreement?: { photos: number; disagreements: Record<string, unknown[]> } | null;
}

export interface Report {
  id: string;
  created: string;
  status: "reading" | "done" | "partial";
  headline: { en: string; ur: string; stamp: Stamp };
  bills: Bill[];
  household: {
    months: { month: string; units: number | null; status?: string | null; bill_id?: string | null }[];
    chain: { from: string; to: string; ok: boolean; note?: string; note_ur?: string }[];
    history?: { month: string; units: number | null; mode?: string }[];
    protected_line: number;
  };
  household_mode?: boolean;
  cost_usd?: number;
}

export type Spoken = "urdu" | "sindhi" | "pashto" | "saraiki" | "punjabi" | "english";

export interface Heard {
  text: string;
  language: Spoken;
  disagreement: number;
  sure: boolean;
}

export interface AgentStep {
  kind: "think" | "look" | "check" | "rule" | "ask" | "answer" | "letter" | "paused";
  en: string;
  ur: string;
  settle_by?: string;
  changes?: { title: string; title_ur: string; status: "problem_found" | "looks_right" | "cannot_be_determined" }[];
  tool?: string;
  args?: string;
  reasoning_tokens?: number;
  seconds?: number;
  note?: string | null;
  tools?: string[];
  replayed?: boolean;
}
export interface AgentAsk {
  item_id: string;
  kind: "confirm" | "date" | "figure" | "meter";
  text: string;
  text_ur: string;
  reason: string | null;
  month: string;
  month_ur: string;
  read_as?: number;
  adds_up_if?: number;
}
export interface AgentState {
  status: "idle" | "running" | "waiting" | "done" | "paused" | "failed";
  trace: AgentStep[];
  ask: AgentAsk | null;
  summary: { text?: string; en?: string; ur?: string; source: string } | null;
  plan?: { kind: "look" | "ask" | "check" | "letter" | "finish"; text: string }[];
  grounding?: { numbers: { n: string; ok: boolean }[]; ok: boolean; refused: number } | null;
  stats?: { calls: number; tokens_in: number; tokens_out: number; reasoning_tokens: number };
  cost_usd?: number;
  started?: number;
  model?: string;
}

export class ApiError extends Error {}

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiError("network");
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body.detail || body.error || "";
    } catch {
      /* not JSON */
    }
    throw new ApiError(detail || `http_${res.status}`);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  /** Upload with progress (0 to 1); fetch cannot report upload progress, so this uses XMLHttpRequest. */
  createReport(photos: File[], onProgress?: (share: number) => void) {
    const form = new FormData();
    photos.forEach((p) => form.append("photos", p, p.name));
    return new Promise<{ id: string }>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/reports");
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
      xhr.onerror = () => reject(new ApiError("network"));
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            reject(new ApiError("bad_response"));
          }
        } else {
          let detail = "";
          try {
            detail = JSON.parse(xhr.responseText).detail || "";
          } catch {
            /* not JSON */
          }
          reject(new ApiError(detail || `http_${xhr.status}`));
        }
      };
      xhr.send(form);
    });
  },
  sampleReport() {
    return call<{ id: string }>("/api/reports/sample", json({ set: "synthetic" }));
  },
  report(id: string) {
    return call<Report>(`/api/reports/${encodeURIComponent(id)}`);
  },
  answer(id: string, billId: string, question: Question["id"], absent: boolean) {
    return call<Report>(`/api/reports/${encodeURIComponent(id)}/bills/${encodeURIComponent(billId)}/answer`,
      json({ question, absent }));
  },
  hear(id: string, billId: string, audio: Blob, ext: string, language: Spoken) {
    const form = new FormData();
    form.append("audio", audio, `question.${ext}`);
    form.append("language", language);
    return call<Heard>(`/api/reports/${encodeURIComponent(id)}/bills/${encodeURIComponent(billId)}/hear`,
      { method: "POST", body: form });
  },
  ask(id: string, billId: string, question: string, language: Spoken) {
    return call<{ text: string; source: string }>(
      `/api/reports/${encodeURIComponent(id)}/bills/${encodeURIComponent(billId)}/ask`, json({ question, language }));
  },
  agent(id: string) {
    return call<AgentState>(`/api/reports/${encodeURIComponent(id)}/agent`);
  },
  agentStart(id: string, language: "en" | "ur") {
    return call<AgentState>(`/api/reports/${encodeURIComponent(id)}/agent`, json({ language }));
  },
  agentReply(id: string, value: string) {
    return call<AgentState>(`/api/reports/${encodeURIComponent(id)}/agent/reply`, json({ value }));
  },
  correct(id: string, billId: string, field: string, value: string) {
    return call<Report>(`/api/reports/${encodeURIComponent(id)}/bills/${encodeURIComponent(billId)}/correct`,
      json({ field, value }));
  },
};
