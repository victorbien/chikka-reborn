/** Mirrors ProfileResponse in backend/app/modules/profiles/schemas.py. */
export type Theme = "system" | "light" | "dark";
export type UiMode = "modern" | "classic";
export type PresencePreference = "online" | "away" | "busy" | "invisible";
export type PresenceState = PresencePreference | "offline";
export type VerificationMode = "live" | "simulated";

export interface PhoneSummary {
  masked: string;
  verification_mode: VerificationMode;
  verified_at: string;
}

export interface Profile {
  id: string;
  username: string | null;
  display_name: string;
  email: string | null;
  email_verified: boolean;
  avatar_url: string | null;
  bio: string | null;
  country_code: string | null;
  language: string;
  time_zone: string;
  theme: Theme;
  ui_mode: UiMode;
  presence_preference: PresencePreference;
  role: "user" | "admin";
  status: "pending_verification" | "active" | "suspended" | "deleted";
  onboarding_completed: boolean;
  phone: PhoneSummary | null;
  created_at: string;
  updated_at: string;
}

export interface PresenceInfo {
  status: PresenceState;
  preference: PresencePreference;
  last_seen_at: string | null;
}

export interface PhoneStatus {
  verified: boolean;
  masked: string | null;
  verification_mode: VerificationMode | null;
  verified_at: string | null;
  delivery_mode: VerificationMode;
}

export interface PhoneStart {
  masked: string;
  verification_mode: VerificationMode;
  expires_in: number;
  resend_available_in: number;
}

export interface SimulatedSms {
  label: "SIMULATED";
  to: string;
  body: string;
  created_at: string;
  expires_at: string;
}
