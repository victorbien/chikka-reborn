import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DISPLAY_MODE_STORAGE_KEY, DisplayModeProvider } from "@/lib/display-mode";
import { estimateSms, maskPhoneNumber } from "@/lib/sms";
import { ChannelBadge } from "./ChannelBadge";
import { ConfirmDialog } from "./ConfirmDialog";
import { MessageBubble } from "./MessageBubble";
import { MessageComposer } from "./MessageComposer";
import { MessageStatusLabel } from "./MessageStatusLabel";
import { ModeSwitcher } from "./ModeSwitcher";
import { SmsCostEstimate } from "./SmsCostEstimate";

describe("estimateSms", () => {
  it("counts a short GSM message as one segment", () => {
    expect(estimateSms("Hello")).toMatchObject({ segments: 1, encoding: "gsm7" });
  });
  it("splits long GSM messages at 153 characters", () => {
    expect(estimateSms("a".repeat(161)).segments).toBe(2);
  });
  it("switches to unicode with a 70 character limit", () => {
    expect(estimateSms("é".repeat(1) + "😀")).toMatchObject({ encoding: "unicode", segments: 1 });
    expect(estimateSms("😀".repeat(71)).segments).toBe(2);
  });
  it("masks phone numbers", () => {
    expect(maskPhoneNumber("+639171231234")).toBe("+63****1234");
  });
});

describe("ChannelBadge", () => {
  it("labels simulated SMS", () => {
    render(<ChannelBadge channel="sms-outbound" smsMode="simulated" />);
    expect(screen.getByText("SIMULATED")).toBeInTheDocument();
  });
  it("labels live SMS and not simulated", () => {
    render(<ChannelBadge channel="sms-outbound" smsMode="live" />);
    expect(screen.getByText("LIVE")).toBeInTheDocument();
    expect(screen.queryByText("SIMULATED")).not.toBeInTheDocument();
  });
  it("shows no SMS mode for internet messages", () => {
    render(<ChannelBadge channel="internet" smsMode="live" />);
    expect(screen.queryByText("LIVE")).not.toBeInTheDocument();
  });
});

describe("MessageStatusLabel", () => {
  it("never presents accepted as delivered", () => {
    render(<MessageStatusLabel status="accepted" channel="sms-outbound" />);
    expect(screen.queryByText("Delivered")).not.toBeInTheDocument();
    expect(screen.getByText("Accepted by provider")).toBeInTheDocument();
  });
  it("flags unconfirmed delivery for sent SMS", () => {
    render(<MessageStatusLabel status="sent" channel="sms-outbound" />);
    expect(screen.getByText("(delivery unconfirmed)")).toBeInTheDocument();
  });
});

describe("MessageBubble", () => {
  it("renders markup in the body as plain text", () => {
    render(
      <ul>
        <MessageBubble body="<b>hi</b>" timestamp="12:00" direction="incoming" channel="internet" />
      </ul>,
    );
    expect(screen.getByText("<b>hi</b>")).toBeInTheDocument();
  });
});

describe("SmsCostEstimate", () => {
  it("charges nothing in simulation", () => {
    render(
      <SmsCostEstimate body="Hello" smsMode="simulated" creditsPerSegment={1} creditBalance={0} />,
    );
    expect(screen.getByText(/No credits charged/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
  it("warns when live cost exceeds balance", () => {
    render(
      <SmsCostEstimate body="Hello" smsMode="live" creditsPerSegment={1} creditBalance={0.5} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Not enough credits");
  });
});

describe("MessageComposer", () => {
  const base = { channel: "internet" as const, onChange: vi.fn() };

  it("sends only on explicit action", async () => {
    const onSend = vi.fn();
    render(<MessageComposer {...base} value="Hi" onSend={onSend} />);
    expect(onSend).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("disables sending and explains why when blocked", () => {
    render(
      <MessageComposer
        {...base}
        value="Hi"
        onSend={vi.fn()}
        disabledReason="Recipient opted out."
      />,
    );
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Recipient opted out.");
  });

  it("shows the AI-assisted badge before sending", () => {
    render(<MessageComposer {...base} value="Hi" onSend={vi.fn()} aiAssisted />);
    expect(screen.getByText("AI-assisted")).toBeInTheDocument();
  });

  it("shows cost estimate only for SMS", () => {
    const { rerender } = render(<MessageComposer {...base} value="Hi" onSend={vi.fn()} />);
    expect(screen.queryByText(/segment/)).not.toBeInTheDocument();
    rerender(<MessageComposer {...base} channel="sms-outbound" value="Hi" onSend={vi.fn()} />);
    expect(screen.getByText(/1 segment/)).toBeInTheDocument();
  });
});

describe("ConfirmDialog", () => {
  it("confirms and closes", async () => {
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <ConfirmDialog
        open
        onOpenChange={onOpenChange}
        title="Delete?"
        description="Sure?"
        confirmLabel="Delete"
        onConfirm={onConfirm}
        destructive
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

describe("ModeSwitcher", () => {
  it("switches mode, updates the document and persists the choice", async () => {
    render(
      <DisplayModeProvider>
        <ModeSwitcher />
      </DisplayModeProvider>,
    );
    await userEvent.click(screen.getByRole("radio", { name: /Classic/ }));
    expect(document.documentElement.dataset.mode).toBe("classic");
    expect(window.localStorage.getItem(DISPLAY_MODE_STORAGE_KEY)).toBe("classic");
  });

  it("restores the stored mode", () => {
    window.localStorage.setItem(DISPLAY_MODE_STORAGE_KEY, "classic");
    render(
      <DisplayModeProvider>
        <ModeSwitcher />
      </DisplayModeProvider>,
    );
    expect(screen.getByRole("radio", { name: /Classic/ })).toBeChecked();
  });
});
