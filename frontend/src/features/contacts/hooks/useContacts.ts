import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import { contactsApi } from "@/features/contacts/api";
import { contactKeys } from "@/features/contacts/query-keys";
import { MIN_SEARCH_LENGTH } from "@/features/contacts/schemas";
import type { ContactListParams } from "@/features/contacts/types";

/** Presence changes while the page is open, so the buddy list refreshes on a timer. */
const PRESENCE_REFRESH_MS = 30_000;

export function useContactList(params: ContactListParams) {
  return useQuery({
    queryKey: contactKeys.list(params),
    queryFn: ({ signal }) => contactsApi.list(params, signal),
    placeholderData: keepPreviousData,
    refetchInterval: PRESENCE_REFRESH_MS,
  });
}

export function useContactDetail(id: string | null) {
  return useQuery({
    queryKey: contactKeys.detail(id ?? ""),
    queryFn: ({ signal }) => contactsApi.detail(id ?? "", signal),
    enabled: id !== null,
  });
}

/** Callers pass an already debounced query; anything shorter than two characters sends nothing. */
export function useContactSearch(query: string) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: contactKeys.search(trimmed),
    queryFn: ({ signal }) => contactsApi.search(trimmed, signal),
    enabled: trimmed.length >= MIN_SEARCH_LENGTH,
    staleTime: 10_000,
    retry: false,
  });
}

export function useRequests(direction: "incoming" | "outgoing", page = 1) {
  return useQuery({
    queryKey: contactKeys.requests(direction, page),
    queryFn: ({ signal }) => contactsApi.requests(direction, page, signal),
    refetchInterval: PRESENCE_REFRESH_MS,
  });
}

export function useGroups() {
  return useQuery({
    queryKey: contactKeys.groups(),
    queryFn: ({ signal }) => contactsApi.groups(signal),
  });
}

export function useBlocks() {
  return useQuery({
    queryKey: contactKeys.blocks(),
    queryFn: ({ signal }) => contactsApi.blocks(signal),
  });
}

export function useRecentContacts() {
  return useQuery({
    queryKey: contactKeys.recent(),
    queryFn: ({ signal }) => contactsApi.recent(signal),
  });
}

export function useRecentConversations() {
  return useQuery({
    queryKey: contactKeys.recentConversations(),
    queryFn: ({ signal }) => contactsApi.recentConversations(signal),
  });
}

/** Any change can touch lists, details, groups, requests and search relationships. */
function refreshAll(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: contactKeys.all });
}

function useRefreshing<TVariables, TResult>(
  mutationFn: (variables: TVariables) => Promise<TResult>,
) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn, onSuccess: () => refreshAll(queryClient) });
}

export const useSendRequest = () =>
  useRefreshing(({ userId, note }: { userId: string; note: string | null }) =>
    contactsApi.sendRequest(userId, note),
  );
export const useAcceptRequest = () =>
  useRefreshing(({ requestId, groupId }: { requestId: string; groupId?: string }) =>
    contactsApi.accept(requestId, groupId),
  );
export const useRejectRequest = () =>
  useRefreshing(({ requestId, block }: { requestId: string; block: boolean }) =>
    contactsApi.reject(requestId, block),
  );
export const useCancelRequest = () =>
  useRefreshing((requestId: string) => contactsApi.cancel(requestId));
export const useUpdateContact = () =>
  useRefreshing(
    ({
      id,
      changes,
    }: {
      id: string;
      changes: { is_favourite?: boolean; nickname?: string | null };
    }) => contactsApi.update(id, changes),
  );
export const useRemoveContact = () => useRefreshing((id: string) => contactsApi.remove(id));
export const useCreateGroup = () => useRefreshing((name: string) => contactsApi.createGroup(name));
export const useRenameGroup = () =>
  useRefreshing(({ id, name }: { id: string; name: string }) => contactsApi.renameGroup(id, name));
export const useDeleteGroup = () => useRefreshing((id: string) => contactsApi.deleteGroup(id));
export const useAddToGroup = () =>
  useRefreshing(({ groupId, contactId }: { groupId: string; contactId: string }) =>
    contactsApi.addToGroup(groupId, contactId),
  );
export const useRemoveFromGroup = () =>
  useRefreshing(({ groupId, contactId }: { groupId: string; contactId: string }) =>
    contactsApi.removeFromGroup(groupId, contactId),
  );
export const useBlockUser = () => useRefreshing((userId: string) => contactsApi.block(userId));
export const useUnblockUser = () => useRefreshing((userId: string) => contactsApi.unblock(userId));
export const useClearRecent = () => useRefreshing(() => contactsApi.clearRecent());
