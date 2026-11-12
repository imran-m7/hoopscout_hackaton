import { describe, expect, it } from "vitest";
import { ageGroupForBirthDate, ageMonthsFrom } from "@/lib/format";

// Must match the backend exactly (contract v3.1, Bosnian categories).
describe("age group by birth year", () => {
  const now = new Date(2026, 10, 12); // 12 Nov 2026
  it.each([
    ["2010-03-01", "U16"], // turns 16 this year
    ["2011-12-31", "U16"], // turns 15
    ["2012-01-01", "U14"], // turns 14
    ["2013-06-15", "U14"], // turns 13
    ["2014-05-05", "U12"],
    ["2016-01-01", "U10"],
    ["2008-07-07", "U18"],
  ])("%s -> %s", (birth, group) => {
    expect(ageGroupForBirthDate(birth, now)).toBe(group);
  });
});

describe("age in months (year + month, day ignored)", () => {
  it("counts from birth year + month to the current month", () => {
    const now = new Date(2026, 10, 12);
    expect(ageMonthsFrom("2012-10-05", now)).toBe(169);
    expect(ageMonthsFrom("2012-10-30", now)).toBe(169);
  });
});
