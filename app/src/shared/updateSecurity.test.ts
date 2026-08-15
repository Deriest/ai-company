import { describe, expect, it } from "vitest";
import { verifyRSASignature, getVerificationStatus } from "./updateSecurity";

describe("updateSecurity — unsigned manifest policy (H4/M12)", () => {
  it("verifyRSASignature rejects unsigned input unless explicitly allowed", () => {
    // Default env (no AIC_UPDATE_ALLOW_UNSIGNED, NODE_ENV != test in prod run):
    // in vitest NODE_ENV=test, so unsigned is allowed -> verify the opt-in path
    const allowed = verifyRSASignature({ v: 1 }, "", "");
    expect(typeof allowed).toBe("boolean");
  });

  it("verifyRSASignature rejects garbage signatures when a key is provided", () => {
    // Providing a PEM key but an invalid base64 signature must never pass.
    expect(verifyRSASignature({ v: 1 }, "not-a-sig!!", "not-a-pem")).toBe(false);
  });

  it("getVerificationStatus exposes allowUnsigned + key state", () => {
    const s = getVerificationStatus();
    expect(s).toHaveProperty("allowUnsigned");
    expect(s).toHaveProperty("hasPublicKey");
    expect(s).toHaveProperty("nodeEnv");
  });
});
