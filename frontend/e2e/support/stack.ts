/** Addresses and throwaway credentials of the local end-to-end stack (see playwright.config.ts). */
export const API = "http://localhost:8010";
export const FAKE = "http://127.0.0.1:54400";
export const SERVICE_KEY = "e2e-service-role-key";
export const PASSWORD = "Correct-Horse-7";
/** Throwaway secrets of the local stack. The security specs use them to forge tokens and webhooks. */
export const JWT_SECRET = "e2e-only-jwt-secret-with-at-least-32-bytes";
export const MOCK_WEBHOOK_SECRET = "e2e-only-mock-webhook-secret-0123456789";
