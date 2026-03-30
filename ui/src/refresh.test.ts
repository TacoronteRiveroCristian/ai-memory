import { describe, expect, it } from "vitest";

import { shouldPauseAutoRefresh } from "./graph";

describe("auto refresh gating", () => {
  it("pauses refresh while interaction cooldown is active", () => {
    expect(shouldPauseAutoRefresh(true, 1000, 4500, 5000)).toBe(true);
    expect(shouldPauseAutoRefresh(true, 1000, 6100, 5000)).toBe(false);
    expect(shouldPauseAutoRefresh(false, 1000, 2000, 5000)).toBe(false);
  });
});
