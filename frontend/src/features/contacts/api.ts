import { apiClient, type ApiClient } from "@/lib/api/client";
import { unwrap, type Envelope } from "@/lib/api/envelope";
import type {
  BlockItem,
  ContactDetail,
  ContactGroup,
  ContactListParams,
  ContactRequestItem,
  ContactSummary,
  Paged,
  RecentContact,
  RecentConversation,
  RequestSent,
  SearchResult,
} from "@/features/contacts/types";

const BASE = "/api/v1/contacts";
export const CONTACT_PAGE_SIZE = 50;

export function createContactsApi(client: ApiClient = apiClient) {
  return {
    list: (params: ContactListParams, signal?: AbortSignal) =>
      client.get<Paged<ContactSummary>>(BASE, {
        signal,
        query: {
          filter: params.filter,
          group_id: params.filter === "group" ? params.groupId : undefined,
          page: params.page,
          page_size: CONTACT_PAGE_SIZE,
        },
      }),
    detail: (id: string, signal?: AbortSignal) =>
      client.get<Envelope<ContactDetail>>(`${BASE}/${id}`, { signal }).then(unwrap),
    update: (id: string, changes: { is_favourite?: boolean; nickname?: string | null }) =>
      client.patch<Envelope<ContactDetail>>(`${BASE}/${id}`, changes).then(unwrap),
    remove: (id: string) => client.delete<void>(`${BASE}/${id}`),
    search: (query: string, signal?: AbortSignal) =>
      client
        .get<Envelope<SearchResult>>(`${BASE}/search`, { signal, query: { q: query } })
        .then(unwrap),

    sendRequest: (userId: string, note: string | null) =>
      client
        .post<Envelope<RequestSent>>(`${BASE}/requests`, { user_id: userId, note })
        .then(unwrap),
    requests: (direction: "incoming" | "outgoing", page: number, signal?: AbortSignal) =>
      client.get<Paged<ContactRequestItem>>(`${BASE}/requests`, {
        signal,
        query: { direction, page, page_size: CONTACT_PAGE_SIZE },
      }),
    accept: (requestId: string, groupId?: string) =>
      client
        .post<Envelope<ContactDetail>>(
          `${BASE}/requests/${requestId}/accept`,
          groupId ? { group_id: groupId } : {},
        )
        .then(unwrap),
    reject: (requestId: string, block: boolean) =>
      client.post<void>(`${BASE}/requests/${requestId}/reject`, { block }),
    cancel: (requestId: string) => client.delete<void>(`${BASE}/requests/${requestId}`),

    groups: (signal?: AbortSignal) =>
      client.get<Envelope<ContactGroup[]>>(`${BASE}/groups`, { signal }).then(unwrap),
    createGroup: (name: string) =>
      client.post<Envelope<ContactGroup>>(`${BASE}/groups`, { name }).then(unwrap),
    renameGroup: (id: string, name: string) =>
      client.patch<Envelope<ContactGroup>>(`${BASE}/groups/${id}`, { name }).then(unwrap),
    deleteGroup: (id: string) => client.delete<void>(`${BASE}/groups/${id}`),
    addToGroup: (groupId: string, contactId: string) =>
      client
        .post<Envelope<ContactGroup>>(`${BASE}/groups/${groupId}/members`, {
          contact_ids: [contactId],
        })
        .then(unwrap),
    removeFromGroup: (groupId: string, contactId: string) =>
      client.delete<void>(`${BASE}/groups/${groupId}/members/${contactId}`),

    blocks: (signal?: AbortSignal) =>
      client.get<Envelope<BlockItem[]>>(`${BASE}/blocks`, { signal }).then(unwrap),
    block: (userId: string) =>
      client.post<Envelope<BlockItem>>(`${BASE}/blocks`, { user_id: userId }).then(unwrap),
    unblock: (userId: string) => client.delete<void>(`${BASE}/blocks/${userId}`),

    recent: (signal?: AbortSignal) =>
      client.get<Envelope<RecentContact[]>>(`${BASE}/recent`, { signal }).then(unwrap),
    clearRecent: () => client.delete<void>(`${BASE}/recent`),
    recentConversations: (signal?: AbortSignal) =>
      client
        .get<Envelope<RecentConversation[]>>(`${BASE}/recent-conversations`, { signal })
        .then(unwrap),
  };
}

export const contactsApi = createContactsApi();
