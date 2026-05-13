import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  buildCookieConsentCookie,
  COOKIE_CONSENT_COOKIE_NAME,
  COOKIE_CONSENT_MAX_AGE_SECONDS,
  COOKIE_CONSENT_VERSION,
  createCookieConsentRecord,
  isCookieConsentChoice
} from "./cookie-consent.ts";

describe("cookie consent helpers", () => {
  it("accepts only supported consent choices", () => {
    assert.equal(isCookieConsentChoice("accepted"), true);
    assert.equal(isCookieConsentChoice("essential"), true);
    assert.equal(isCookieConsentChoice("rejected"), false);
    assert.equal(isCookieConsentChoice(null), false);
  });

  it("creates versioned consent records", () => {
    const decidedAt = new Date("2026-05-13T12:00:00.000Z");

    assert.deepEqual(createCookieConsentRecord("essential", decidedAt), {
      choice: "essential",
      decidedAt: "2026-05-13T12:00:00.000Z",
      version: COOKIE_CONSENT_VERSION
    });
  });

  it("builds a durable SameSite cookie", () => {
    assert.equal(
      buildCookieConsentCookie("accepted", true),
      `${COOKIE_CONSENT_COOKIE_NAME}=accepted; Max-Age=${COOKIE_CONSENT_MAX_AGE_SECONDS}; Path=/; SameSite=Lax; Secure`,
    );
    assert.equal(
      buildCookieConsentCookie("essential", false),
      `${COOKIE_CONSENT_COOKIE_NAME}=essential; Max-Age=${COOKIE_CONSENT_MAX_AGE_SECONDS}; Path=/; SameSite=Lax`,
    );
  });
});
