import { useCallback, useEffect, useRef, useState } from "react";
import { api, type AgentAsk, type AgentState, type AgentStep } from "../api";
import { Chip } from "./bits";
import { useI18n } from "../i18n";

const POLL_MS = 600;

/**
 * The case agent at work. Every entry on screen is an event the server recorded as it happened: the model's
 * plan, each call it made (with its reasoning-token count and its own short note), each tool SahiBill ran and
 * what came back, the household's answers, and the grounding check on the summary. Nothing here is invented
 * for effect; motion only marks an event arriving or a step completing.
 */
export function Agent({ reportId, onChange }: { reportId: string; onChange: () => void }) {
  const { t, lang } = useI18n();
  const [st, setSt] = useState<AgentState | null>(null);
  const [busy, setBusy] = useState(false);
  const seen = useRef(0);

  const take = useCallback((s: AgentState) => {
    setSt(s);
    if (s.trace.length !== seen.current) {
      seen.current = s.trace.length;
      onChange();               // an answer or a re-check changed the report itself
    }
  }, [onChange]);

  useEffect(() => {
    api.agent(reportId).then(take).catch(() => setSt(null));
  }, [reportId, take]);

  useEffect(() => {
    if (st?.status !== "running") return;
    const timer = window.setTimeout(() => api.agent(reportId).then(take).catch(() => undefined), POLL_MS);
    return () => window.clearTimeout(timer);
  }, [st, reportId, take]);

  async function go(fn: () => Promise<AgentState>) {
    setBusy(true);
    try {
      take(await fn());
    } catch {
      setSt((s) => (s ? { ...s, status: "failed" } : s));
    } finally {
      setBusy(false);
    }
  }

  const status = st?.status || "idle";
  if (status === "idle") {
    return (
      <div className="agent agent--idle">
        <p className="agent__intro">{t.agent.intro}</p>
        <button className="btn btn--primary" type="button" disabled={busy}
          onClick={() => go(() => api.agentStart(reportId, lang))}>{t.agent.start}</button>
      </div>
    );
  }

  const trace = st?.trace || [];
  const running = status === "running";
  return (
    <div className={`agent agent--${status}`}>
      <div className="agent__head">
        <StatusPill status={status} since={lastEventTime(st)} />
        <span className="agent__model">{st?.model || "Muse Spark Open"}</span>
      </div>

      <div className="agent__grid">
        {st?.plan?.length ? <Plan plan={st.plan} trace={trace} status={status} /> : null}

        <div className="agent__log">
          <h3 className="agent__h">{t.agent.activity}</h3>
          <ol className="agent__events" aria-live="polite">
            {trace.map((s, i) => <Event key={i} step={s} />)}
            {running ? <Thinking /> : null}
          </ol>
        </div>
      </div>

      {status === "waiting" && st?.ask ? (
        <AskCard ask={st.ask} reportId={reportId} busy={busy} onAnswer={(v) => go(() => api.agentReply(reportId, v))} />
      ) : null}

      {status === "done" && st?.summary ? <Summary st={st} /> : null}

      {status === "paused" ? <p className="alert">{t.agent.paused}</p> : null}
      {status === "failed" ? <p className="alert alert--bad" role="alert">{t.agent.failed}</p> : null}

      <footer className="agent__foot">
        {st?.stats ? (
          <dl className="agent__stats">
            <div><dt>{t.agent.stats.calls}</dt><dd className="num">{st.stats.calls}</dd></div>
            <div><dt>{t.agent.stats.tokensIn}</dt><dd className="num">{st.stats.tokens_in.toLocaleString("en-US")}</dd></div>
            <div><dt>{t.agent.stats.tokensOut}</dt><dd className="num">{st.stats.tokens_out.toLocaleString("en-US")}</dd></div>
            <div><dt>{t.agent.stats.reasoning}</dt><dd className="num">{st.stats.reasoning_tokens.toLocaleString("en-US")}</dd></div>
            <div><dt>{t.agent.stats.cost}</dt><dd className="num">${(st.cost_usd || 0).toFixed(3)}</dd></div>
          </dl>
        ) : null}
        <p className="muted agent__footer">{t.agent.footer}</p>
        {status === "done" || status === "failed" || status === "paused" ? (
          <button className="btn btn--quiet btn--small" type="button" disabled={busy}
            onClick={() => go(() => api.agentStart(reportId, lang))}>{t.agent.again}</button>
        ) : null}
      </footer>
    </div>
  );
}

