/** Mirrors backend/app/modules/credits/schemas.py. Units are credits x 100. */

export type LedgerType = "demo" | "live";

export type EntryType =
  | "grant"
  | "top_up"
  | "reservation"
  | "reservation_release"
  | "deduction"
  | "refund"
  | "adjustment";

export interface LedgerBalance {
  ledger: LedgerType;
  balance_units: number;
  reserved_units: number;
  available_units: number;
  available_credits: number;
  /** False for the live ledger: live sends are not metered until payments exist. */
  charges_apply: boolean;
}

export interface Balance {
  ledgers: LedgerBalance[];
  /** The ledger the current SMS mode charges: "demo" in simulation. */
  active_ledger: LedgerType;
  is_simulated: boolean;
  low_balance_threshold_units: number;
  is_low: boolean;
  notice: string;
}

export interface CreditTransaction {
  id: string;
  ledger: LedgerType;
  entry_type: EntryType;
  description: string;
  balance_delta: number;
  reserved_delta: number;
  credits_delta: number;
  balance_after: number | null;
  message_id: string | null;
  provider: string | null;
  country_code: string | null;
  segment_count: number | null;
  reason: string | null;
  created_at: string;
}

export interface TransactionPage {
  data: CreditTransaction[];
  pagination: {
    total: number;
    page: number;
    page_size: number;
    has_next: boolean;
    has_prev: boolean;
  };
}
