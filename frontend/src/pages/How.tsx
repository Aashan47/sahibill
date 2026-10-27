import { Section } from "../components/bits";
import { Cliff } from "../cliff/Cliff";
import { dicts, useI18n } from "../i18n";

type Outcome = "met" | "missed" | "partial";

// Every row is copied from build/sahibill/results/*.md (runs of 21 and 22 October 2026). Nothing is rounded up.
const EVAL: { test: [string, string]; target: [string, string]; result: [string, string]; outcome: Outcome }[] = [
  {
    test: ["E1 Reading synthetic bills (100 photos)", "E1 مصنوعی بل پڑھنا (100 تصاویر)"],
    target: ["97% of fields right on clean photos; 90% on hard photos", "صاف تصاویر پر 97٪ خانے درست؛ مشکل تصاویر پر 90٪"],
    result: ["100% clean; 99.8% phone photos; 52.9% hard photos", "صاف 100٪؛ فون تصاویر 99.8٪؛ مشکل تصاویر 52.9٪"],
    outcome: "partial",
  },
  {
    test: ["E2 Two readers with abstention", "E2 دو ماڈل، شک پر رک جانا"],
    target: ["At most 1% wrong among accepted fields, accepting at least 85%", "قبول شدہ میں زیادہ سے زیادہ 1٪ غلط، کم از کم 85٪ قبول"],
    result: ["85.5% accepted, 1.65% wrong; all wrong fields on hard photos. With the retake gate added afterwards: 0 wrong, 74.4% accepted", "85.5٪ قبول، 1.65٪ غلط؛ تمام غلط خانے مشکل تصاویر پر۔ بعد میں دوبارہ تصویر مانگنے کی جانچ کے ساتھ: کوئی غلط نہیں، 74.4٪ قبول"],
    outcome: "missed",
  },
  {
    test: ["E3 Finding seeded defects", "E3 جان بوجھ کر ڈالی گئی غلطیاں پکڑنا"],
    target: ["95% of defects found", "95٪ غلطیاں پکڑی جائیں"],
    result: ["76.9% on clean to phone photos; most misses traced to the test generator, fixed but not re-measured", "صاف سے فون تصاویر تک 76.9٪؛ زیادہ تر چوک ٹیسٹ بنانے والے کوڈ کی، درست کی گئی مگر دوبارہ ناپی نہیں گئی"],
    outcome: "missed",
  },
  {
    test: ["E4a Rules on 64 real NEPRA decisions", "E4a نیپرا کے 64 اصل فیصلوں پر قواعد"],
    target: ["Matches NEPRA's finding in 70%", "70٪ میں نیپرا کے فیصلے سے مطابقت"],
    result: ["47.6% (20 of 42, strict set); 46.5% after all 129 labels were re-read. Most misses are the rules lacking an input the decision does not state", "47.6٪ (42 میں سے 20)؛ تمام 129 لیبل دوبارہ پڑھنے کے بعد 46.5٪۔ زیادہ تر چوک وہاں جہاں فیصلے میں ضروری معلومات نہیں"],
    outcome: "missed",
  },
  {
    test: ["E4b The same, read from the page images", "E4b یہی، صفحات کی تصاویر سے پڑھ کر"],
    target: ["At least 55%", "کم از کم 55٪"],
    result: ["36.7% (11 of 30); 35.5% (11 of 31) after the re-read. Reading lost 1 decision and added 1, so the gap is the rules", "36.7٪ (30 میں سے 11)؛ دوبارہ پڑھنے کے بعد 35.5٪۔ پڑھائی سے ایک کم ایک زیادہ، فرق قواعد کا ہے"],
    outcome: "missed",
  },
  {
    test: ["E6 Numbers read from NEPRA decisions", "E6 نیپرا فیصلوں سے اعداد پڑھنا"],
    target: ["At least 85% right", "کم از کم 85٪ درست"],
    result: ["91.7% (154 of 168)", "91.7٪ (168 میں سے 154)"],
    outcome: "met",
  },
  {
    test: ["E7 Speech, Omnilingual ASR 7B", "E7 آواز، اومنی لنگوئل اے ایس آر 7B"],
    target: ["Character error within 3 points of Meta's published figure", "حروف کی غلطی میٹا کے شائع شدہ عدد سے 3 پوائنٹس کے اندر"],
    result: ["Urdu 4.91%, Sindhi 7.17%, Pashto 13.16% within; Saraiki 21.99% not within. Refusing unsure clips: Sindhi 4.77% on 79% of clips; Pashto and Saraiki mostly refused. Punjabi not run", "اردو 4.91٪، سندھی 7.17٪، پشتو 13.16٪ اندر؛ سرائیکی 21.99٪ باہر۔ غیر یقینی آوازیں رد کرنے سے سندھی 79٪ آوازوں پر 4.77٪؛ پشتو اور سرائیکی زیادہ تر رد۔ پنجابی نہیں چلایا گیا"],
    outcome: "partial",
  },
  {
    test: ["E8 Six real IESCO bills, 12 photos", "E8 آئیسکو کے چھ اصل بل، 12 تصاویر"],
    target: ["Descriptive: report what it reads", "صرف بیان: جو پڑھا وہ بتانا"],
    result: ["237 of 248 fields right; no false alarm after the fixes the test led to", "248 میں سے 237 خانے درست؛ جانچ کے بعد کی اصلاحات سے کوئی غلط الزام نہیں"],
    outcome: "met",
  },
];

export default function How() {
  const { t, lang } = useI18n();
  const i = lang === "ur" ? 1 : 0;
  const word: Record<Outcome, string> = { met: t.how.met, missed: t.how.missed, partial: t.how.partial };
  return (
    <div className="page">
      <div className="prose">
        <h1>{t.how.title}</h1>
        <p className="lede">{t.how.lede}</p>
      </div>

      <Section title={t.how.stepsTitle} titleUr={dicts.ur.how.stepsTitle} id="who">
        <div className="scroll">
          <table className="table">
            <thead>
              <tr>{t.how.cols.map((c) => <th scope="col" key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {t.how.rows.map(([step, who, note]) => (
                <tr key={step}>
                  <td><b>{step}</b></td>
                  <td>{who}</td>
                  <td className="muted">{note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title={t.cliff.title} titleUr={dicts.ur.cliff.title} id="cliff">
        <p className="list muted cliff__intro">{t.cliff.intro}</p>
        <Cliff />
      </Section>

      <Section title={t.how.evalTitle} titleUr={dicts.ur.how.evalTitle} id="eval">
        <div className="scroll">
          <table className="table">
            <thead>
              <tr>{t.how.evalCols.slice(0, 3).map((c) => <th scope="col" key={c}>{c}</th>)}<th scope="col"><span className="visually-hidden">{t.how.evalCols[2]}</span></th></tr>
            </thead>
            <tbody>
              {EVAL.map((r) => (
                <tr key={r.test[0]}>
                  <td><b>{r.test[i]}</b></td>
                  <td className="muted">{r.target[i]}</td>
                  <td>{r.result[i]}</td>
                  <td><span className={`result result--${r.outcome}`}>{word[r.outcome]}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="list muted">{t.how.note}</p>
      </Section>
    </div>
  );
}
