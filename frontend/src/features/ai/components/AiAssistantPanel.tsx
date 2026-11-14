import { Sparkles, X } from "lucide-react";
import { cloneElement, useId, useState, type ReactElement } from "react";
import { FormAlert } from "@/components/common/FormAlert";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { AiDraftCard } from "@/features/ai/components/AiDraftCard";
import { AiOptimiseCompare } from "@/features/ai/components/AiOptimiseCompare";
import {
  useAiRun,
  useAiStatus,
  useRecordDecision,
  useSetAiEnabled,
} from "@/features/ai/hooks/useAi";
import type {
  AiDraft,
  AiRequest,
  AiStatus,
  RewriteInstruction,
  SummaryLength,
  Tone,
} from "@/features/ai/types";
import { toUserFacingError } from "@/lib/error-handling";

type Mode = AiRequest["kind"];

const INSTRUCTIONS: { value: RewriteInstruction; label: string }[] = [
  { value: "make_professional", label: "More professional" },
  { value: "make_friendly", label: "Friendlier" },
  { value: "shorten", label: "Shorter" },
  { value: "improve_clarity", label: "Clearer" },
  { value: "fix_grammar", label: "Fix grammar only" },
  { value: "adjust_tone", label: "Adjust the tone…" },
];
const TONES: { value: Tone; label: string }[] = [
  { value: "formal", label: "Formal" },
  { value: "casual", label: "Casual" },
  { value: "friendly", label: "Friendly" },
  { value: "professional", label: "Professional" },
];
const SUMMARY_LENGTHS: { value: SummaryLength; label: string }[] = [
  { value: "short", label: "Short (1-2 sentences)" },
  { value: "medium", label: "Medium (a paragraph)" },
  { value: "long", label: "Long (detailed)" },
];
const MODE_LABELS: Record<Mode, string> = {
  replies: "Replies",
  translate: "Translate",
  rewrite: "Rewrite",
  summary: "Summary",
  optimise: "Shorten SMS",
  compose: "Write for me",
};
const NEEDS_TEXT: Mode[] = ["translate", "rewrite", "optimise"];

export interface AiAssistantPanelProps {
  /** What is in the message box now. Translate, rewrite and shorten work on it. */
  draft: string;
  /** A Chikka conversation. Without it, replies and summary are not offered. */
  conversationId?: string;
  /** Shorten SMS is offered for SMS drafts only. */
  channel: "chat" | "sms";
  /** Puts text in the message box. The user still has to press Send. */
  onUse: (text: string) => void;
  onClose: () => void;
}

export function AiAssistantPanel({
  draft,
  conversationId,
  channel,
  onUse,
  onClose,
}: AiAssistantPanelProps) {
  const status = useAiStatus();
  return (
    <section aria-label="AI assistant" className="rounded-panel border border-ai bg-surface p-3">
      <header className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <Sparkles aria-hidden className="size-4 text-ai" />
          AI assistant
        </h3>
        <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close AI assistant">
          <X aria-hidden className="size-4" />
        </Button>
      </header>
      <p className="text-xs text-fg-muted">
        Drafts only. Nothing is sent until you press Send. You can always write the message
        yourself.
      </p>
      <div className="mt-2">
        {status.isPending ? (
          <p role="status" className="text-sm text-fg-muted">
            Checking the assistant…
          </p>
        ) : null}
        {status.isError ? (
          <FormAlert tone="error">
            The AI assistant is unavailable right now. You can still write and send your message.
          </FormAlert>
        ) : null}
        {status.data ? (
          <Assistant
            status={status.data}
            draft={draft}
            conversationId={conversationId}
            channel={channel}
            onUse={onUse}
          />
        ) : null}
      </div>
    </section>
  );
}

function Assistant({
  status,
  draft,
  conversationId,
  channel,
  onUse,
}: Omit<AiAssistantPanelProps, "onClose"> & { status: AiStatus }) {
  if (!status.available) {
    return (
      <p role="status" className="text-sm text-fg-muted">
        The AI assistant is switched off by the administrators for now.
      </p>
    );
  }
  if (!status.enabled) return <Consent />;
  return (
    <Tools
      status={status}
      draft={draft}
      conversationId={conversationId}
      channel={channel}
      onUse={onUse}
    />
  );
}

