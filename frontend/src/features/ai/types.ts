export type SegmentEncoding = "gsm7" | "ucs2";

export interface AiLanguage {
  code: string;
  name: string;
}

export interface AiStatus {
  /** Platform switch (administrator). */
  available: boolean;
  /** This user's opt-in. Off until the user turns it on. */
  enabled: boolean;
  /** True when answers come from the demo provider, not a real model. */
  simulated: boolean;
  model_id: string;
  languages: AiLanguage[];
  max_text_chars: number;
}

interface AiMeta {
  assistance_id: string | null;
  model_id: string;
  latency_ms: number;
  simulated: boolean;
  /** Set when no usable draft came back. */
  message: string | null;
}

export interface SuggestRepliesResult extends AiMeta {
  suggestions: string[];
}

export interface TranslateResult extends AiMeta {
  original_text: string;
  translated_text: string | null;
  source_language: string | null;
  target_language: string;
}

export type RewriteInstruction =
  | "make_professional"
  | "make_friendly"
  | "make_formal"
  | "make_casual"
  | "shorten"
  | "improve_clarity"
  | "fix_grammar"
  | "adjust_tone";

export type Tone = "formal" | "casual" | "friendly" | "professional";

export interface RewriteResult extends AiMeta {
  original_text: string;
  rewritten_text: string | null;
  instruction: RewriteInstruction;
}

export interface SegmentCount {
  characters: number;
  units: number;
  segments: number;
  encoding: SegmentEncoding;
}

export interface OptimiseSmsResult extends AiMeta {
  original_text: string;
  optimised_text: string | null;
  original: SegmentCount;
  optimised: SegmentCount | null;
  max_segments: number;
  within_target: boolean;
  /** The model's own claim, not verified. */
  meaning_preserved: boolean | null;
}

export type SummaryLength = "short" | "medium" | "long";

export interface SummariseResult extends AiMeta {
  summary: string | null;
  messages_summarised: number;
}

export interface ComposeResult extends AiMeta {
  composed_text: string | null;
  character_count: number;
  segments: SegmentCount | null;
}

export type AiDecision = "accepted" | "edited" | "dismissed";

export type AiRequest =
  | { kind: "replies"; conversationId: string }
  | { kind: "translate"; text: string; target: string; source: string | null }
  | { kind: "rewrite"; text: string; instruction: RewriteInstruction; tone: Tone | null }
  | { kind: "summary"; conversationId: string; length: SummaryLength }
  | { kind: "optimise"; text: string; maxSegments: number }
  | { kind: "compose"; prompt: string; language: string | null };

/** What every action reduces to, so one card can show, edit, accept or reject it. */
export interface AiDraft {
  kind: AiRequest["kind"];
  assistanceId: string | null;
  /** Empty when the model produced nothing usable. */
  texts: string[];
  message: string | null;
  simulated: boolean;
  optimise?: OptimiseSmsResult;
}
