// Plain names for every field the reader returns, in English and Urdu. Fields not listed here are not shown.
import type { Lang } from "./i18n";

export const FIELD_NAMES: Record<string, [string, string]> = {
  billing_month: ["Bill month", "بل کا مہینہ"],
  reading_date: ["Reading date", "ریڈنگ کی تاریخ"],
  prev_reading_date: ["Previous reading date", "پچھلی ریڈنگ کی تاریخ"],
  issue_date: ["Issue date", "اجرا کی تاریخ"],
  due_date: ["Due date", "آخری تاریخ"],
  tariff: ["Tariff", "ٹیرف"],
  sanctioned_load_kw: ["Sanctioned load (kW)", "منظور شدہ لوڈ (کلوواٹ)"],
  status: ["Category", "زمرہ"],
  prev_reading: ["Previous reading", "پچھلی ریڈنگ"],
  present_reading: ["Present reading", "موجودہ ریڈنگ"],
  units: ["Units billed", "یونٹس"],
  carried_forward: ["Units carried forward", "آگے منتقل یونٹس"],
  pro_rata: ["Reading is pro-rata", "پرو ریٹا ریڈنگ"],
  outstanding_units: ["Outstanding units", "بقایا یونٹس"],
  snapshot_state: ["Meter photo on the bill", "بل پر میٹر کی تصویر"],
  snapshot_reading: ["Meter photo reading", "میٹر تصویر کی ریڈنگ"],
  snapshot_stamp: ["Meter photo time stamp", "میٹر تصویر کا وقت"],
  snapshot_stamp_printed: ["Time stamp printed", "وقت درج ہے"],
  variable: ["Cost of electricity (Rs)", "بجلی کی قیمت (روپے)"],
  fixed: ["Fixed charges (Rs)", "مقررہ چارجز (روپے)"],
  min_charge: ["Minimum charges (Rs)", "کم از کم چارجز (روپے)"],
  fca: ["Fuel price adjustment (Rs)", "فیول پرائس ایڈجسٹمنٹ (روپے)"],
  fc_surcharge: ["F.C. surcharge (Rs)", "ایف سی سرچارج (روپے)"],
  qta: ["Quarterly tariff adjustment (Rs)", "سہ ماہی ٹیرف ایڈجسٹمنٹ (روپے)"],
  gst: ["GST (Rs)", "جی ایس ٹی (روپے)"],
  gst_on_fpa: ["GST on fuel adjustment (Rs)", "فیول ایڈجسٹمنٹ پر جی ایس ٹی (روپے)"],
  total_electricity_charges: ["Total electricity charges (Rs)", "کل بجلی چارجز (روپے)"],
  subsidies: ["Subsidies (Rs)", "سبسڈی (روپے)"],
  net_electricity_charges: ["Net electricity charges (Rs)", "خالص بجلی چارجز (روپے)"],
  taxes: ["Taxes (Rs)", "ٹیکس (روپے)"],
  current_bill: ["Current bill (Rs)", "موجودہ بل (روپے)"],
  total_fpa: ["Total fuel adjustment (Rs)", "کل فیول ایڈجسٹمنٹ (روپے)"],
  payable_within: ["Payable within due date (Rs)", "مقررہ تاریخ تک قابل ادائیگی (روپے)"],
};

export function fieldName(key: string, lang: Lang): string | null {
  const n = FIELD_NAMES[key];
  return n ? n[lang === "ur" ? 1 : 0] : null;
}
