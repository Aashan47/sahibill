// Ask about this bill: speak (or type) in Urdu, Sindhi, Pashto, Saraiki, Punjabi or English. What was heard is
// shown back to confirm whenever the two speech models disagree beyond the language's measured threshold.
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Heard, type Spoken } from "../api";
import { useI18n } from "../i18n";

const LANGS: { id: Spoken; label: string; lang: string }[] = [
  { id: "urdu", label: "اردو", lang: "ur" },
  { id: "sindhi", label: "سنڌي", lang: "sd" },
  { id: "pashto", label: "پښتو", lang: "ps" },
  { id: "saraiki", label: "سرائیکی", lang: "skr" },
  { id: "punjabi", label: "پنجابی", lang: "pnb" },
  { id: "english", label: "English", lang: "en" },
];
const MAX_SECONDS = 30;

export function Ask({ reportId, billId }: { reportId: string; billId: string }) {
  const { t, lang: uiLang } = useI18n();
  const [language, setLanguage] = useState<Spoken>(uiLang === "ur" ? "urdu" : "english");
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [heard, setHeard] = useState<Heard | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState<"" | "hearing" | "answering">("");
  const [answer, setAnswer] = useState<{ text: string; source: string } | null>(null);
  const [msg, setMsg] = useState("");
  const rec = useRef<MediaRecorder | null>(null);
  const timer = useRef<number>();
  const meta = LANGS.find((l) => l.id === language)!;

  useEffect(() => {
    fetch("/api/voice/warm", { method: "POST" }).catch(() => undefined);   // start loading the speech models now
  }, []);

  useEffect(() => () => {
    window.clearInterval(timer.current);
    rec.current?.stream.getTracks().forEach((tr) => tr.stop());
  }, []);

  async function start() {
    setMsg("");
    setAnswer(null);
    setHeard(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setMsg(t.ask.micBlocked);
      return;
    }
    const type = ["audio/webm", "audio/mp4", "audio/ogg"].find((m) => MediaRecorder.isTypeSupported?.(m)) || "";
    const r = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
    const chunks: Blob[] = [];
    r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    r.onstop = async () => {
      stream.getTracks().forEach((tr) => tr.stop());
      window.clearInterval(timer.current);
      setRecording(false);
      const blob = new Blob(chunks, { type: r.mimeType || type || "audio/webm" });
      const ext = (r.mimeType || type).includes("mp4") ? "m4a" : (r.mimeType || type).includes("ogg") ? "ogg" : "webm";
      await hear(blob, ext);
    };
    rec.current = r;
    r.start();
    setRecording(true);
    setSeconds(0);
    timer.current = window.setInterval(() => {
      setSeconds((s) => {
        if (s + 1 >= MAX_SECONDS) r.state === "recording" && r.stop();
        return s + 1;
      });
    }, 1000);
  }

  function stop() {
    if (rec.current?.state === "recording") rec.current.stop();
  }

  async function hear(blob: Blob, ext: string) {
    setBusy("hearing");
    try {
      const h = await api.hear(reportId, billId, blob, ext, language);
      setHeard(h);
      setDraft(h.text);
      if (h.sure && h.text.trim()) await ask(h.text);
    } catch (e) {
      setMsg(e instanceof ApiError && e.message.startsWith("Listening") ? t.ask.noListening : t.report.error);
    } finally {
      setBusy("");
    }
  }

  async function ask(question: string) {
    if (!question.trim()) return;
    setBusy("answering");
    setMsg("");
    try {
      const a = await api.ask(reportId, billId, question.trim(), language);
      setAnswer({ text: a.text, source: a.source });
    } catch {
      setMsg(t.report.error);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="ask">
      <div className="ask__langs" role="radiogroup" aria-label={t.ask.language}>
        {LANGS.map((l) => (
          <button key={l.id} type="button" role="radio" aria-checked={language === l.id} lang={l.lang}
            className={`ask__lang${l.lang === "en" ? "" : " ask__lang--rtl"}`} onClick={() => setLanguage(l.id)} disabled={recording}>
            {l.label}
          </button>
        ))}
      </div>

      <div className="ask__row">
        <button type="button" className={`mic${recording ? " mic--on" : ""}`} onClick={recording ? stop : start}
          disabled={!!busy} aria-pressed={recording}>
          <svg viewBox="0 0 24 24" aria-hidden="true" width="22" height="22">
            <rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" />
            <path d="M5 11a7 7 0 0 0 14 0M12 18v3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <span>{recording ? t.ask.stop(MAX_SECONDS - seconds) : t.ask.speak}</span>
        </button>
        <span className="muted">{t.ask.orType}</span>
      </div>

      {busy === "hearing" ? <p className="pulse" aria-live="polite">{t.ask.hearing}</p> : null}

      {heard && !heard.sure ? <p className="ask__unsure">{t.ask.unsure}</p> : null}
      {heard && heard.sure ? <p className="muted">{t.ask.heard}</p> : null}

      <form className="ask__form" onSubmit={(e) => { e.preventDefault(); ask(draft); }}>
        <label className="visually-hidden" htmlFor="ask-q">{t.ask.placeholder}</label>
        <textarea id="ask-q" rows={2} value={draft} lang={meta.lang} dir={meta.lang === "en" ? "ltr" : "rtl"}
          placeholder={t.ask.placeholder} onChange={(e) => setDraft(e.target.value)} maxLength={500} />
        <button className="btn btn--primary" type="submit" disabled={!draft.trim() || !!busy}>
          {heard && !heard.sure ? t.ask.confirm : t.ask.ask}
        </button>
      </form>

      {busy === "answering" ? <p className="pulse" aria-live="polite">{t.ask.answering}</p> : null}
      {msg ? <p className="alert" role="alert">{msg}</p> : null}

      {answer ? (
        <div className="answer-box" aria-live="polite">
          <p lang={meta.lang} dir={meta.lang === "en" ? "ltr" : "rtl"} className="answer-box__text">{answer.text}</p>
          <p className="muted answer-box__src">{answer.source === "findings" ? t.ask.fromFindings : t.ask.fromModel}</p>
        </div>
      ) : null}
    </div>
  );
}
