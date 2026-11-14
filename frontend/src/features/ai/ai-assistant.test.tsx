import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AiAssistantPanel } from "@/features/ai/components/AiAssistantPanel";
import { AiAssistantToggle } from "@/features/ai/components/AiAssistantToggle";
import type { AiStatus, OptimiseSmsResult } from "@/features/ai/types";
import { ChatComposer } from "@/features/chat/components/ChatComposer";
import { fail, mockApi, ok, type MockHandler } from "@/test/api-mock";

const BASE = "/api/v1/ai";
const CONVERSATION = "11111111-1111-4111-8111-111111111111";
const ASSISTANCE = "22222222-2222-4222-8222-222222222222";

function status(overrides: Partial<AiStatus> = {}): MockHandler {
  return ok<AiStatus>({
    available: true,
    enabled: true,
    simulated: false,
    model_id: "test-model",
    languages: [
      { code: "en", name: "English" },
      { code: "fil", name: "Filipino (Tagalog)" },
      { code: "es", name: "Spanish" },
    ],
    max_text_chars: 1600,
    ...overrides,
  });
}

const meta = {
  assistance_id: ASSISTANCE,
  model_id: "test-model",
  latency_ms: 5,
  simulated: false,
  message: null,
};

function wrap(children: React.ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>);
}

function panel(props: Partial<React.ComponentProps<typeof AiAssistantPanel>> = {}) {
  const onUse = vi.fn();
  wrap(
    <AiAssistantPanel draft="Hello" channel="chat" onUse={onUse} onClose={vi.fn()} {...props} />,
  );
  return onUse;
}

const translated: MockHandler = ok({
  ...meta,
  original_text: "Hello",
  translated_text: "Kumusta",
  source_language: null,
  target_language: "fil",
});

async function translateHello(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(await screen.findByLabelText("To"), "fil");
  await user.click(screen.getByRole("button", { name: "Ask the assistant" }));
  await screen.findByText("Kumusta");
}

