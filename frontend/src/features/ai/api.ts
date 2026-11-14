import { apiClient, type ApiClient } from "@/lib/api/client";
import { unwrap, type Envelope } from "@/lib/api/envelope";
import type {
  AiDecision,
  AiDraft,
  AiRequest,
  AiStatus,
  ComposeResult,
  OptimiseSmsResult,
  RewriteResult,
  SuggestRepliesResult,
  SummariseResult,
  TranslateResult,
} from "@/features/ai/types";

const BASE = "/api/v1/ai";

export function createAiApi(client: ApiClient = apiClient) {
  const post = <T>(path: string, body: unknown, signal?: AbortSignal) =>
    client.post<Envelope<T>>(`${BASE}/${path}`, body, { signal }).then(unwrap);

  return {
    status: (signal?: AbortSignal) =>
      client.get<Envelope<AiStatus>>(`${BASE}/status`, { signal }).then(unwrap),
    setEnabled: (enabled: boolean) =>
      client.put<Envelope<AiStatus>>(`${BASE}/settings`, { enabled }).then(unwrap),
    recordDecision: (assistanceId: string, decision: AiDecision) =>
      post<{ assistance_id: string; decision: AiDecision }>(`assistance/${assistanceId}/decision`, {
        decision,
      }),
    /** Runs one request and reduces the answer to a draft. Never sends anything. */
    run: async (request: AiRequest, signal?: AbortSignal): Promise<AiDraft> => {
      switch (request.kind) {
        case "replies": {
          const r = await post<SuggestRepliesResult>(
            "suggest-replies",
            { conversation_id: request.conversationId, count: 3 },
            signal,
          );
          return draft("replies", r, r.suggestions);
        }
        case "translate": {
          const r = await post<TranslateResult>(
            "translate",
            {
              text: request.text,
              target_language: request.target,
              ...(request.source ? { source_language: request.source } : {}),
            },
            signal,
          );
          return draft("translate", r, [r.translated_text]);
        }
        case "rewrite": {
          const r = await post<RewriteResult>(
            "rewrite",
            {
              text: request.text,
              instruction: request.instruction,
              ...(request.instruction === "adjust_tone" ? { tone: request.tone } : {}),
            },
            signal,
          );
          return draft("rewrite", r, [r.rewritten_text]);
        }
        case "summary": {
          const r = await post<SummariseResult>(
            "summarise",
            { conversation_id: request.conversationId, length: request.length },
            signal,
          );
          return draft("summary", r, [r.summary]);
        }
        case "optimise": {
          const r = await post<OptimiseSmsResult>(
            "optimise-sms",
            { text: request.text, max_segments: request.maxSegments },
            signal,
          );
          return { ...draft("optimise", r, [r.optimised_text]), optimise: r };
        }
        case "compose": {
          const r = await post<ComposeResult>(
            "compose",
            { prompt: request.prompt, ...(request.language ? { language: request.language } : {}) },
            signal,
          );
          return draft("compose", r, [r.composed_text]);
        }
      }
    },
  };
}

function draft(
  kind: AiDraft["kind"],
  result: { assistance_id: string | null; message: string | null; simulated: boolean },
  texts: (string | null)[],
): AiDraft {
  return {
    kind,
    assistanceId: result.assistance_id,
    texts: texts.filter((text): text is string => typeof text === "string" && text.length > 0),
    message: result.message,
    simulated: result.simulated,
  };
}

export const aiApi = createAiApi();
