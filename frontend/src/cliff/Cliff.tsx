// "The 200-unit cliff": the 3D centrepiece. A late meter reading adds days of units to one bill; past 200 units
// a protected household is billed every unit at the unprotected rate. NEPRA's pro-rata rule brings it back.
import { useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { LIMIT, LOST_MONTHS, rateOfUnit, scenario, type Scenario } from "./model";
import { webglAvailable } from "./webgl";

const rs = (x: number) => x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function Cliff({ daily = 6, monthDays = 30, illustrative = true }: { daily?: number; monthDays?: number; illustrative?: boolean }) {
  const { t } = useI18n();
  const c = t.cliff;
  const [days, setDays] = useState(Math.max(28, Math.min(40, monthDays)));   // start on time; the jump comes from dragging
  const [proRata, setProRata] = useState(false);
  const s = useMemo(() => scenario(daily, days, monthDays, proRata), [daily, days, monthDays, proRata]);
  const onTime = useMemo(() => scenario(daily, monthDays, monthDays, false), [daily, monthDays]);
  const host = useRef<HTMLDivElement>(null);
  const scene = useRef<{ set: (st: { unitsRead: number; unitsBilled: number; status: "protected" | "unprotected" }) => void; dispose: () => void } | null>(null);
  const [mode, setMode] = useState<"loading" | "3d" | "flat">("loading");

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    if (!webglAvailable()) {
      setMode("flat");
      return;
    }
    let disposed = false;
    const io = new IntersectionObserver(async ([e]) => {
      if (!e.isIntersecting || scene.current) return;
      io.disconnect();
      try {
        const { CliffScene } = await import("./Scene3D");
        if (disposed) return;
        scene.current = new CliffScene(el, reduced);
        setMode("3d");
      } catch {
        setMode("flat");
      }
    }, { rootMargin: "200px" });
    io.observe(el);
    return () => {
      disposed = true;
      io.disconnect();
      scene.current?.dispose();
      scene.current = null;
    };
  }, []);

  useEffect(() => {
    scene.current?.set({ unitsRead: s.unitsRead, unitsBilled: s.unitsBilled, status: s.status });
  }, [s, mode]);

  return (
    <div className="cliff">
      <div className="cliff__stage">
        <div ref={host} className="cliff__canvas" hidden={mode === "flat"} />
        {mode === "flat" ? <FlatTower s={s} /> : null}
        <p className="cliff__legend">
          <span className="sw sw--p" />{c.legendProtected} <span className="sw sw--u" />{c.legendUnprotected} <span className="sw sw--l" />{c.legendLimit(LIMIT)}
        </p>
      </div>
      <div className="cliff__panel">
        <label className="cliff__label" htmlFor="cliff-days">{c.daysLabel(days)}</label>
        <input id="cliff-days" type="range" min={28} max={40} step={1} value={days} onChange={(e) => setDays(Number(e.target.value))}
          aria-valuetext={c.daysLabel(days)} />
        <div className="cliff__scale"><span>28</span><span>{c.monthLength(monthDays)}</span><span>40</span></div>

        <button type="button" className={`switch${proRata ? " switch--on" : ""}`} aria-pressed={proRata} onClick={() => setProRata(!proRata)}>
          <span className="switch__knob" aria-hidden="true" />
          <span>{c.proRata}</span>
        </button>

        <dl className="cliff__out" aria-live="polite">
          <div><dt>{c.unitsRead}</dt><dd className="num">{s.unitsRead}</dd></div>
          <div><dt>{c.unitsBilled}</dt><dd className="num">{s.unitsBilled}</dd></div>
          <div className="cliff__charge"><dt>{c.energy}</dt><dd className={`num${s.overLimit ? " is-over" : ""}`}>Rs {rs(s.energy)}</dd></div>
        </dl>
        {s.overLimit ? (
          <p className="cliff__lost">{c.lost(s.unitsBilled, LOST_MONTHS, rs(onTime.energy))}</p>
        ) : s.carried > 0 ? (
          <p className="cliff__saved">{c.carried(s.carried)}</p>
        ) : (
          <p className="cliff__ok">{c.ok(LIMIT)}</p>
        )}
        <p className="cliff__note">{illustrative ? c.noteIllustrative(daily, monthDays) : c.noteHousehold(daily, monthDays)}</p>
      </div>
    </div>
  );
}

/** The same tower in 2D, for reduced motion settings, no WebGL, and print. */
function FlatTower({ s }: { s: Scenario }) {
  const W = 400, H = 180, bars = 40, bw = W / bars;
  return (
    <svg className="cliff__flat" viewBox={`0 0 ${W} ${H + 20}`} role="img" aria-label={`${s.unitsBilled} units`}>
      {Array.from({ length: bars }, (_, i) => {
        const on = i * 10 + 1 <= s.unitsBilled;
        const h = on ? rateOfUnit(s.status, i * 10 + 1, s.unitsBilled) * 4.4 : 2;
        return <rect key={i} x={i * bw + 1} y={H - h} width={bw - 2} height={h} rx="1.5"
          fill={on ? (s.status === "protected" ? "var(--print)" : "var(--ochre)") : "var(--rule)"} />;
      })}
      <line x1={(LIMIT / 10) * bw} x2={(LIMIT / 10) * bw} y1={10} y2={H} stroke="var(--ink)" strokeDasharray="5 4" strokeWidth="1.5" />
      <text x={(LIMIT / 10) * bw + 4} y={20} fontSize="11" fontWeight="700" fill="var(--ink)">{LIMIT}</text>
    </svg>
  );
}
