import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Section } from "../components/bits";
import { dicts, useI18n } from "../i18n";

const MAX_FILES = 12;
const MAX_BYTES = 12_000_000;

interface Picked {
  file: File;
  url: string;
}

export default function Check() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [picked, setPicked] = useState<Picked[]>([]);
  const [over, setOver] = useState(false);
  const [msg, setMsg] = useState("");
  const [sending, setSending] = useState(false);
  const [progress, setProgress] = useState(0);
  const choose = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);

  useEffect(() => () => picked.forEach((p) => URL.revokeObjectURL(p.url)), []); // eslint-disable-line react-hooks/exhaustive-deps

  function add(files: FileList | File[] | null) {
    if (!files) return;
    setMsg("");
    const next = [...picked];
    for (const f of Array.from(files)) {
      if (!f.type.startsWith("image/")) {
        setMsg(t.check.notImage);
        continue;
      }
      if (f.size > MAX_BYTES) {
        setMsg(t.check.tooBig);
        continue;
      }
      if (next.length >= MAX_FILES) {
        setMsg(t.check.tooMany);
        break;
      }
      next.push({ file: f, url: URL.createObjectURL(f) });
    }
    setPicked(next);
  }

  function remove(i: number) {
    URL.revokeObjectURL(picked[i].url);
    setPicked(picked.filter((_, j) => j !== i));
  }

  async function submit() {
    setSending(true);
    setMsg("");
    try {
      const { id } = await api.createReport(picked.map((p) => p.file), setProgress);
      nav(`/r/${id}`);
    } catch {
      setMsg(t.report.error);
      setSending(false);
    }
  }

  return (
    <div className="page">
      <h1>{t.check.title}</h1>
      <p className="lede">{t.check.lede}</p>

      <div
        className={`drop${over ? " drop--over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          add(e.dataTransfer.files);
        }}
      >
        <p className="drop__title">{t.check.drop}</p>
        <p className="muted">{t.check.or}</p>
        <div className="actions">
          <button type="button" className="btn btn--primary" onClick={() => choose.current?.click()}>
            {t.check.choose}
          </button>
          <button type="button" className="btn btn--quiet" onClick={() => camera.current?.click()}>
            {t.check.camera}
          </button>
        </div>
        <input ref={choose} type="file" accept="image/*" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
        <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
        <ul className="tips" aria-label={t.check.tipsTitle}>
          {t.check.tips.map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ul>
      </div>

      {msg ? <p className="alert" role="alert">{msg}</p> : null}

      {picked.length > 0 ? (
        <Section title={t.check.queued(picked.length)} titleUr={dicts.ur.check.queued(picked.length)} id="queue">
          <ul className="queue">
            {picked.map((p, i) => (
              <li key={p.url}>
                <img className="thumb" src={p.url} alt="" />
                <span>
                  <b>{p.file.name}</b>
                  <br />
                  <span className="muted num">{(p.file.size / 1_000_000).toFixed(1)} MB</span>
                </span>
                <button type="button" className="link-btn" onClick={() => remove(i)} disabled={sending}>
                  {t.check.remove}
                </button>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      <div className="actions">
        <button type="button" className="btn btn--primary" disabled={picked.length === 0 || sending} onClick={submit}>
          {sending ? t.check.sending : t.check.submit(Math.max(1, picked.length))}
        </button>
      </div>
      {sending ? (
        <div className="upload" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}
          aria-label={t.check.sending}>
          <span style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
      ) : null}
      <p className="fine">{t.check.privacy}</p>
    </div>
  );
}
