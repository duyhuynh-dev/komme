export const COOKIE_CONSENT_STORAGE_KEY = "komme_cookie_consent_v1";
export const COOKIE_CONSENT_COOKIE_NAME = "komme_cookie_consent";
export const COOKIE_CONSENT_VERSION = 1;
export const COOKIE_CONSENT_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

export type CookieConsentChoice = "accepted" | "essential";

export type CookieConsentRecord = {
  choice: CookieConsentChoice;
  decidedAt: string;
  version: typeof COOKIE_CONSENT_VERSION;
};

export function isCookieConsentChoice(value: string | null): value is CookieConsentChoice {
  return value === "accepted" || value === "essential";
}

export function createCookieConsentRecord(
  choice: CookieConsentChoice,
  now: Date = new Date(),
): CookieConsentRecord {
  return {
    choice,
    decidedAt: now.toISOString(),
    version: COOKIE_CONSENT_VERSION
  };
}

export function buildCookieConsentCookie(choice: CookieConsentChoice, secure = true) {
  const secureFlag = secure ? "; Secure" : "";

  return `${COOKIE_CONSENT_COOKIE_NAME}=${choice}; Max-Age=${COOKIE_CONSENT_MAX_AGE_SECONDS}; Path=/; SameSite=Lax${secureFlag}`;
}

export function readCookieConsent(): CookieConsentRecord | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const stored = window.localStorage.getItem(COOKIE_CONSENT_STORAGE_KEY);

    if (stored) {
      const parsed = JSON.parse(stored) as Partial<CookieConsentRecord>;
      const choice = parsed.choice ?? null;

      if (isCookieConsentChoice(choice)) {
        return {
          choice,
          decidedAt: typeof parsed.decidedAt === "string" ? parsed.decidedAt : new Date(0).toISOString(),
          version: COOKIE_CONSENT_VERSION
        };
      }
    }
  } catch {
    window.localStorage.removeItem(COOKIE_CONSENT_STORAGE_KEY);
  }

  const cookieChoice = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${COOKIE_CONSENT_COOKIE_NAME}=`))
    ?.split("=")[1];

  const choice = cookieChoice ?? null;

  if (!isCookieConsentChoice(choice)) {
    return null;
  }

  return createCookieConsentRecord(choice);
}

export function writeCookieConsent(choice: CookieConsentChoice): CookieConsentRecord {
  const record = createCookieConsentRecord(choice);

  if (typeof window === "undefined") {
    return record;
  }

  window.localStorage.setItem(COOKIE_CONSENT_STORAGE_KEY, JSON.stringify(record));
  document.cookie = buildCookieConsentCookie(choice, window.location.protocol === "https:");

  return record;
}
