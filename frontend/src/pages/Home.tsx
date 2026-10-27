import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Stamp as StampKind } from "../api";
import { Chip, Section, Stamp } from "../components/bits";
import { Cliff } from "../cliff/Cliff";
import { dicts, useI18n } from "../i18n";

const KINDS: StampKind[] = ["problem_found", "looks_right", "cannot_be_determined"];

export default function Home() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function sample() {
    setBusy(true);
    setErr("");
    try {
      const { id } = await api.sampleReport();
      nav(`/r/${id}`);
    } catch {
      setErr(t.report.error);
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <section className="hero">
        <div>
          <h1>{t.home.title}</h1>
          <p className="lede">{t.home.lede}</p>
          <div className="actions">
            <Link className="btn btn--primary" to="/check">
              {t.home.check}
            </Link>
            <button className="btn btn--quiet" type="button" onClick={sample} disabled={busy}>
              {busy ? t.home.sampleBusy : t.home.sample}
            </button>
          </div>
          {err ? <p className="alert alert--bad" role="alert">{err}</p> : null}
          <p className="fine">{t.home.fine}</p>
        </div>
        <Specimen />
      </section>

      <Section title={t.cliff.title} titleUr={dicts.ur.cliff.title} id="cliff">
        <p className="list muted cliff__intro">{t.cliff.intro}</p>
        <Cliff />
      </Section>

      <Section title={t.home.answersTitle} titleUr={dicts.ur.home.answersTitle} id="answers">
        <div className="answers">
          {KINDS.map((k) => (
            <div className="answer" key={k}>
              <div>
                <Stamp status={k} size="sm" />
              </div>
              <p>{t.home.answers[k]}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title={t.home.stepsTitle} titleUr={dicts.ur.home.stepsTitle} id="steps">
        <ol className="steps">
          {t.home.steps.map(([title, body]) => (
            <li key={title}>
              <div>
                <b>{title}</b>
                <span className="muted">{body}</span>
              </div>
            </li>
          ))}
        </ol>
      </Section>

      <Section title={t.home.proofTitle} titleUr={dicts.ur.home.proofTitle} id="proof">
        <ul className="proof">
          {t.home.proof.map(([claim, src]) => (
            <li key={claim}>
              <span>{claim}</span>
              <span className="src">{src}</span>
            </li>
          ))}
          <li>
            <Link to="/how">{t.home.proofMore}</Link>
          </li>
        </ul>
      </Section>
    </div>
  );
}

/** An excerpt of a real result on a synthetic sample bill, as SahiBill reported it (copied from the sample report). */
function Specimen() {
  const { t } = useI18n();
  const sp = t.report.specimen;
  return (
    <figure className="specimen" aria-label={sp.label}>
      <div className="specimen__head">
        <div>
          <p className="specimen__label">{sp.label}</p>
          <p className="specimen__title">{sp.headline}</p>
        </div>
        <Stamp status="problem_found" />
      </div>
      <div className="specimen__rows">
        {sp.rows.map(([k, title, line, clause]) => (
          <div className="specimen__row" key={title}>
            <span>
              <b>{title}</b>
              {line}
              <small>{clause}</small>
            </span>
            <Chip status={k} />
          </div>
        ))}
      </div>
    </figure>
  );
}