function lastEventTime(st: AgentState | null): number {
  return st?.started ? st.started * 1000 : Date.now();
}

function StatusPill({ status, since }: { status: AgentState["status"]; since: number }) {
  const { t } = useI18n();
  const label = status === "running" ? t.agent.statusRunning : status === "waiting" ? t.agent.waitingYou
    : status === "done" ? t.agent.statusDone : status === "paused" ? t.agent.paused : t.agent.failed;
  return (
    <span className={`agent__pill agent__pill--${status}`} role="status">
      <span className="agent__dot" aria-hidden="true" />
      {label}
      {status === "running" ? <Elapsed since={since} /> : null}
    </span>
  );
}

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(id);
  }, []);
  return <span className="num agent__elapsed">{Math.max(0, (now - since) / 1000).toFixed(1)} s</span>;
}

/** The model's own plan. An item ticks only when a step of its kind has really happened. */
function Plan({ plan, trace, status }: { plan: NonNullable<AgentState["plan"]>; trace: AgentStep[]; status: AgentState["status"] }) {
  const { t } = useI18n();
  const happened = (kind: string) => (kind === "finish" ? (status === "done" ? 1 : 0) : trace.filter((s) => s.kind === kind).length);
  const need: Record<string, number> = {};
  const done = plan.map((p) => {
    need[p.kind] = (need[p.kind] || 0) + 1;
    return happened(p.kind) >= need[p.kind];
  });
  const current = status === "running" || status === "waiting" ? done.indexOf(false) : -1;
  return (
    <div className="agent__plan">
      <h3 className="agent__h">{t.agent.plan}</h3>
      <ol>
        {plan.map((p, i) => (
          <li key={i} className={`agent__pitem${done[i] ? " is-done" : ""}${i === current ? " is-current" : ""}`}>
            <svg className="agent__tick" viewBox="0 0 20 20" aria-hidden="true">
              <circle cx="10" cy="10" r="8.5" />
              <path d="M5.8 10.4l2.7 2.7 5.7-6" />
            </svg>
            <span>{p.text}</span>
          </li>
        ))}
      </ol>
      <p className="muted agent__small">{t.agent.planNote}</p>
    </div>
  );
}

