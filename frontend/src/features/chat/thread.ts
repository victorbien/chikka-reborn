/**
 * The cached state of one open conversation, and the pure functions that change it.
 *
 * Server messages are ordered by `seq` (never by clock). Messages not stored yet ("pending")
 * or that could not be stored ("failed") follow them in the order they were written. When the
 * stored copy arrives (REST response or push, whichever is first) it replaces the local one,
 * matched by client_message_id, so a message never appears twice. A status only applies when
 * its status_version is newer than what is held.
 */
import type {
  Attachment,
  ChatMessage,
  MessagePage,
  ServerMessage,
  StatusChange,
} from "@/features/chat/types";

export interface Thread {
  messages: ChatMessage[];
  hasMoreBefore: boolean;
  lastReadSeq: number;
  peerReadSeq: number | null;
}

export const EMPTY_THREAD: Thread = {
  messages: [],
  hasMoreBefore: false,
  lastReadSeq: 0,
  peerReadSeq: null,
};

export function maxSeq(thread: Thread | undefined): number {
  let highest = 0;
  for (const message of thread?.messages ?? []) {
    if (!message.local && message.seq > highest) highest = message.seq;
  }
  return highest;
}

export function minSeq(thread: Thread | undefined): number | null {
  let lowest: number | null = null;
  for (const message of thread?.messages ?? []) {
    if (!message.local && (lowest === null || message.seq < lowest)) lowest = message.seq;
  }
  return lowest;
}

function order(messages: ChatMessage[]): ChatMessage[] {
  const stored = messages.filter((m) => !m.local).sort((a, b) => a.seq - b.seq);
  const local = messages
    .filter((m) => m.local)
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
  return [...stored, ...local];
}

function newer(incoming: ServerMessage, current: ChatMessage): boolean {
  if (current.local) return true;
  return (incoming.status_version ?? 0) >= (current.status_version ?? 0);
}

/** Insert or update stored messages. Idempotent: merging the same data twice changes nothing. */
export function mergeMessages(thread: Thread, incoming: ServerMessage[]): Thread {
  if (incoming.length === 0) return thread;
  const byId = new Map(thread.messages.filter((m) => !m.local).map((m) => [m.id, m]));
  const localByClientId = new Map(
    thread.messages.filter((m) => m.local).map((m) => [m.client_message_id, m]),
  );
  for (const message of incoming) {
    if (message.client_message_id) localByClientId.delete(message.client_message_id);
    const current = byId.get(message.id);
    if (!current || newer(message, current)) byId.set(message.id, { ...message });
  }
  return { ...thread, messages: order([...byId.values(), ...localByClientId.values()]) };
}

export function mergePage(thread: Thread | undefined, page: MessagePage, older = false): Thread {
  const base = thread ?? EMPTY_THREAD;
  const merged = mergeMessages(base, page.messages);
  return {
    ...merged,
    hasMoreBefore: older || !thread ? page.has_more_before : base.hasMoreBefore,
    lastReadSeq: Math.max(base.lastReadSeq, page.last_read_seq),
    peerReadSeq: page.peer_read_seq,
  };
}

/**
 * Union of a freshly fetched thread and what the cache holds now (messages pushed or sent
 * while the request was in flight). Same rules as mergeMessages: newest status wins, and a
 * local message is dropped once its stored copy is present.
 */
export function combine(fetched: Thread, cached: Thread | undefined): Thread {
  if (!cached) return fetched;
  const byId = new Map(fetched.messages.filter((m) => !m.local).map((m) => [m.id, m]));
  for (const message of cached.messages) {
    if (message.local) continue;
    const current = byId.get(message.id);
    if (!current || (message.status_version ?? 0) > (current.status_version ?? 0)) {
      byId.set(message.id, message);
    }
  }
  const storedClientIds = new Set(
    [...byId.values()].map((m) => m.client_message_id).filter((id): id is string => Boolean(id)),
  );
  const locals = new Map<string, ChatMessage>();
  for (const message of [...fetched.messages, ...cached.messages]) {
    const clientId = message.client_message_id;
    if (message.local && clientId && !storedClientIds.has(clientId)) locals.set(clientId, message);
  }
  return {
    ...fetched,
    lastReadSeq: Math.max(fetched.lastReadSeq, cached.lastReadSeq),
    messages: order([...byId.values(), ...locals.values()]),
  };
}

export interface LocalDraft {
  clientMessageId: string;
  conversationId: string;
  senderId: string;
  body: string | null;
  attachments: Attachment[];
  createdAt: string;
}

export function addLocal(thread: Thread, draft: LocalDraft): Thread {
  const message: ChatMessage = {
    id: `local-${draft.clientMessageId}`,
    conversation_id: draft.conversationId,
    seq: 0,
    sender_user_id: draft.senderId,
    is_mine: true,
    body: draft.body,
    attachments: draft.attachments,
    created_at: draft.createdAt,
    edited_at: null,
    client_message_id: draft.clientMessageId,
    status: "pending",
    status_version: null,
    delivered_at: null,
    read_at: null,
    local: { state: "pending", attachmentIds: draft.attachments.map((a) => a.id) },
  };
  return { ...thread, messages: order([...thread.messages, message]) };
}

export function setLocalState(
  thread: Thread,
  clientMessageId: string,
  state: "pending" | "failed",
  error?: string,
): Thread {
  return {
    ...thread,
    messages: thread.messages.map((m) =>
      m.local && m.client_message_id === clientMessageId
        ? { ...m, status: state, local: { ...m.local, state, error } }
        : m,
    ),
  };
}

export function removeLocal(thread: Thread, clientMessageId: string): Thread {
  return {
    ...thread,
    messages: thread.messages.filter((m) => !(m.local && m.client_message_id === clientMessageId)),
  };
}

export function applyStatus(thread: Thread, change: StatusChange): Thread {
  let changed = false;
  const messages = thread.messages.map((m) => {
    if (m.local || m.id !== change.message_id) return m;
    if ((m.status_version ?? 0) >= change.status_version) return m;
    changed = true;
    return {
      ...m,
      status: change.status,
      status_version: change.status_version,
      delivered_at: change.delivered_at,
      read_at: change.read_at,
    };
  });
  return changed ? { ...thread, messages } : thread;
}

/** A pushed message more than one ahead means something was missed: resync from REST. */
export function isGap(thread: Thread | undefined, seq: number): boolean {
  const highest = maxSeq(thread);
  return highest > 0 && seq > highest + 1;
}
