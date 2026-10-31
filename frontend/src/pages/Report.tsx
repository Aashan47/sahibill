import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError, type Bill, type NextStep, type Report as ReportT } from "../api";
import { Chip, Section, Stamp } from "../components/bits";
import { Ask } from "../components/Ask";
import { Agent } from "../components/Agent";
import { Cliff } from "../cliff/Cliff";
import { Chain, CheckRows, Letter, Questions, ReadingTable, UnitsChart } from "../components/report";
import { fieldName } from "../fields";
import { dicts, monthName, useI18n } from "../i18n";

const POLL_MS = 1500;

function formatDate(iso: string, lang: "en" | "ur"): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(lang === "ur" ? "ur-PK" : "en-GB", { day: "numeric", month: "long", year: "numeric" });
}

export default function Report() {
  const { id = "" } = useParams();
  const { t, lang } = useI18n();
  const [report, setReport] = useState<ReportT | null>(null);
  const [missing, setMissing] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const landed = useRef(false);

  const load = useCallback(async () => {
    try {
      const r = await api.report(id);
      setReport(r);
      return r;
    } catch (e) {
      if (e instanceof ApiError && e.message.includes("No such report")) setMissing(true);
      else setErr(t.report.error);
      return null;
    }
  }, [id, t.report.error]);

  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    const tick = async () => {
      const r = await load();
      if (alive && r && r.status === "reading") timer = window.setTimeout(tick, POLL_MS);
    };
    tick();
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [load]);

  const bills = useMemo(() => {
    const list = [...(report?.bills || [])];
    return list.sort((a, b) => (a.billing_month || "9999").localeCompare(b.billing_month || "9999"));
  }, [report]);

  useEffect(() => {
    if (!bills.length) return;
    if (selected && bills.some((b) => b.id === selected)) return;
    const firstProblem = bills.find((b) => b.stamp === "problem_found");
    setSelected((firstProblem || bills[bills.length - 1]).id);
  }, [bills, selected]);

  async function act(fn: () => Promise<ReportT>) {
    setBusy(true);
    setErr("");
    try {
      setReport(await fn());
    } catch {
      setErr(t.report.error);
    } finally {
      setBusy(false);
    }
  }

  if (missing) {
    return (
      <div className="page">
        <p className="alert alert--bad" role="alert">{t.report.notFound}</p>
      </div>
    );
  }
  if (!report) {
    return (
      <div className="page">
        <p className="pulse" aria-live="polite">{t.report.loading}</p>
        {err ? <p className="alert alert--bad" role="alert">{err}</p> : null}
      </div>
    );
  }

  const reading = report.status === "reading";
  const bill = bills.find((b) => b.id === selected) || bills[0];
  const land = !reading && !landed.current;
  if (land) landed.current = true;
  const history = report.household.history?.length ? report.household.history : report.household.months;

  return (
    <div className="page">
      <header className="verdict">
        <div>
          <h1 lang={lang}>{reading ? t.report.reading : lang === "ur" ? report.headline.ur : report.headline.en}</h1>
          <p className="meta">{t.report.created(formatDate(report.created, lang))}</p>
        </div>
        {reading ? <span className="pulse" aria-live="polite">{t.report.reading}</span> : <Stamp status={report.headline.stamp} land={land} />}
      </header>

      {err ? <p className="alert alert--bad" role="alert">{err}</p> : null}

      {!reading && bills.some((b) => b.status === "done") ? (
        <Section title={t.agent.title} titleUr={dicts.ur.agent.title} id="agent">
          <Agent reportId={report.id} onChange={load} />
        </Section>
      ) : null}

      {!reading && report.household_mode !== false && history.length > 1 ? (
        <Section title={t.report.unitsTitle} titleUr={dicts.ur.report.unitsTitle} id="units">
          <UnitsChart household={{ ...report.household, months: history.map((h) => ({ month: h.month, units: h.units })) }} />
          {report.household.chain.length ? <Chain chain={report.household.chain} /> : null}
        </Section>
      ) : null}

      {!reading && dailyOf(bills) ? (
        <Section title={t.cliff.title} titleUr={dicts.ur.cliff.title} id="cliff">
          <p className="list muted cliff__intro">{t.cliff.intro}</p>
          <Cliff daily={dailyOf(bills)!.daily} monthDays={dailyOf(bills)!.days} illustrative={false} />
        </Section>
      ) : null}

      <div className="report">
        <aside className="rail" aria-label={t.report.months}>
          <h2 className="bar">{t.report.months}</h2>
          <div className="panel">
            <ol>
              {bills.map((b) => (
                <li key={b.id}>
                  <button type="button" aria-current={b.id === bill?.id} onClick={() => setSelected(b.id)}>
                    <span className="month">{b.billing_month ? monthName(b.billing_month, lang) : b.photo_name || t.report.unknownMonth}</span>
                    {b.status === "done" && b.stamp ? <Chip status={b.stamp} /> : <span className="pulse">{t.report.statuses[b.status]}</span>}
                    <span className="sub num">{t.report.units(unitsOf(b))}</span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        </aside>

        <div>{bill ? <BillView report={report} bill={bill} busy={busy} act={act} /> : null}
        </div>
      </div>
    </div>
  );
}

function unitsOf(b: Bill): number | null {
  const f = b.reading?.find((r) => r.key === "units");
  return typeof f?.value === "number" ? f.value : null;
}

function BillView({ report, bill, busy, act }: {
  report: ReportT;
  bill: Bill;
  busy: boolean;
  act: (fn: () => Promise<ReportT>) => void;
}) {
  const { t, lang } = useI18n();
  if (bill.status === "queued" || bill.status === "reading") {
    return (
      <Section title={t.report.reading} titleUr={dicts.ur.report.reading} id="progress">
        <ul className="progress">
          {report.bills.map((b) => (
            <li key={b.id}>
              <span>{b.photo_name}</span>
              <span className={b.status === "done" ? "" : "pulse"}>{t.report.statuses[b.status]}</span>
            </li>
          ))}
        </ul>
      </Section>
    );
  }
  if (bill.status === "failed") {
    // The server's own reason (a retake request, a paused service), in the reader's language when it has one.
    const reason = (lang === "ur" ? bill.error_ur : bill.error) || t.report.failed;
    return (
      <div className="alert" role="alert">
        {bill.retake ? <p className="alert__title"><b>{t.report.retakeTitle}</b></p> : null}
        <p>{reason}</p>
      </div>
    );
  }

  const fields = bill.reading
    .map((f) => ({ ...f, label: fieldName(f.key, lang) || "" }))
    .filter((f) => f.label);
  const steps = bill.next_steps || {};
  const say = (s: NextStep) => (lang === "ur" ? s.ur : s.en);

  return (
    <>
      {bill.photo_urls?.length ? (
        <div className="photos">
          {bill.photo_urls.map((u, i) => (
            <a key={u} href={u} target="_blank" rel="noreferrer" className="photo">
              <img src={u} alt={t.report.photoAlt(i + 1)} loading="lazy" />
            </a>
          ))}
          <p className="muted">{t.report.photoNote}</p>
        </div>
      ) : null}

      {bill.questions.length ? (
        <Section title={t.report.questionsTitle} titleUr={dicts.ur.report.questionsTitle} id="questions">
          <Questions
            questions={bill.questions}
            busy={busy}
            onAnswer={(q, absent) => act(() => api.answer(report.id, bill.id, q, absent))}
          />
        </Section>
      ) : null}

      {needsMeter(bill) ? (
        <Section title={t.report.meterTitle} titleUr={dicts.ur.report.meterTitle} id="meter">
          <MeterRead src={`/api/reports/${encodeURIComponent(report.id)}/bills/${encodeURIComponent(bill.id)}/meter`} busy={busy}
            onSave={(n) => act(() => api.correct(report.id, bill.id, "snapshot_reading", n))} />
        </Section>
      ) : null}

      <Section title={t.ask.title} titleUr={dicts.ur.ask.title} id="ask">
        <Ask reportId={report.id} billId={bill.id} />
      </Section>

      <Section title={t.report.checksTitle} titleUr={dicts.ur.report.checksTitle} id="checks">
        <CheckRows cards={bill.cards} />
      </Section>

      {steps.retake?.length ? (
        <Section title={t.report.retakeTitle} titleUr={dicts.ur.report.retakeTitle} id="retake">
          <ul className="list">{steps.retake.map((s) => <li key={s.en}>{say(s)}</li>)}</ul>
        </Section>
      ) : null}

      <Section title={t.report.letterTitle} titleUr={dicts.ur.report.letterTitle} id="letter">
        {bill.complaint && bill.complaint.problem_count > 0 ? (
          <Letter complaint={bill.complaint} />
        ) : (
          <p className="list muted">{t.report.noLetter}</p>
        )}
      </Section>

      {steps.user?.length ? (
        <Section title={t.report.userTitle} titleUr={dicts.ur.report.userTitle} id="you">
          <ul className="list">
            {steps.user.map((s) => (
              <li key={s.en}>
                {say(s)}
                {s.checks?.includes("10B") ? (
                  <DeliveryDate busy={busy} onSave={(d) => act(() => api.correct(report.id, bill.id, "delivery_date", d))} />
                ) : null}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {steps.utility?.length ? (
        <Section title={t.report.requestTitle} titleUr={dicts.ur.report.requestTitle} id="records">
          <ul className="list">
            {steps.utility.map((s) => (
              <li key={s.en}>
                {say(s)}
                {s.clause ? <small>{s.clause}</small> : null}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      <Section title={t.report.readTitle} titleUr={dicts.ur.report.readTitle} id="read">
        <ReadingTable
          fields={fields}
          busy={busy}
          onCorrect={(key, value) => act(() => api.correct(report.id, bill.id, key, value))}
        />
      </Section>

      {steps.limit?.length ? (
        <Section title={t.report.limitTitle} titleUr={dicts.ur.report.limitTitle} id="limits">
          <ul className="list">{steps.limit.map((s) => <li key={s.en}>{say(s)}</li>)}</ul>
        </Section>
      ) : null}
    </>
  );
}

function DeliveryDate({ busy, onSave }: { busy: boolean; onSave: (iso: string) => void }) {
  const { t } = useI18n();
  const [d, setD] = useState("");
  return (
    <form className="edit delivery" onSubmit={(e) => { e.preventDefault(); if (d) onSave(d); }}>
      <label className="visually-hidden" htmlFor="delivery">{t.report.deliveryLabel}</label>
      <input id="delivery" type="date" value={d} onChange={(e) => setD(e.target.value)} />
      <button className="btn btn--primary btn--small" type="submit" disabled={busy || !d}>{t.report.deliverySave}</button>
    </form>
  );
}

/** The snapshot check could not run because the meter photo was not read (and the person has not typed it yet). */
function needsMeter(bill: Bill): boolean {
  const card = bill.cards.find((c) => c.check === "2");
  const typed = bill.reading.find((r) => r.key === "snapshot_reading")?.corrected;
  const blank = bill.reading.find((r) => r.key === "snapshot_state")?.value === "blank";
  return !typed && !blank && !!card && card.status === "cannot_be_determined";
}

function MeterRead({ src, busy, onSave }: { src: string; busy: boolean; onSave: (n: string) => void }) {
  const { t } = useI18n();
  const [found, setFound] = useState(true);
  const [n, setN] = useState("");
  return (
    <div className="meter">
      {found ? <img className="meter__img" src={src} alt={t.report.meterAlt} onError={() => setFound(false)} /> : null}
      <p>{found ? t.report.meterText : t.report.meterMissing}</p>
      <form className="edit" onSubmit={(e) => { e.preventDefault(); if (n.trim()) onSave(n.trim()); }}>
        <label className="meter__label" htmlFor="meter-n">{t.report.meterLabel}</label>
        <input id="meter-n" inputMode="numeric" pattern="[0-9]*" value={n}
          onChange={(e) => setN(e.target.value.replace(/[^0-9]/g, ""))} />
        <button className="btn btn--primary btn--small" type="submit" disabled={busy || !n}>{t.report.meterSave}</button>
      </form>
    </div>
  );
}

/** This household's average daily use from its latest read bill (units over the days in that month). */
function dailyOf(bills: Bill[]): { daily: number; days: number } | null {
  const b = [...bills].reverse().find((x) => x.status === "done" && x.billing_month && unitsOf(x));
  if (!b) return null;
  const [y, m] = b.billing_month!.split("-").map(Number);
  const days = new Date(y, m, 0).getDate();
  return { daily: Math.round((unitsOf(b)! / days) * 10) / 10, days };
}
