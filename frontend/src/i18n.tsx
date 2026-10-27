// English and Urdu for every word on screen. Urdu sets the page right to left. The choice is remembered
// on this device only.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Stamp } from "./api";

export type Lang = "en" | "ur";

const en = {
  brand: "SahiBill",
  nav: { check: "Check a bill", how: "How it decides" },
  langLabel: "Language",
  footer: {
    built: "Built with Muse Spark Open, Meta's open model.",
    privacy: "Your photos are used only to check your bill. SahiBill copies out the billing figures, never names, addresses or account numbers.",
    rules: "Rules: NEPRA Consumer Service Manual (revised 26 November 2025) and the NEPRA tariff in force.",
  },
  stamp: {
    problem_found: "Problem found",
    looks_right: "Looks right",
    cannot_be_determined: "Can't tell yet",
  } as Record<Stamp, string>,
  home: {
    title: "Is this electricity bill right?",
    lede: "SahiBill reads your bill, checks it against NEPRA's own rules, and tells you what it found, with the rule and the numbers. When it is not sure, it asks you.",
    check: "Check a bill",
    sample: "Try a sample bill",
    sampleBusy: "Opening the sample…",
    fine: "Free to use. Works on a phone. English and Urdu.",
    specimenTitle: "What a result looks like",
    specimenNote: "Each check gives one of three answers, with the rule it used.",
    answersTitle: "Three answers, and never a guess",
    answers: {
      problem_found: "A rule was broken and the numbers show it. You get the clause and a complaint letter.",
      looks_right: "The check ran and the bill follows the rule.",
      cannot_be_determined: "Something the rule needs is not on the bill or not readable. SahiBill says exactly what, and who can supply it.",
    } as Record<Stamp, string>,
    stepsTitle: "How a check works",
    steps: [
      ["Photograph the bill", "One photo per month. Several months together let SahiBill check how they connect."],
      ["It reads every field", "Muse Spark Open, Meta's open model, transcribes the bill. It never calculates."],
      ["Code checks the rules", "Ten checks from NEPRA's Consumer Service Manual and tariff: billing period, protected status, the meter photo, fuel adjustment, charges, detection bills and more."],
      ["You get the answer, and the letter", "Findings in English and Urdu, questions where it is unsure, and a complaint addressed to your company's complaint cell."],
    ],
    proofTitle: "How well it works, including where it falls short",
    proof: [
      ["237 of 248 fields read right on 12 photos of six real IESCO bills.", "E8, 22 October 2026"],
      ["154 of 168 numbers read right from real NEPRA decision documents.", "E6, 22 October 2026"],
      ["Weakest result: on badly damaged photos, two readers together still accepted some wrong fields (1.65% of accepted fields). Those photos should be taken again.", "E2, 22 October 2026"],
    ],
    proofMore: "See every test and its result",
  },
  check: {
    title: "Check your bills",
    lede: "Add a photo of each bill. Add several months at once and SahiBill will also check how they connect.",
    drop: "Drop bill photos here",
    or: "or",
    choose: "Choose photos",
    camera: "Take a photo",
    tipsTitle: "For a clear reading",
    tips: ["Lay the bill flat, in daylight.", "Keep all four corners in the photo.", "One bill per photo. Up to 12 photos."],
    queued: (n: number) => (n === 1 ? "1 photo ready" : `${n} photos ready`),
    remove: "Remove",
    submit: (n: number) => (n === 1 ? "Check this bill" : `Check ${n} bills`),
    sending: "Sending…",
    tooMany: "Up to 12 photos at a time.",
    tooBig: "That photo is over 12 MB. Try a smaller one.",
    notImage: "That file is not a photo.",
    privacy: "Photos are kept on SahiBill's server for 30 days, then deleted. To be read, each photo is sent to the services that run SahiBill's open models. Nothing else is shared.",
  },
  report: {
    loading: "Opening the report…",
    notFound: "This report was not found. It may have expired.",
    reading: "Reading your bills",
    statuses: { queued: "Waiting", reading: "Reading", done: "Done", failed: "Could not read" },
    created: (d: string) => `Checked on ${d}`,
    months: "Months",
    unknownMonth: "Month not read",
    units: (u: number | null) => (u == null ? "units not read" : `${u} units`),
    questionsTitle: "A question for you",
    yes: "Yes, it is there",
    no: "No, it isn't",
    checksTitle: "What we checked",
    showRule: "Show the rule",
    hideRule: "Hide the rule",
    readTitle: "What we read from the photo",
    field: "Field",
    value: "Value",
    held: (why: string) => `Not used: ${why}`,
    notRead: "Not read",
    edit: "Correct",
    save: "Save",
    cancel: "Cancel",
    corrected: "corrected",
    unitsTitle: "Units, month by month",
    protectedNote: (n: number) => `The line marks ${n} units. A protected household must stay at or under it every month for six months.`,
    chainTitle: "Do the months connect?",
    letterTitle: "Your complaint letter",
    noLetter: "No complaint is needed for this bill.",
    copy: "Copy",
    copied: "Copied",
    print: "Print",
    requestTitle: "Records you can ask the company for",
    userTitle: "Something only you can tell us",
    deliveryLabel: "Date the bill reached you",
    meterTitle: "Read the meter for us",
    meterText: "This is the meter photo printed on your bill, found by SAM 3. We could not read it clearly. What number does the meter show? If it is unclear here, look at the paper bill.",
    meterMissing: "We could not find the meter photo in your picture. Look at the meter photo on the paper bill: what number does it show?",
    meterLabel: "Number on the meter",
    meterSave: "Check with this number",
    meterAlt: "The meter photo printed on the bill, enlarged",
    deliverySave: "Check the time to pay",
    photoAlt: (n: number) => `Photo ${n} of this bill`,
    photoNote: "The photo SahiBill read. Open it to compare with what we read below.",
    chainOk: (from: string, to: string, n: string) => `${to} starts where ${from} ended${n ? ` (${n})` : ""}.`,
    chainGap: (from: string, to: string) => `${to} does not start where ${from} ended.`,
    chainAll: (n: number) => `Each of the ${n} months starts where the month before ended.`,
    showDetail: "Show each month",
    hideDetail: "Hide",
    heldGeneric: "Not used: the photos or the bill's own totals do not agree.",
    yesWord: "yes",
    noWord: "no",
    specimen: {
      label: "From a sample bill (synthetic), as SahiBill reported it",
      headline: "1 problem found on this bill.",
      rows: [
        ["problem_found", "Detection bill units", "Even at the higher load factor the limit is 1,642.5 units; the bill charges 2,414.", "CSM 9.1.3, 9.2.3(b)"],
        ["looks_right", "Detection bill months", "3 months charged: within the limit.", "CSM 9.2.3(c)(i)"],
        ["cannot_be_determined", "Time to pay", "Needs: delivery date (not printed on bills).", "CSM 6.5"],
      ] as [Stamp, string, string, string][],
    },
    retakeTitle: "Please take this photo again",
    limitTitle: "What SahiBill cannot check yet",
    failed: "This photo could not be read. Take it again, flat and in daylight.",
    error: "Something went wrong. Please try again.",
    rotated: "The photo was turned upright before reading.",
  },
  how: {
    title: "How SahiBill decides",
    lede: "Models read and listen. Code decides every number. Every result below is from a real run, including the ones that missed.",
    stepsTitle: "Who does what",
    cols: ["Step", "Done by", "Notes"],
    rows: [
      ["Read the bill", "Muse Spark Open (Meta, open weights)", "Transcribes only; every number is parsed and checked in code."],
      ["Hold what does not add up", "SahiBill code", "Readings, dates and charges must agree with each other, or the field is held."],
      ["Check the rules", "SahiBill code", "Ten checks written from NEPRA's Consumer Service Manual and tariff, each with its clause."],
      ["Ask when unsure", "SahiBill code", "Anything that rests on a field being absent is asked before it is alleged."],
      ["Write the complaint", "SahiBill code", "Built only from the findings, with the response times and escalation route the manual sets."],
    ],
    evalTitle: "Tests and results",
    evalCols: ["Test", "Target", "Result", ""],
    met: "Met",
    missed: "Missed",
    partial: "Partly",
    note: "Targets were written down before each test ran. Missing one is reported as it is.",
  },
  ask: {
    title: "Ask about this bill",
    language: "Language of your question",
    speak: "Ask by voice",
    stop: (left: number) => `Stop (${left} s)`,
    orType: "or type it below",
    hearing: "Listening to your question…",
    heard: "We heard this. You can change it and ask again.",
    unsure: "We are not sure we heard you right. Is this what you said? Correct it if needed, then ask.",
    placeholder: "For example: Is my bill right? Why is it higher this month?",
    ask: "Ask",
    confirm: "Yes, ask this",
    answering: "Finding the answer in your bill's checks…",
    fromFindings: "Answered from this bill's checks.",
    fromModel: "Written by Muse Spark Open from this bill's checks; it may use no number they do not contain.",
    micBlocked: "The microphone is blocked. Allow it in your browser, or type the question.",
    noListening: "Listening is not available right now. Type the question instead.",
  },
  cliff: {
    title: "What a few days can do to a bill",
    intro: "Drag the slider to read the meter later. Past 200 units, a protected household is charged the unprotected rate on every unit, the first 200 included.",
    daysLabel: (d: number) => `Meter read after ${d} days`,
    monthLength: (m: number) => `${m}-day month`,
    proRata: "Apply NEPRA's pro-rata rule (CSM\u00a06.1.1.1)",
    unitsRead: "Units on the meter",
    unitsBilled: "Units on this bill",
    energy: "Energy charge",
    lost: (u: number, months: number, onTime: string) => `${u} units: every unit is now charged at the unprotected rate, and protected status is lost for the next ${months} months. Read on time, the same household pays Rs ${onTime}.`,
    carried: (n: number) => `${n} units are carried to next month under the pro-rata rule, so this bill stays protected.`,
    ok: (limit: number) => `At or under ${limit} units: protected rates apply.`,
    noteIllustrative: (d: number, m: number) => `Illustrative: a protected household using ${d} units a day in a ${m}-day month. Energy charge only, at NEPRA's tariff (S.R.O. 279(I)/2026).`,
    noteHousehold: (d: number, m: number) => `Your household: about ${d} units a day from your latest bill, in a ${m}-day month. Energy charge only, at NEPRA's tariff (S.R.O. 279(I)/2026).`,
    legendProtected: "Protected rate",
    legendUnprotected: "Unprotected rate",
    legendLimit: (l: number) => `${l} units`,
  },
};

