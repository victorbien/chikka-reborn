import { createHmac } from "node:crypto";
import { JWT_SECRET, MOCK_WEBHOOK_SECRET } from "./stack";

const b64 = (value: string | Buffer): string => Buffer.from(value).toString("base64url");

export function decodeClaims(token: string): Record<string, unknown> {
  return JSON.parse(Buffer.from(token.split(".")[1] ?? "", "base64url").toString()) as Record<
    string,
    unknown
  >;
}

/** An HS256 token over `claims`, signed with `secret` (the stack's real secret by default). */
export function signJwt(claims: Record<string, unknown>, secret: string = JWT_SECRET): string {
  const head = b64(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = b64(JSON.stringify(claims));
  const signature = createHmac("sha256", secret).update(`${head}.${body}`).digest("base64url");
  return `${head}.${body}.${signature}`;
}

/** A token with no signature at all (the classic `alg: none` downgrade). */
export function unsignedJwt(claims: Record<string, unknown>): string {
  return `${b64(JSON.stringify({ alg: "none", typ: "JWT" }))}.${b64(JSON.stringify(claims))}.`;
}

/** Signature the mock SMS provider puts on its webhooks: HMAC-SHA256 over "<timestamp>.<body>". */
export function webhookSignature(timestamp: string, rawBody: string | Buffer): string {
  return createHmac("sha256", MOCK_WEBHOOK_SECRET)
    .update(Buffer.concat([Buffer.from(`${timestamp}.`), Buffer.from(rawBody)]))
    .digest("hex");
}
