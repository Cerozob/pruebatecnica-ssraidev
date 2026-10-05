import { describe, expect, it } from "vitest";
import { isAdmin } from "./auth";

describe("isAdmin", () => {
  it("reconoce el grupo de administradores", () => {
    expect(isAdmin({ "cognito:groups": ["users", "admins"] })).toBe(true);
  });

  it("niega el acceso a usuarios normales o sin grupos", () => {
    expect(isAdmin({ "cognito:groups": ["users"] })).toBe(false);
    expect(isAdmin({})).toBe(false);
    expect(isAdmin(undefined)).toBe(false);
  });
});
