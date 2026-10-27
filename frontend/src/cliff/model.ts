// The 200-unit cliff, computed exactly as the rules engine does (sahibill/rules/consumption.py):
// protected households pay block rates; past the limit every unit is charged at one unprotected rate.
import tariff from "./tariff.json";

export type Status = "protected" | "unprotected";

const money = (x: number) => Math.round((x + Number.EPSILON) * 100) / 100;
/** Python's round_half_up for whole numbers (the engine's pro-rata rounding). */
const roundHalfUp = (x: number) => Math.floor(x + 0.5 + 1e-9);

export function unprotectedRate(units: number): number {
  const row = tariff.unprotected.find((r) => r.upto === null || units <= r.upto) || tariff.unprotected[tariff.unprotected.length - 1];
  return row.rate;
}

/** Rs per unit for the unit numbered `n` (1-based) in a bill of `units` units at this status. */
export function rateOfUnit(status: Status, n: number, units: number): number {
  if (status === "unprotected") return unprotectedRate(units);
  return n <= tariff.protected[0].upto! ? tariff.protected[0].rate : tariff.protected[1].rate;
}

export function energyCharge(status: Status, units: number): number {
  if (status === "protected") {
    const [a, b] = tariff.protected;
    return units <= a.upto! ? money(units * a.rate) : money(a.upto! * a.rate + (units - a.upto!) * b.rate);
  }
  return money(units * unprotectedRate(units));
}

export function prorate(units: number, days: number, monthDays: number): number {
  return days <= monthDays ? units : roundHalfUp((units * monthDays) / days);
}

export interface Scenario {
  unitsRead: number;
  unitsBilled: number;
  carried: number;
  status: Status;
  energy: number;
  overLimit: boolean;
}

/** A protected household using `daily` units a day, read after `days` days, in a month of `monthDays`. */
export function scenario(daily: number, days: number, monthDays: number, proRata: boolean): Scenario {
  const unitsRead = Math.round(daily * days);
  const unitsBilled = proRata ? prorate(unitsRead, days, monthDays) : unitsRead;
  const overLimit = unitsBilled > tariff.protected_limit;
  const status: Status = overLimit ? "unprotected" : "protected";
  return { unitsRead, unitsBilled, carried: unitsRead - unitsBilled, status, energy: energyCharge(status, unitsBilled), overLimit };
}

export const LIMIT = tariff.protected_limit;
export const LOST_MONTHS = tariff.protected_months;
