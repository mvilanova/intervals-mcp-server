import { createHmac, timingSafeEqual } from "node:crypto";

const COOKIE_NAME = "dashboard_session";

function getSecret(): string {
  const secret = process.env.SESSION_SECRET;
  if (!secret || secret.length < 32) {
    throw new Error(
      "SESSION_SECRET must be set and at least 32 chars long",
    );
  }
  return secret;
}

export function signSession(): string {
  const secret = getSecret();
  return createHmac("sha256", secret).update("auth").digest("hex");
}

export function verifySession(cookieValue: string | undefined): boolean {
  if (!cookieValue) return false;
  let expected: string;
  try {
    expected = signSession();
  } catch {
    return false;
  }
  const a = Buffer.from(cookieValue, "hex");
  const b = Buffer.from(expected, "hex");
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

export { COOKIE_NAME };