describe("AI assistant panel", () => {
  it("explains what is sent and stays off until the user opts in", async () => {
    const api = mockApi({
      [`GET ${BASE}/status`]: status({ enabled: false }),
      [`PUT ${BASE}/settings`]: status({ enabled: true }),
    });
    const user = userEvent.setup();
    panel();

    expect(await screen.findByText(/sent to an AI service/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ask the assistant" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Turn on the AI assistant" }));

    expect(await screen.findByRole("button", { name: "Ask the assistant" })).toBeInTheDocument();
    expect(api.callsTo("PUT", `${BASE}/settings`)[0]?.body).toEqual({ enabled: true });
  });

  it("says so when administrators switched the assistant off", async () => {
    mockApi({ [`GET ${BASE}/status`]: status({ available: false }) });
    panel();

    expect(await screen.findByText(/switched off by the administrators/i)).toBeInTheDocument();
  });

  it("keeps working without the assistant when its status cannot be loaded", async () => {
    mockApi({ [`GET ${BASE}/status`]: fail(502, "ai_unavailable") });
    panel();

    expect(
      await screen.findByText(/You can still write and send your message/i),
    ).toBeInTheDocument();
  });

  it("labels the demo provider honestly", async () => {
    mockApi({ [`GET ${BASE}/status`]: status({ simulated: true }) });
    panel();

    expect(
      await screen.findByText(/canned examples, not from a real AI model/i),
    ).toBeInTheDocument();
  });

  it("translates between chosen languages and only fills the box after Use", async () => {
    const api = mockApi({
      [`GET ${BASE}/status`]: status(),
      [`POST ${BASE}/translate`]: translated,
      [`POST ${BASE}/assistance/${ASSISTANCE}/decision`]: ok({}),
    });
    const user = userEvent.setup();
    const onUse = panel();

    await user.selectOptions(await screen.findByLabelText("From"), "en");
    await translateHello(user);

    expect(onUse).not.toHaveBeenCalled();
    expect(api.callsTo("POST", `${BASE}/translate`)[0]?.body).toEqual({
      text: "Hello",
      target_language: "fil",
      source_language: "en",
    });

    await user.click(screen.getByRole("button", { name: "Use" }));

    expect(onUse).toHaveBeenCalledExactlyOnceWith("Kumusta");
    await waitFor(() =>
      expect(api.callsTo("POST", `${BASE}/assistance/${ASSISTANCE}/decision`)[0]?.body).toEqual({
        decision: "accepted",
      }),
    );
  });

  it("lets the user edit a draft before using it", async () => {
    const api = mockApi({
      [`GET ${BASE}/status`]: status(),
      [`POST ${BASE}/translate`]: translated,
      [`POST ${BASE}/assistance/${ASSISTANCE}/decision`]: ok({}),
    });
    const user = userEvent.setup();
    const onUse = panel();
    await translateHello(user);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const editor = screen.getByLabelText("Edit the AI draft");
    await user.clear(editor);
    await user.type(editor, "Kumusta ka");
    await user.click(screen.getByRole("button", { name: "Use edited text" }));

    expect(onUse).toHaveBeenCalledExactlyOnceWith("Kumusta ka");
    await waitFor(() =>
      expect(api.callsTo("POST", `${BASE}/assistance/${ASSISTANCE}/decision`)[0]?.body).toEqual({
        decision: "edited",
      }),
    );
  });

  it("rejects a draft without using it", async () => {
    const api = mockApi({
      [`GET ${BASE}/status`]: status(),
      [`POST ${BASE}/translate`]: translated,
      [`POST ${BASE}/assistance/${ASSISTANCE}/decision`]: ok({}),
    });
    const user = userEvent.setup();
    const onUse = panel();
    await translateHello(user);

    await user.click(screen.getByRole("button", { name: "Reject" }));

    expect(onUse).not.toHaveBeenCalled();
    expect(screen.queryByText("Kumusta")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(api.callsTo("POST", `${BASE}/assistance/${ASSISTANCE}/decision`)[0]?.body).toEqual({
        decision: "dismissed",
      }),
    );
  });

  it("asks for text first when translate, rewrite or shorten have nothing to work on", async () => {
    mockApi({ [`GET ${BASE}/status`]: status() });
    panel({ draft: "   " });

    expect(await screen.findByText(/Write your message first/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask the assistant" })).toBeDisabled();
  });

  it("rewrites with a chosen instruction and tone", async () => {
    const api = mockApi({
      [`GET ${BASE}/status`]: status(),
      [`POST ${BASE}/rewrite`]: ok({
        ...meta,
        original_text: "Hello",
        rewritten_text: "Hey there!",
        instruction: "adjust_tone",
      }),
    });
    const user = userEvent.setup();
    panel();

    await user.click(await screen.findByRole("button", { name: "Rewrite" }));
    await user.selectOptions(screen.getByLabelText("Make it"), "adjust_tone");
    await user.selectOptions(screen.getByLabelText("Tone"), "friendly");
    await user.click(screen.getByRole("button", { name: "Ask the assistant" }));

    expect(await screen.findByText("Hey there!")).toBeInTheDocument();
    expect(api.callsTo("POST", `${BASE}/rewrite`)[0]?.body).toEqual({
      text: "Hello",
      instruction: "adjust_tone",
      tone: "friendly",
    });
  });

  it("offers replies and summaries only inside a Chikka conversation", async () => {
    mockApi({ [`GET ${BASE}/status`]: status() });
    panel();
    await screen.findByRole("button", { name: "Translate" });
    expect(screen.queryByRole("button", { name: "Replies" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Summary" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Shorten SMS" })).not.toBeInTheDocument();
  });

  it("shows several reply suggestions and sends the conversation id only", async () => {
    const api = mockApi({
      [`GET ${BASE}/status`]: status(),
      [`POST ${BASE}/suggest-replies`]: ok({ ...meta, suggestions: ["Yes!", "Not today"] }),
    });
    const user = userEvent.setup();
    panel({ conversationId: CONVERSATION, draft: "" });

    await user.click(await screen.findByRole("button", { name: "Ask the assistant" }));

    expect(await screen.findByText("Yes!")).toBeInTheDocument();
    expect(screen.getByText("Not today")).toBeInTheDocument();
    expect(api.callsTo("POST", `${BASE}/suggest-replies`)[0]?.body).toEqual({
      conversation_id: CONVERSATION,
      count: 3,
    });
  });

  it("summarises with the chosen length and offers no Use button", async () => {
    const api = mockApi({
      [`GET ${BASE}/status`]: status(),
      [`POST ${BASE}/summarise`]: ok({
        ...meta,
        summary: "They agreed to meet Saturday.",
        messages_summarised: 4,
      }),
    });
    const user = userEvent.setup();
    panel({ conversationId: CONVERSATION, draft: "" });

    await user.click(await screen.findByRole("button", { name: "Summary" }));
    await user.selectOptions(screen.getByLabelText("Summary length"), "short");
    await user.click(screen.getByRole("button", { name: "Ask the assistant" }));

    expect(await screen.findByText("They agreed to meet Saturday.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Use" })).not.toBeInTheDocument();
    expect(api.callsTo("POST", `${BASE}/summarise`)[0]?.body).toEqual({
      conversation_id: CONVERSATION,
      length: "short",
    });
  });

  it("composes a draft from a short instruction", async () => {
    const api = mockApi({
      [`GET ${BASE}/status`]: status(),
      [`POST ${BASE}/compose`]: ok({
        ...meta,
        composed_text: "Hi! I will be 15 minutes late.",
        character_count: 30,
        segments: null,
      }),
    });
    const user = userEvent.setup();
    const onUse = panel({ draft: "" });

    await user.click(await screen.findByRole("button", { name: "Write for me" }));
    const ask = screen.getByRole("button", { name: "Ask the assistant" });
    expect(ask).toBeDisabled();
    await user.type(screen.getByLabelText("What should the message say?"), "I will be late");
    await user.click(ask);
    await user.click(await screen.findByRole("button", { name: "Use" }));

    expect(api.callsTo("POST", `${BASE}/compose`)[0]?.body).toEqual({ prompt: "I will be late" });
    expect(onUse).toHaveBeenCalledExactlyOnceWith("Hi! I will be 15 minutes late.");
  });

  describe("SMS optimisation", () => {
    const optimised: OptimiseSmsResult = {
      ...meta,
      original_text: "A very long message",
      optimised_text: "Short message",
      original: { characters: 200, units: 200, segments: 2, encoding: "gsm7" },
      optimised: { characters: 13, units: 13, segments: 1, encoding: "gsm7" },
      max_segments: 1,
      within_target: true,
      meaning_preserved: true,
    };

    it("shows original and optimised versions with their counts, and no price claim", async () => {
      const api = mockApi({
        [`GET ${BASE}/status`]: status(),
        [`POST ${BASE}/optimise-sms`]: ok(optimised),
      });
      const user = userEvent.setup();
      const onUse = panel({ channel: "sms", draft: "A very long message" });

      await user.click(await screen.findByRole("button", { name: "Shorten SMS" }));
      await user.click(screen.getByRole("button", { name: "Ask the assistant" }));

      const original = await screen.findByRole("region", { name: "Original message" });
      const shorter = screen.getByRole("region", { name: "Shorter version" });
      expect(within(original).getByText(/200 characters, GSM-7, 2 segments/)).toBeInTheDocument();
      expect(within(shorter).getByText(/13 characters, GSM-7, 1 segment$/)).toBeInTheDocument();
      expect(screen.getByText(/Read it carefully/)).toBeInTheDocument();
      expect(document.body.textContent).not.toMatch(/credit|cost|price|save|cheaper/i);
      expect(api.callsTo("POST", `${BASE}/optimise-sms`)[0]?.body).toEqual({
        text: "A very long message",
        max_segments: 1,
      });
      expect(onUse).not.toHaveBeenCalled();
    });

    it("explains when the meaning cannot be kept", async () => {
      mockApi({
        [`GET ${BASE}/status`]: status(),
        [`POST ${BASE}/optimise-sms`]: ok({
          ...optimised,
          optimised_text: null,
          optimised: null,
          within_target: false,
          meaning_preserved: false,
          message:
            "This message can't be shortened to 1 segment(s) without losing important information.",
        }),
      });
      const user = userEvent.setup();
      panel({ channel: "sms", draft: "A very long message" });

      await user.click(await screen.findByRole("button", { name: "Shorten SMS" }));
      await user.click(screen.getByRole("button", { name: "Ask the assistant" }));

      expect(await screen.findByText(/can't be shortened/i)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Use" })).not.toBeInTheDocument();
    });
  });

  describe("failures", () => {
    it("shows the server's message when the model returned nothing usable", async () => {
      mockApi({
        [`GET ${BASE}/status`]: status(),
        [`POST ${BASE}/translate`]: ok({
          ...meta,
          assistance_id: null,
          original_text: "Hello",
          translated_text: null,
          source_language: null,
          target_language: "en",
          message: "Couldn't generate a suggestion. Try again, or write the message yourself.",
        }),
      });
      const user = userEvent.setup();
      panel();

      await user.click(await screen.findByRole("button", { name: "Ask the assistant" }));

      expect(await screen.findByText(/Couldn't generate a suggestion/)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Use" })).not.toBeInTheDocument();
    });

    it("reports a provider error and lets the user try again", async () => {
      let calls = 0;
      mockApi({
        [`GET ${BASE}/status`]: status(),
        [`POST ${BASE}/translate`]: () => {
          calls += 1;
          return calls === 1
            ? fail(502, "ai_unavailable", "The AI assistant is unavailable right now.")
            : translated;
        },
      });
      const user = userEvent.setup();
      panel();

      await user.click(await screen.findByRole("button", { name: "Ask the assistant" }));
      expect(await screen.findByText(/keep writing your message yourself/i)).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Ask the assistant" }));

      expect(await screen.findByText("Kumusta")).toBeInTheDocument();
    });

    it("explains the hourly limit", async () => {
      mockApi({
        [`GET ${BASE}/status`]: status(),
        [`POST ${BASE}/translate`]: fail(429, "rate_limited", "AI features are paused for now."),
      });
      const user = userEvent.setup();
      panel();

      await user.click(await screen.findByRole("button", { name: "Ask the assistant" }));

      expect(await screen.findByText(/paused for now/i)).toBeInTheDocument();
    });
  });
});

describe("AI assistant in the composer", () => {
  it("is closed until opened, and drafting never sends", async () => {
    const api = mockApi({
      [`GET ${BASE}/status`]: status(),
      [`POST ${BASE}/compose`]: ok({
        ...meta,
        composed_text: "Hi! I will be 15 minutes late.",
        character_count: 30,
        segments: null,
      }),
      [`POST ${BASE}/assistance/${ASSISTANCE}/decision`]: ok({}),
    });
    const onSend = vi.fn();
    const user = userEvent.setup();
    wrap(<ChatComposer conversationId={CONVERSATION} onSend={onSend} />);

    expect(screen.queryByRole("region", { name: "AI assistant" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "AI assistant" }));
    await user.click(await screen.findByRole("button", { name: "Write for me" }));
    await user.type(screen.getByLabelText("What should the message say?"), "late");
    await user.click(screen.getByRole("button", { name: "Ask the assistant" }));
    await user.click(await screen.findByRole("button", { name: "Use" }));

    // The draft is in the message box, labelled, and still unsent.
    expect(screen.getByLabelText("Message")).toHaveValue("Hi! I will be 15 minutes late.");
    expect(screen.getByText("AI-assisted")).toBeInTheDocument();
    expect(onSend).not.toHaveBeenCalled();
    expect(api.calls.filter((call) => call.path.includes("/messages"))).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(onSend).toHaveBeenCalledExactlyOnceWith("Hi! I will be 15 minutes late.", []);
    expect(screen.queryByText("AI-assisted")).not.toBeInTheDocument();
  });

  it("leaves typing and sending fully usable when the assistant is down", async () => {
    mockApi({ [`GET ${BASE}/status`]: fail(502, "ai_unavailable") });
    const onSend = vi.fn();
    const user = userEvent.setup();
    wrap(
      <>
        <AiAssistantToggle draft="" channel="chat" onUse={vi.fn()} />
        <ChatComposer conversationId={CONVERSATION} onSend={onSend} />
      </>,
    );

    await user.click(screen.getAllByRole("button", { name: "AI assistant" })[0]!);
    await screen.findByText(/You can still write and send your message/i);
    await user.type(screen.getByLabelText("Message"), "Typed by me");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(onSend).toHaveBeenCalledExactlyOnceWith("Typed by me", []);
  });
});
