// The pieces of a report: check rows, questions, the reading table, the units chart and the letter.
import { useState } from "react";
import type { Bill, Card, Question, ReadingField, Report, Stamp as StampKind } from "../api";
import { monthName, useI18n } from "../i18n";
import { Chip } from "./bits";

const ORDER: Record<StampKind, number> = { problem_found: 0, cannot_be_determined: 1, looks_right: 2 };

export function CheckRows({ cards }: { cards: Card[] }) {
  const { t, lang } = useI18n();
  const [open, setOpen] = useState<string | null>(null);
  const sorted = [...cards].sort((a, b) => ORDER[a.status] - ORDER[b.status] || a.check.localeCompare(b.check));
  return (
    <ul className="rows">
      {sorted.map((c) => {
        const key = `${c.check}-${c.title}`;
        const isOpen = open === key;
        const lines = lang === "ur" && c.lines_ur?.length ? c.lines_ur : c.lines;
        return (
          <li key={key} className={`row row--${c.status}`}>
            <button type="button" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : key)}>
              <span className="row__title">{lang === "ur" ? c.title_ur || c.title : c.title}</span>
              <Chip status={c.status} />
              <span className="row__lines">
                {lines.map((l, i) => (
                  <p key={i}>{l}</p>
                ))}
              </span>
              {c.clauses.length ? <span className="row__hint">{isOpen ? t.report.hideRule : t.report.showRule}</span> : null}
            </button>
            {isOpen && c.clauses.length > 0 ? (
              <div className="row__more">
                <ul>
                  {c.clauses.map((cl) => (
                    <li key={cl}>{cl}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

export function Questions({ questions, onAnswer, busy }: {
  questions: Question[];
  onAnswer: (q: Question["id"], absent: boolean) => void;
  busy: boolean;
}) {
  const { t, lang } = useI18n();
  return (
    <div>
      {questions.map((q) => (
        <div className="question" key={q.id}>
          <p>{lang === "ur" ? q.ur : q.en}</p>
          <div className="actions">
            <button type="button" className="btn btn--quiet btn--small" disabled={busy} onClick={() => onAnswer(q.id, false)}>
              {t.report.yes}
            </button>
            <button type="button" className="btn btn--quiet btn--small" disabled={busy} onClick={() => onAnswer(q.id, true)}>
              {t.report.no}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function show(v: unknown, yes: string, no: string, lang: "en" | "ur" = "en"): string {
  if (v == null || v === "") return "";
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)) {
    const d = new Date(`${v}T00:00:00`);
    if (!Number.isNaN(d.getTime()))
      return d.toLocaleDateString(lang === "ur" ? "ur-PK" : "en-GB", { day: "numeric", month: "short", year: "numeric" });
  }
  if (typeof v === "string" && /^\d{4}-\d{2}$/.test(v)) return monthName(v, lang);
  if (typeof v === "boolean") return v ? yes : no;
  if (typeof v === "number") return v.toLocaleString("en-US", { maximumFractionDigits: 4 });
  return String(v);
}

export function ReadingTable({ fields, onCorrect, busy }: {
  fields: ReadingField[];
  onCorrect: (key: string, value: string) => void;
  busy: boolean;
}) {
  const { t, lang } = useI18n();
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const shown = fields.filter((f) => f.value != null || f.held);
  return (
    <div className="scroll">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">{t.report.field}</th>
            <th scope="col">{t.report.value}</th>
            <th scope="col">
              <span className="visually-hidden">{t.report.edit}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {shown.map((f) => (
            <tr key={f.key}>
              <td>{f.label}</td>
              <td className="v">
                {editing === f.key ? (
                  <form
                    className="edit"
                    onSubmit={(e) => {
                      e.preventDefault();
                      onCorrect(f.key, draft.trim());
                      setEditing(null);
                    }}
                  >
                    <input aria-label={f.label} value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus />
                    <button className="btn btn--primary btn--small" type="submit" disabled={busy || !draft.trim()}>
                      {t.report.save}
                    </button>
                    <button className="btn btn--quiet btn--small" type="button" onClick={() => setEditing(null)}>
                      {t.report.cancel}
                    </button>
                  </form>
                ) : (
                  <>
                    <span className="num">{f.value != null ? show(f.value, t.report.yesWord, t.report.noWord, lang) : t.report.notRead}</span>
                    {f.corrected ? <span className="tag">{t.report.corrected}</span> : null}
                    {f.held ? <span className="held">{lang === "ur" ? t.report.heldGeneric : t.report.held(f.held)}</span> : null}
                  </>
                )}
              </td>
              <td>
                {editing === f.key ? null : (
                  <button
                    type="button"
                    className="link-btn"
                    onClick={() => {
                      setEditing(f.key);
                      setDraft(f.value != null ? String(f.value) : "");
                    }}
                  >
                    {t.report.edit}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Units per month as horizontal bars, with the protected-status line. Plain HTML: reads at any width, both directions. */
export function UnitsChart({ household }: { household: Report["household"] }) {
  const { t, lang } = useI18n();
  const months = household.months.filter((m) => m.month);
  if (months.length === 0) return null;
  const line = household.protected_line || 200;
  const max = Math.max(line * 1.2, ...months.map((m) => m.units || 0)) || 1;
  const at = `${(line / max) * 100}%`;
  return (
    <div className="chart">
      <ol className="bars" aria-label={t.report.unitsTitle}>
        {months.map((m, i) => {
          const u = m.units;
          const kind = u == null ? "none" : u > line ? "over" : "";
          return (
            <li key={m.month}>
              <span className="bars__label">{monthName(m.month, lang)}</span>
              <span className="bars__track" aria-hidden="true">
                <span className={`bars__fill${kind ? ` bars__fill--${kind}` : ""}`}
                  style={{ display: "block", width: `${((u || 0) / max) * 100}%` }} />
                <span className="bars__line" style={{ insetInlineStart: at }}>
                  {i === 0 ? <span className="bars__line-label">{line}</span> : null}
                </span>
              </span>
              <span className="bars__value num">{u ?? "?"}</span>
            </li>
          );
        })}
      </ol>
      <p className="chart__note">{t.report.protectedNote(line)}</p>
    </div>
  );
}

export function Chain({ chain }: { chain: Report["household"]["chain"] }) {
  const { t } = useI18n();
  const allOk = chain.every((c) => c.ok);
  const [open, setOpen] = useState(!allOk);
  if (!chain.length) return null;
  return (
    <>
      {allOk ? (
        <p className="chain__all">
          <span className="chip chip--looks_right">{t.report.chainAll(chain.length + 1)}</span>{" "}
          <button type="button" className="link-btn" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? t.report.hideDetail : t.report.showDetail}
          </button>
        </p>
      ) : null}
      {open ? <ChainList chain={chain} /> : null}
    </>
  );
}

function ChainList({ chain }: { chain: Report["household"]["chain"] }) {
  const { t, lang } = useI18n();
  return (
    <ul className="chain">
      {chain.map((c) => {
        const from = monthName(c.from, lang);
        const to = monthName(c.to, lang);
        const n = /\((\d[\d,]*)\)/.exec(c.note || "")?.[1] || "";
        return (
          <li key={`${c.from}-${c.to}`}>
            <span className={`chip chip--${c.ok ? "looks_right" : "cannot_be_determined"}`}>
              {c.ok ? t.report.chainOk(from, to, n) : t.report.chainGap(from, to)}
            </span>
            {!c.ok && c.note ? <span className="muted"> {lang === "ur" ? c.note_ur || "" : c.note}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}

export function Letter({ complaint }: { complaint: NonNullable<Bill["complaint"]> }) {
  const { t, lang } = useI18n();
  const [tab, setTab] = useState<"en" | "ur">(lang);
  const [copied, setCopied] = useState(false);
  const text = tab === "ur" ? complaint.ur : complaint.en;
  return (
    <div>
      <div className="letter__tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "en"} onClick={() => setTab("en")}>
          English
        </button>
        <button type="button" role="tab" lang="ur" aria-selected={tab === "ur"} onClick={() => setTab("ur")}>
          اردو
        </button>
      </div>
      <pre className="letter__body" lang={tab} role="tabpanel">
        {text}
      </pre>
      <div className="letter__actions">
        <button
          type="button"
          className="btn btn--primary btn--small"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(text);
              setCopied(true);
              setTimeout(() => setCopied(false), 1800);
            } catch {
              /* clipboard blocked: the text stays selectable */
            }
          }}
        >
          {copied ? t.report.copied : t.report.copy}
        </button>
        <button type="button" className="btn btn--quiet btn--small" onClick={() => window.print()}>
          {t.report.print}
        </button>
      </div>
    </div>
  );
}