function Event({ step }: { step: AgentStep }) {
  const { t, lang } = useI18n();
  const text = lang === "ur" ? step.ur || step.en : step.en || step.ur;
  if (step.kind === "think") {
    return (
      <li className="agent__ev agent__ev--think">
        <span className="agent__evlabel">
          {t.agent.thought(step.reasoning_tokens || 0, step.seconds || 0)}
          {step.replayed ? <span className="agent__tag">{t.agent.recorded}</span> : null}
        </span>
        {step.note ? <q className="agent__note"><span className="visually-hidden">{t.agent.says} </span>{step.note}</q> : null}
      </li>
    );
  }
  return (
    <li className={`agent__ev agent__ev--${step.kind}`}>
      {step.tool ? (
        <span className="agent__evlabel">
          {t.agent.tool} <code className="agent__tool">{step.tool}</code>
          {step.args ? <span className="agent__args">{step.args}</span> : null}
        </span>
      ) : null}
      <span className="agent__evtext">{text}</span>
      {step.changes?.length ? (
        <ul className="agent__changes">
          {step.changes.map((c) => (
            <li key={c.title}><span>{lang === "ur" ? c.title_ur : c.title}</span><Chip status={c.status} /></li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function Thinking() {
  const { t } = useI18n();
  const [since] = useState(Date.now());
  return (
    <li className="agent__ev agent__ev--live" aria-label={t.agent.running}>
      <span className="agent__shimmer">{t.agent.thinking}</span>
      <Elapsed since={since} />
    </li>
  );
}

function Summary({ st }: { st: AgentState }) {
  const { t, lang } = useI18n();
  const s = st.summary!;
  const g = st.grounding;
  return (
    <div className="agent__summary">
      <h3 className="agent__h">{t.agent.done}</h3>
      <p lang={lang}>{s.text || (lang === "ur" ? s.ur : s.en)}</p>
      {g ? (
        <div className="agent__ground">
          <span className="agent__evlabel">{t.agent.grounding}</span>
          {g.ok ? (
            <>
              <ul className="agent__nums">
                {g.numbers.map((x, i) => (
                  <li key={x.n + i} style={{ animationDelay: `${0.15 + i * 0.12}s` }} className="num">{x.n}</li>
                ))}
              </ul>
              <p className="agent__small">{t.agent.groundingOk(g.numbers.length)}</p>
            </>
          ) : (
            <p className="agent__small">{t.agent.groundingRefused}</p>
          )}
        </div>
      ) : null}
      {st.trace.some((x) => x.kind === "letter") ? <a href="#letter" className="btn btn--quiet btn--small">{t.agent.seeLetter}</a> : null}
    </div>
  );
}

function AskCard({ ask, reportId, busy, onAnswer }: {
  ask: AgentAsk;
  reportId: string;
  busy: boolean;
  onAnswer: (value: string) => void;
}) {
  const { t, lang } = useI18n();
  const [v, setV] = useState("");
  const billId = ask.item_id.split(":")[0];
  return (
    <div className="agent__ask" role="group" aria-labelledby="agent-q">
      <p className="agent__label">{t.agent.waiting}: {lang === "ur" ? ask.month_ur : ask.month}</p>
      <p id="agent-q" className="agent__q" lang={lang}>{lang === "ur" ? ask.text_ur : ask.text}</p>
      {ask.reason ? <p className="agent__why"><span className="agent__says">{t.agent.says}</span> {ask.reason}</p> : null}

      <button className="btn btn--quiet btn--small agent__unsure" type="button" disabled={busy} onClick={() => onAnswer("unsure")}>{t.agent.unsure}</button>
      {ask.kind === "confirm" ? (
        <div className="actions">
          <button className="btn btn--primary btn--small" type="button" disabled={busy} onClick={() => onAnswer("present")}>{t.agent.yes}</button>
          <button className="btn btn--quiet btn--small" type="button" disabled={busy} onClick={() => onAnswer("absent")}>{t.agent.no}</button>
        </div>
      ) : null}

      {ask.kind === "date" ? (
        <form className="edit" onSubmit={(e) => { e.preventDefault(); if (v) onAnswer(v); }}>
          <input type="date" value={v} onChange={(e) => setV(e.target.value)} aria-labelledby="agent-q" />
          <button className="btn btn--primary btn--small" type="submit" disabled={busy || !v}>{t.agent.send}</button>
        </form>
      ) : null}

      {ask.kind === "meter" || ask.kind === "figure" ? (
        <>
          {ask.kind === "meter" ? (
            <img className="meter__img agent__meter" alt={t.agent.meterAlt}
              src={`/api/reports/${encodeURIComponent(reportId)}/bills/${encodeURIComponent(billId)}/meter`} />
          ) : (
            <div className="actions">
              {[ask.read_as, ask.adds_up_if].map((x) => x === undefined ? null : (
                <button key={String(x)} className="btn btn--quiet btn--small" type="button" disabled={busy}
                  onClick={() => onAnswer(String(x))}>{t.agent.readAs(String(x))}</button>
              ))}
            </div>
          )}
          <form className="edit" onSubmit={(e) => { e.preventDefault(); if (v.trim()) onAnswer(v.trim()); }}>
            <input inputMode="decimal" value={v} onChange={(e) => setV(e.target.value.replace(/[^0-9.]/g, ""))} aria-labelledby="agent-q" />
            <button className="btn btn--primary btn--small" type="submit" disabled={busy || !v}>{t.agent.send}</button>
          </form>
        </>
      ) : null}
    </div>
  );
}
