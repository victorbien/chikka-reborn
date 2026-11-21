import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { PersonResult } from "@/features/contacts/components/PersonResult";
import { QueryError } from "@/features/contacts/components/QueryError";
import { useContactSearch } from "@/features/contacts/hooks/useContacts";
import {
  MIN_SEARCH_LENGTH,
  requestNoteSchema,
  type RequestNoteInput,
  type RequestNoteValues,
} from "@/features/contacts/schemas";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

/**
 * Find someone by exact username, email or mobile number and send a request.
 * An email or number only matches when its owner chose to be found that way, and a miss
 * looks the same whatever the reason, so this dialog cannot be used to check who is registered.
 */
export function AddContactDialog() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const debounced = useDebouncedValue(query, 300);
  const search = useContactSearch(debounced);
  const form = useForm<RequestNoteInput, unknown, RequestNoteValues>({
    resolver: zodResolver(requestNoteSchema),
    defaultValues: { note: "" },
    mode: "onChange",
  });
  const noteText = useWatch({ control: form.control, name: "note" }) ?? "";
  const parsedNote = requestNoteSchema.safeParse({ note: noteText });
  const note = parsedNote.success ? parsedNote.data.note : null;
  const ready = query.trim().length >= MIN_SEARCH_LENGTH && query.trim() === debounced.trim();

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setQuery("");
          form.reset();
        }
      }}
    >
      <DialogTrigger asChild>
        <Button>Add contact</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle className="text-lg font-semibold">Add a contact</DialogTitle>
        <DialogDescription className="mt-1 text-sm text-fg-muted">
          Enter an exact username. You can also use an email address or mobile number, but only
          people who chose to be found that way will appear.
        </DialogDescription>
        <div className="mt-4 space-y-3">
          <FormField label="Username, email or mobile number">
            <Input
              value={query}
              autoComplete="off"
              spellCheck={false}
              onChange={(event) => setQuery(event.target.value)}
            />
          </FormField>
          <FormField
            label="Note (optional)"
            error={form.formState.errors.note?.message}
            hint={`${noteText.length}/140`}
          >
            <Textarea rows={2} {...form.register("note")} />
          </FormField>
          <div aria-live="polite" className="min-h-12">
            {ready && search.isFetching ? (
              <p role="status" className="text-sm text-fg-muted">
                Searching…
              </p>
            ) : null}
            {ready && search.isError ? (
              <QueryError error={search.error} onRetry={() => void search.refetch()} />
            ) : null}
            {ready && search.data && !search.isFetching ? (
              search.data.people.length > 0 ? (
                <ul>
                  {search.data.people.map((person) => (
                    <PersonResult key={person.user_id} person={person} note={note} />
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-fg-muted">
                  No one found. Check the spelling, or ask them for their username.
                </p>
              )
            ) : null}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