type Dict = typeof en;

const ur: Dict = {
  brand: "صحیح بل",
  nav: { check: "بل چیک کریں", how: "یہ کیسے فیصلہ کرتا ہے" },
  langLabel: "زبان",
  footer: {
    built: "میٹا کے اوپن ماڈل میوز اسپارک اوپن سے بنایا گیا۔",
    privacy: "آپ کی تصاویر صرف آپ کا بل جانچنے کے لیے استعمال ہوتی ہیں۔ صحیح بل صرف بل کے اعداد نقل کرتا ہے، نام، پتہ یا اکاؤنٹ نمبر کبھی نہیں۔",
    rules: "قواعد: نیپرا کنزیومر سروس مینوئل (نظرثانی 26 نومبر 2025) اور نافذ نیپرا ٹیرف۔",
  },
  stamp: {
    problem_found: "مسئلہ ملا",
    looks_right: "درست لگتا ہے",
    cannot_be_determined: "ابھی نہیں کہہ سکتے",
  },
  home: {
    title: "کیا یہ بجلی کا بل درست ہے؟",
    lede: "صحیح بل آپ کا بل پڑھتا ہے، اسے نیپرا کے اپنے قواعد سے جانچتا ہے، اور قاعدے اور اعداد کے ساتھ بتاتا ہے کہ کیا ملا۔ جب یقین نہ ہو تو آپ سے پوچھتا ہے۔",
    check: "بل چیک کریں",
    sample: "نمونے کا بل دیکھیں",
    sampleBusy: "نمونہ کھل رہا ہے…",
    fine: "مفت۔ فون پر چلتا ہے۔ اردو اور انگریزی۔",
    specimenTitle: "نتیجہ کیسا دکھتا ہے",
    specimenNote: "ہر جانچ تین میں سے ایک جواب دیتی ہے، اور بتاتی ہے کہ کون سا قاعدہ لگا۔",
    answersTitle: "تین جواب، اور کبھی اندازہ نہیں",
    answers: {
      problem_found: "کوئی قاعدہ ٹوٹا اور اعداد یہ دکھاتے ہیں۔ آپ کو شق اور شکایت کا خط ملتا ہے۔",
      looks_right: "جانچ ہوئی اور بل قاعدے کے مطابق ہے۔",
      cannot_be_determined: "قاعدے کو جو چاہیے وہ بل پر نہیں یا پڑھا نہیں جا سکا۔ صحیح بل بتاتا ہے کہ کیا، اور کون فراہم کر سکتا ہے۔",
    },
    stepsTitle: "جانچ کیسے ہوتی ہے",
    steps: [
      ["بل کی تصویر لیں", "ہر مہینے کی ایک تصویر۔ کئی مہینے اکٹھے ہوں تو صحیح بل ان کا آپس میں ربط بھی جانچتا ہے۔"],
      ["ہر خانہ پڑھا جاتا ہے", "میٹا کا اوپن ماڈل میوز اسپارک اوپن بل نقل کرتا ہے۔ وہ کوئی حساب نہیں کرتا۔"],
      ["کوڈ قواعد جانچتا ہے", "نیپرا کے کنزیومر سروس مینوئل اور ٹیرف سے دس جانچیں: بلنگ کی مدت، پروٹیکٹڈ حیثیت، میٹر کی تصویر، فیول ایڈجسٹمنٹ، چارجز، ڈیٹیکشن بل اور مزید۔"],
      ["جواب اور خط آپ کو ملتا ہے", "اردو اور انگریزی میں نتائج، جہاں یقین نہ ہو وہاں سوال، اور آپ کی کمپنی کے شکایت سیل کے نام خط۔"],
    ],
    proofTitle: "یہ کتنا درست ہے، اور کہاں کمزور ہے",
    proof: [
      ["آئیسکو کے چھ اصل بلوں کی 12 تصاویر پر 248 میں سے 237 خانے درست پڑھے گئے۔", "E8، 22 اکتوبر 2026"],
      ["نیپرا کے اصل فیصلوں سے 168 میں سے 154 اعداد درست پڑھے گئے۔", "E6، 22 اکتوبر 2026"],
      ["سب سے کمزور نتیجہ: بہت خراب تصاویر پر دو ماڈل مل کر بھی کچھ غلط خانے قبول کر گئے (قبول شدہ کا 1.65٪)۔ ایسی تصاویر دوبارہ لینی چاہئیں۔", "E2، 22 اکتوبر 2026"],
    ],
    proofMore: "تمام جانچیں اور ان کے نتائج دیکھیں",
  },
  check: {
    title: "اپنے بل چیک کریں",
    lede: "ہر بل کی ایک تصویر شامل کریں۔ کئی مہینے اکٹھے شامل کریں تو صحیح بل ان کا آپس میں ربط بھی جانچے گا۔",
    drop: "بل کی تصاویر یہاں چھوڑیں",
    or: "یا",
    choose: "تصاویر منتخب کریں",
    camera: "تصویر لیں",
    tipsTitle: "صاف پڑھائی کے لیے",
    tips: ["بل کو دن کی روشنی میں سیدھا رکھیں۔", "چاروں کونے تصویر میں ہوں۔", "ہر تصویر میں ایک بل۔ زیادہ سے زیادہ 12 تصاویر۔"],
    queued: (n: number) => `${n} تصاویر تیار`,
    remove: "ہٹائیں",
    submit: (n: number) => (n === 1 ? "یہ بل چیک کریں" : `${n} بل چیک کریں`),
    sending: "بھیجا جا رہا ہے…",
    tooMany: "ایک وقت میں زیادہ سے زیادہ 12 تصاویر۔",
    tooBig: "یہ تصویر 12 ایم بی سے بڑی ہے۔ چھوٹی تصویر آزمائیں۔",
    notImage: "یہ فائل تصویر نہیں ہے۔",
    privacy: "تصاویر 30 دن صحیح بل کے سرور پر رہتی ہیں، پھر مٹا دی جاتی ہیں۔ پڑھنے کے لیے ہر تصویر ان سروسز کو بھیجی جاتی ہے جن پر صحیح بل کے اوپن ماڈل چلتے ہیں۔ اس کے علاوہ کچھ شیئر نہیں ہوتا۔",
  },
  report: {
    loading: "رپورٹ کھل رہی ہے…",
    notFound: "یہ رپورٹ نہیں ملی۔ شاید اس کی مدت ختم ہو گئی ہو۔",
    reading: "آپ کے بل پڑھے جا رہے ہیں",
    statuses: { queued: "انتظار", reading: "پڑھا جا رہا ہے", done: "مکمل", failed: "پڑھا نہیں جا سکا" },
    created: (d: string) => `${d} کو جانچا گیا`,
    months: "مہینے",
    unknownMonth: "مہینہ نہیں پڑھا گیا",
    units: (u: number | null) => (u == null ? "یونٹس نہیں پڑھے گئے" : `${u} یونٹس`),
    questionsTitle: "آپ سے ایک سوال",
    yes: "ہاں، موجود ہے",
    no: "نہیں، موجود نہیں",
    checksTitle: "ہم نے کیا جانچا",
    showRule: "قاعدہ دکھائیں",
    hideRule: "قاعدہ چھپائیں",
    readTitle: "تصویر سے ہم نے کیا پڑھا",
    field: "خانہ",
    value: "قدر",
    held: (why: string) => `استعمال نہیں ہوا: ${why}`,
    notRead: "نہیں پڑھا گیا",
    edit: "درست کریں",
    save: "محفوظ کریں",
    cancel: "منسوخ",
    corrected: "درست کیا گیا",
    unitsTitle: "ماہ بہ ماہ یونٹس",
    protectedNote: (n: number) => `لکیر ${n} یونٹس پر ہے۔ پروٹیکٹڈ صارف کو چھ ماہ تک ہر مہینے اس سے کم یا برابر رہنا ہوتا ہے۔`,
    chainTitle: "کیا مہینے آپس میں جڑتے ہیں؟",
    letterTitle: "آپ کا شکایت کا خط",
    noLetter: "اس بل کے لیے شکایت کی ضرورت نہیں۔",
    copy: "کاپی کریں",
    copied: "کاپی ہو گیا",
    print: "پرنٹ کریں",
    requestTitle: "کمپنی سے آپ یہ ریکارڈ مانگ سکتے ہیں",
    userTitle: "یہ صرف آپ بتا سکتے ہیں",
    deliveryLabel: "بل آپ کو کس تاریخ کو ملا",
    meterTitle: "میٹر کی ریڈنگ ہمیں بتائیں",
    meterText: "یہ آپ کے بل پر چھپی میٹر کی تصویر ہے، جو SAM 3 نے ڈھونڈی۔ ہم اسے صاف نہیں پڑھ سکے۔ میٹر پر کون سا نمبر ہے؟ اگر یہاں صاف نہ ہو تو کاغذی بل پر دیکھیں۔",
    meterMissing: "آپ کی تصویر میں میٹر کی تصویر نہیں ملی۔ کاغذی بل پر میٹر کی تصویر دیکھیں: اس پر کون سا نمبر ہے؟",
    meterLabel: "میٹر پر نمبر",
    meterSave: "اس نمبر سے جانچیں",
    meterAlt: "بل پر چھپی میٹر کی تصویر، بڑی کر کے",
    deliverySave: "ادائیگی کا وقت جانچیں",
    photoAlt: (n: number) => `اس بل کی تصویر ${n}`,
    photoNote: "وہ تصویر جو صحیح بل نے پڑھی۔ کھول کر نیچے پڑھی گئی معلومات سے ملا لیں۔",
    chainOk: (from: string, to: string, n: string) => `${to} وہیں سے شروع ہوتا ہے جہاں ${from} ختم ہوا${n ? ` (${n})` : ""}۔`,
    chainGap: (from: string, to: string) => `${to} وہاں سے شروع نہیں ہوتا جہاں ${from} ختم ہوا۔`,
    chainAll: (n: number) => `${n} میں سے ہر مہینہ وہیں سے شروع ہوتا ہے جہاں پچھلا مہینہ ختم ہوا۔`,
    showDetail: "ہر مہینہ دکھائیں",
    hideDetail: "چھپائیں",
    heldGeneric: "استعمال نہیں ہوا: تصاویر یا بل کے اپنے مجموعے آپس میں نہیں ملتے۔",
    yesWord: "ہاں",
    noWord: "نہیں",
    specimen: {
      label: "نمونے کے بل (مصنوعی) سے، جیسا صحیح بل نے بتایا",
      headline: "اس بل میں 1 مسئلہ ملا۔",
      rows: [
        ["problem_found", "ڈیٹیکشن بل کے یونٹس", "زیادہ لوڈ فیکٹر پر بھی حد 1,642.5 یونٹس ہے؛ بل میں 2,414 یونٹس لگائے گئے۔", "CSM 9.1.3, 9.2.3(b)"],
        ["looks_right", "ڈیٹیکشن بل کے مہینے", "3 مہینوں کا بل: حد کے اندر۔", "CSM 9.2.3(c)(i)"],
        ["cannot_be_determined", "ادائیگی کا وقت", "ابھی طے نہیں ہو سکا۔ یہ بل آپ کو کس تاریخ کو ملا؟", "CSM 6.5"],
      ] as [Stamp, string, string, string][],
    },
    retakeTitle: "براہ کرم یہ تصویر دوبارہ لیں",
    limitTitle: "صحیح بل ابھی کیا نہیں جانچ سکتا",
    failed: "یہ تصویر پڑھی نہیں جا سکی۔ دن کی روشنی میں سیدھا رکھ کر دوبارہ لیں۔",
    error: "کچھ غلط ہو گیا۔ دوبارہ کوشش کریں۔",
    rotated: "پڑھنے سے پہلے تصویر سیدھی کی گئی۔",
  },
  how: {
    title: "صحیح بل کیسے فیصلہ کرتا ہے",
    lede: "ماڈل پڑھتے اور سنتے ہیں۔ ہر عدد کا فیصلہ کوڈ کرتا ہے۔ نیچے ہر نتیجہ اصل جانچ سے ہے، ناکام ہونے والے بھی۔",
    stepsTitle: "کون کیا کرتا ہے",
    cols: ["مرحلہ", "کون", "تفصیل"],
    rows: [
      ["بل پڑھنا", "میوز اسپارک اوپن (میٹا، اوپن ویٹس)", "صرف نقل کرتا ہے؛ ہر عدد کوڈ میں پڑھا اور جانچا جاتا ہے۔"],
      ["جو نہ ملے اسے روکنا", "صحیح بل کوڈ", "ریڈنگز، تاریخیں اور چارجز آپس میں ملنے چاہئیں، ورنہ خانہ روک لیا جاتا ہے۔"],
      ["قواعد جانچنا", "صحیح بل کوڈ", "نیپرا کے مینوئل اور ٹیرف سے لکھی دس جانچیں، ہر ایک اپنی شق کے ساتھ۔"],
      ["شک ہو تو پوچھنا", "صحیح بل کوڈ", "جو بات کسی خانے کے نہ ہونے پر ٹکی ہو، الزام سے پہلے پوچھی جاتی ہے۔"],
      ["شکایت لکھنا", "صحیح بل کوڈ", "صرف نتائج سے، مینوئل کی مقررہ مدت اور آگے جانے کے راستے کے ساتھ۔"],
    ],
    evalTitle: "جانچیں اور نتائج",
    evalCols: ["جانچ", "ہدف", "نتیجہ", ""],
    met: "پورا ہوا",
    missed: "پورا نہیں ہوا",
    partial: "جزوی",
    note: "ہر ہدف جانچ سے پہلے لکھا گیا تھا۔ جو پورا نہ ہوا وہ ویسے ہی بتایا گیا ہے۔",
  },
  ask: {
    title: "اس بل کے بارے میں پوچھیں",
    language: "سوال کی زبان",
    speak: "بول کر پوچھیں",
    stop: (left: number) => `روکیں (${left} سیکنڈ)`,
    orType: "یا نیچے لکھیں",
    hearing: "آپ کا سوال سنا جا رہا ہے…",
    heard: "ہم نے یہ سنا۔ آپ اسے بدل کر دوبارہ پوچھ سکتے ہیں۔",
    unsure: "ہمیں یقین نہیں کہ ہم نے ٹھیک سنا۔ کیا آپ نے یہی کہا؟ ضرورت ہو تو درست کریں، پھر پوچھیں۔",
    placeholder: "مثلاً: کیا میرا بل درست ہے؟ اس مہینے بل زیادہ کیوں ہے؟",
    ask: "پوچھیں",
    confirm: "ہاں، یہی پوچھیں",
    answering: "آپ کے بل کی جانچ سے جواب تلاش کیا جا رہا ہے…",
    fromFindings: "یہ جواب اس بل کی جانچ سے دیا گیا۔",
    fromModel: "میوز اسپارک اوپن نے اس بل کی جانچ سے لکھا؛ اس میں جانچ سے باہر کوئی عدد نہیں ہو سکتا۔",
    micBlocked: "مائیکروفون بند ہے۔ براؤزر میں اجازت دیں، یا سوال لکھیں۔",
    noListening: "ابھی سننا ممکن نہیں۔ سوال لکھ دیں۔",
  },
  cliff: {
    title: "چند دن بل کا کیا حال کر سکتے ہیں",
    intro: "سلائیڈر کھینچ کر میٹر دیر سے پڑھیں۔ 200 یونٹس سے اوپر پروٹیکٹڈ صارف سے ہر یونٹ کا ریٹ غیر پروٹیکٹڈ لیا جاتا ہے، پہلے 200 یونٹس سمیت۔",
    daysLabel: (d: number) => `میٹر ${d} دن بعد پڑھا گیا`,
    monthLength: (m: number) => `${m} دن کا مہینہ`,
    proRata: "نیپرا کا پرو ریٹا قاعدہ لگائیں \u2066(CSM\u00a06.1.1.1)\u2069",
    unitsRead: "میٹر پر یونٹس",
    unitsBilled: "اس بل کے یونٹس",
    energy: "توانائی چارجز",
    lost: (u: number, months: number, onTime: string) => `${u} یونٹس: اب ہر یونٹ غیر پروٹیکٹڈ ریٹ پر ہے، اور اگلے ${months} مہینوں کے لیے پروٹیکٹڈ حیثیت ختم۔ وقت پر پڑھا جاتا تو یہی گھر ${onTime} روپے دیتا۔`,
    carried: (n: number) => `پرو ریٹا قاعدے کے تحت ${n} یونٹس اگلے مہینے منتقل ہوتے ہیں، اس لیے یہ بل پروٹیکٹڈ رہتا ہے۔`,
    ok: (limit: number) => `${limit} یونٹس یا کم: پروٹیکٹڈ ریٹ لاگو۔`,
    noteIllustrative: (d: number, m: number) => `مثال: ${m} دن کے مہینے میں روزانہ ${d} یونٹس استعمال کرنے والا پروٹیکٹڈ گھر۔ صرف توانائی چارجز، نیپرا ٹیرف کے مطابق \u2066(S.R.O. 279(I)/2026)\u2069۔`,
    noteHousehold: (d: number, m: number) => `آپ کا گھر: آپ کے تازہ بل کے مطابق روزانہ تقریباً ${d} یونٹس، ${m} دن کا مہینہ۔ صرف توانائی چارجز، نیپرا ٹیرف کے مطابق \u2066(S.R.O. 279(I)/2026)\u2069۔`,
    legendProtected: "پروٹیکٹڈ ریٹ",
    legendUnprotected: "غیر پروٹیکٹڈ ریٹ",
    legendLimit: (l: number) => `${l} یونٹس`,
  },
};

