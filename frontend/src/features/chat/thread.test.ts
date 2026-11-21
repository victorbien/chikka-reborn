import { describe, expect, it } from "vitest";
import {
  addLocal,
  applyStatus,
  combine,
  EMPTY_THREAD,
  isGap,
  maxSeq,
  mergeMessages,
  mergePage,
  setLocalState,
} from "@/features/chat/thread";
import type { ServerMessage } from "@/features/chat/types";

function message(seq: number, overrides: Partial<ServerMessage> = {}): ServerMessage {
  return {
    id: `m-${seq}`,
    conversation_id: "k-1",
    seq,
    sender_user_id: "u-other",
    is_mine: false,
    body: `message ${seq}`,
    attachments: [],
    created_at: `2026-11-12T08:0${seq}:00Z`,
    edited_at: null,
    client_message_id: null,
    status: null,
    status_version: null,
    delivered_at: null,
    read_at: null,
    ...overrides,
  };
}

describe("thread merging", () => {
  it("orders by seq, not by arrival, and ignores duplicates", () => {
    let thread = mergeMessages(EMPTY_THREAD, [message(3), message(1)]);
    thread = mergeMessages(thread, [message(2), message(3)]);
    expect(thread.messages.map((m) => m.seq)).toEqual([1, 2, 3]);
  });

  it("replaces the local copy when the stored message arrives, in either order", () => {
    const draft = {
      clientMessageId: "c-1",
      conversationId: "k-1",
      senderId: "me",
      body: "hi",
      attachments: [],
      createdAt: "2026-11-12T09:00:00Z",
    };
    const stored = message(4, {
      is_mine: true,
      client_message_id: "c-1",
      status: "sent",
      status_version: 1,
    });
    const viaPush = mergeMessages(addLocal(EMPTY_THREAD, draft), [stored]);
    const twice = mergeMessages(viaPush, [stored]);
    expect(twice.messages).toHaveLength(1);
    expect(twice.messages[0]?.local).toBeUndefined();
    expect(twice.messages[0]?.status).toBe("sent");
  });

  it("keeps unsent messages after stored ones", () => {
    const thread = addLocal(mergeMessages(EMPTY_THREAD, [message(1)]), {
      clientMessageId: "c-2",
      conversationId: "k-1",
      senderId: "me",
      body: "pending",
      attachments: [],
      createdAt: "2026-11-12T07:00:00Z",
    });
    const later = mergeMessages(thread, [message(2)]);
    expect(later.messages.map((m) => m.body)).toEqual(["message 1", "message 2", "pending"]);
    expect(setLocalState(later, "c-2", "failed", "Offline").messages[2]?.status).toBe("failed");
  });

  it("applies a status only when it is newer", () => {
    const thread = mergeMessages(EMPTY_THREAD, [
      message(1, { is_mine: true, status: "sent", status_version: 1 }),
    ]);
    const delivered = applyStatus(thread, {
      message_id: "m-1",
      conversation_id: "k-1",
      status: "delivered",
      status_version: 2,
      delivered_at: "2026-11-12T08:05:00Z",
      read_at: null,
    });
    expect(delivered.messages[0]?.status).toBe("delivered");
    const stale = applyStatus(delivered, {
      message_id: "m-1",
      conversation_id: "k-1",
      status: "sent",
      status_version: 1,
      delivered_at: null,
      read_at: null,
    });
    expect(stale.messages[0]?.status).toBe("delivered");
    // A refetch with an older copy does not roll the status back either.
    const refetched = mergeMessages(stale, [
      message(1, { is_mine: true, status: "sent", status_version: 1 }),
    ]);
    expect(refetched.messages[0]?.status).toBe("delivered");
  });

  it("keeps messages pushed or sent while a resync request was in flight", () => {
    // Regression: the resync used to overwrite the cache with a snapshot taken before the
    // request, dropping a message pushed in the meantime.
    const fetched = mergeMessages(EMPTY_THREAD, [message(1)]);
    const cacheNow = addLocal(mergeMessages(EMPTY_THREAD, [message(1), message(2)]), {
      clientMessageId: "c-9",
      conversationId: "k-1",
      senderId: "me",
      body: "typed during the request",
      attachments: [],
      createdAt: "2026-11-12T09:00:00Z",
    });
    const result = combine(fetched, cacheNow);
    expect(result.messages.map((m) => m.body)).toEqual([
      "message 1",
      "message 2",
      "typed during the request",
    ]);
    // Once the stored copy is known, the local one is not kept twice.
    const stored = message(3, {
      is_mine: true,
      client_message_id: "c-9",
      status: "sent",
      status_version: 1,
    });
    expect(combine(mergeMessages(fetched, [stored]), cacheNow).messages).toHaveLength(3);
  });

  it("detects gaps and keeps older pages on refresh", () => {
    const thread = mergePage(undefined, {
      messages: [message(5), message(6)],
      has_more_before: true,
      last_read_seq: 4,
      peer_read_seq: null,
    });
    expect(isGap(thread, 7)).toBe(false);
    expect(isGap(thread, 9)).toBe(true);
    expect(isGap(EMPTY_THREAD, 9)).toBe(false);
    const withOlder = mergePage(
      thread,
      {
        messages: [message(3), message(4)],
        has_more_before: false,
        last_read_seq: 4,
        peer_read_seq: null,
      },
      true,
    );
    expect(withOlder.hasMoreBefore).toBe(false);
    const refreshed = mergePage(withOlder, {
      messages: [message(5), message(6), message(7)],
      has_more_before: true,
      last_read_seq: 6,
      peer_read_seq: null,
    });
    expect(refreshed.messages.map((m) => m.seq)).toEqual([3, 4, 5, 6, 7]);
    expect(refreshed.hasMoreBefore).toBe(false);
    expect(refreshed.lastReadSeq).toBe(6);
    expect(maxSeq(refreshed)).toBe(7);
  });
});
