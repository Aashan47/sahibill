import { describe, expect, it } from "vitest";
import tariff from "./tariff.json";
import { energyCharge, prorate, scenario, type Status } from "./model";

describe("the cliff model matches the rules engine", () => {
  it("energy charges", () => {
    for (const e of tariff.examples) expect(energyCharge(e.status as Status, e.units)).toBe(e.energy);
  });
  it("pro-rata rounding", () => {
    for (const p of tariff.prorata_examples) expect(prorate(p.units, p.days, p.month_days)).toBe(p.billed);
  });
  it("a late reading crosses the limit, and pro-rata brings it back", () => {
    const late = scenario(6, 34, 30, false);
    expect(late.unitsBilled).toBe(204);
    expect(late.status).toBe("unprotected");
    const fixed = scenario(6, 34, 30, true);
    expect(fixed.unitsBilled).toBe(180);
    expect(fixed.carried).toBe(24);
    expect(fixed.status).toBe("protected");
  });
});