export const dicts: Record<Lang, Dict> = { en, ur };

interface I18n {
  lang: Lang;
  t: Dict;
  setLang: (l: Lang) => void;
}

const Ctx = createContext<I18n | null>(null);

function initial(): Lang {
  try {
    const saved = localStorage.getItem("sahibill.lang");
    if (saved === "en" || saved === "ur") return saved;
  } catch {
    /* storage blocked */
  }
  return navigator.language?.startsWith("ur") ? "ur" : "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initial);
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ur" ? "rtl" : "ltr";
  }, [lang]);
  const value = useMemo<I18n>(
    () => ({
      lang,
      t: dicts[lang],
      setLang: (l) => {
        setLangState(l);
        try {
          localStorage.setItem("sahibill.lang", l);
        } catch {
          /* storage blocked */
        }
      },
    }),
    [lang],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const v = useContext(Ctx);
  if (!v) throw new Error("useI18n outside I18nProvider");
  return v;
}

const MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const MONTHS_UR = ["جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون", "جولائی", "اگست", "ستمبر", "اکتوبر", "نومبر", "دسمبر"];

/** "2026-09" -> "September 2026" / "ستمبر 2026"; anything else is returned as given. */
export function monthName(ym: string | null | undefined, lang: Lang, short = false): string {
  const m = /^(\d{4})-(\d{2})/.exec(ym || "");
  if (!m) return ym || "";
  const names = lang === "ur" ? MONTHS_UR : MONTHS_EN;
  const name = names[Number(m[2]) - 1] || m[2];
  return `${short && lang === "en" ? name.slice(0, 3) : name} ${m[1]}`;
}