function Consent() {
  const enable = useSetAiEnabled();
  return (
    <div className="space-y-2">
      <p className="text-sm">
        The assistant is off. If you turn it on, the text you ask it to work on, and the latest few
        messages of a conversation when you ask for replies or a summary, are sent to an AI service.
        Emails and long numbers in those messages are masked first. Your name and contacts are not
        sent. You can turn it off at any time.
      </p>
      <Button size="sm" onClick={() => enable.mutate(true)} disabled={enable.isPending}>
        Turn on the AI assistant
      </Button>
      {enable.isError ? (
        <FormAlert tone="error">{toUserFacingError(enable.error).message}</FormAlert>
      ) : null}
    </div>
  );
}

function Tools({
  status,
  draft,
  conversationId,
  channel,
  onUse,
}: Omit<AiAssistantPanelProps, "onClose"> & { status: AiStatus }) {
  const modes: Mode[] = [
    ...(conversationId ? (["replies", "summary"] as Mode[]) : []),
    "translate",
    "rewrite",
    ...(channel === "sms" ? (["optimise"] as Mode[]) : []),
    "compose",
  ];
  const [mode, setMode] = useState<Mode>(modes[0] ?? "translate");
  const [target, setTarget] = useState("en");
  const [source, setSource] = useState("");
  const [instruction, setInstruction] = useState<RewriteInstruction>("make_professional");
  const [tone, setTone] = useState<Tone>("friendly");
  const [length, setLength] = useState<SummaryLength>("medium");
  const [maxSegments, setMaxSegments] = useState(1);
  const [prompt, setPrompt] = useState("");
  const [composeLanguage, setComposeLanguage] = useState("");
  const [result, setResult] = useState<AiDraft | null>(null);
  const run = useAiRun();
  const decide = useRecordDecision();
  const promptId = useId();
  const text = draft.trim();
  const missingText = NEEDS_TEXT.includes(mode) && text.length === 0;

  function request(): AiRequest | null {
    switch (mode) {
      case "replies":
        return conversationId ? { kind: "replies", conversationId } : null;
      case "summary":
        return conversationId ? { kind: "summary", conversationId, length } : null;
      case "translate":
        return { kind: "translate", text, target, source: source || null };
      case "rewrite":
        return {
          kind: "rewrite",
          text,
          instruction,
          tone: instruction === "adjust_tone" ? tone : null,
        };
      case "optimise":
        return { kind: "optimise", text, maxSegments };
      case "compose":
        return { kind: "compose", prompt: prompt.trim(), language: composeLanguage || null };
    }
  }

  function start() {
    const next = request();
    if (!next) return;
    setResult(null);
    run.mutate(next, { onSuccess: setResult });
  }

  function decideOn(decision: "accepted" | "edited" | "dismissed") {
    if (result?.assistanceId) {
      decide.mutate({ assistanceId: result.assistanceId, decision });
    }
  }

  function accept(value: string, edited: boolean) {
    decideOn(edited ? "edited" : "accepted");
    onUse(value);
    setResult(null);
  }

  function reject() {
    decideOn("dismissed");
    setResult(null);
  }

  const canRun = !run.isPending && !missingText && (mode !== "compose" || prompt.trim().length > 0);
  const languages = status.languages;

  return (
    <div className="space-y-3">
      {status.simulated ? (
        <p className="text-xs text-fg-muted">
          Demo assistant: answers are canned examples, not from a real AI model.
        </p>
      ) : null}
      <div role="group" aria-label="What should the assistant do?" className="flex flex-wrap gap-2">
        {modes.map((value) => (
          <Button
            key={value}
            size="sm"
            variant={mode === value ? "primary" : "secondary"}
            aria-pressed={mode === value}
            onClick={() => {
              setMode(value);
              setResult(null);
            }}
          >
            {MODE_LABELS[value]}
          </Button>
        ))}
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {mode === "translate" ? (
          <>
            <Field label="From">
              <Select value={source} onChange={(e) => setSource(e.target.value)}>
                <option value="">Detect automatically</option>
                {languages.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="To">
              <Select value={target} onChange={(e) => setTarget(e.target.value)}>
                {languages.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.name}
                  </option>
                ))}
              </Select>
            </Field>
          </>
        ) : null}
        {mode === "rewrite" ? (
          <>
            <Field label="Make it">
              <Select
                value={instruction}
                onChange={(e) => setInstruction(e.target.value as RewriteInstruction)}
              >
                {INSTRUCTIONS.map((i) => (
                  <option key={i.value} value={i.value}>
                    {i.label}
                  </option>
                ))}
              </Select>
            </Field>
            {instruction === "adjust_tone" ? (
              <Field label="Tone">
                <Select value={tone} onChange={(e) => setTone(e.target.value as Tone)}>
                  {TONES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : null}
          </>
        ) : null}
        {mode === "summary" ? (
          <Field label="Summary length">
            <Select value={length} onChange={(e) => setLength(e.target.value as SummaryLength)}>
              {SUMMARY_LENGTHS.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </Select>
          </Field>
        ) : null}
        {mode === "optimise" ? (
          <Field label="Aim for at most">
            <Select value={maxSegments} onChange={(e) => setMaxSegments(Number(e.target.value))}>
              {[1, 2, 3].map((n) => (
                <option key={n} value={n}>
                  {n === 1 ? "1 segment" : `${n} segments`}
                </option>
              ))}
            </Select>
          </Field>
        ) : null}
        {mode === "compose" ? (
          <>
            <div className="sm:col-span-2">
              <label htmlFor={promptId} className="mb-1 block text-sm font-medium">
                What should the message say?
              </label>
              <Input
                id={promptId}
                value={prompt}
                maxLength={300}
                placeholder="Tell my friend I will be 15 minutes late"
                onChange={(e) => setPrompt(e.target.value)}
              />
            </div>
            <Field label="Language">
              <Select value={composeLanguage} onChange={(e) => setComposeLanguage(e.target.value)}>
                <option value="">Same as my instruction</option>
                {languages.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.name}
                  </option>
                ))}
              </Select>
            </Field>
          </>
        ) : null}
      </div>

      {missingText ? (
        <p className="text-xs text-fg-muted">Write your message first, then ask the assistant.</p>
      ) : null}
      <Button size="sm" onClick={start} disabled={!canRun}>
        {run.isPending ? "Working…" : result ? "Try again" : "Ask the assistant"}
      </Button>

      <div aria-live="polite">
        {run.isPending ? <p className="text-sm text-fg-muted">Thinking…</p> : null}
        {run.isError ? (
          <FormAlert tone="error">
            {toUserFacingError(run.error).message} You can keep writing your message yourself.
          </FormAlert>
        ) : null}
        {result ? <Result result={result} onAccept={accept} onReject={reject} /> : null}
      </div>
    </div>
  );
}

function Result({
  result,
  onAccept,
  onReject,
}: {
  result: AiDraft;
  onAccept: (text: string, edited: boolean) => void;
  onReject: () => void;
}) {
  if (result.texts.length === 0) {
    return (
      <p role="status" className="text-sm text-fg-muted">
        {result.message ?? "Couldn't generate a suggestion. Try again, or write it yourself."}
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {result.optimise ? <AiOptimiseCompare result={result.optimise} /> : null}
      <p className="text-xs text-fg-muted">Draft from the AI. Check it before you use it.</p>
      <ul aria-label="AI drafts" className="space-y-2">
        {result.texts.map((value) => (
          <AiDraftCard
            key={value}
            text={value}
            canUse={result.kind !== "summary"}
            onAccept={onAccept}
            onReject={onReject}
          />
        ))}
      </ul>
    </div>
  );
}

/** A label tied to its single control, so every select has an accessible name. */
function Field({ label, children }: { label: string; children: ReactElement<{ id?: string }> }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      {cloneElement(children, { id })}
    </div>
  );
}
