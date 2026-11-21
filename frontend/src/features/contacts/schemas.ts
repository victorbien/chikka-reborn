import { z } from "zod";

/** Mirrors backend/app/modules/contacts/schemas.py. The server re-validates everything. */
function plain(value: string): string {
  return value.replace(/<[^>]*>/g, "").trim();
}

export const MIN_SEARCH_LENGTH = 2;

export const searchQuerySchema = z
  .string()
  .transform((value) => value.trim())
  .pipe(z.string().min(MIN_SEARCH_LENGTH).max(254));

export const requestNoteSchema = z.object({
  note: z
    .string()
    .transform(plain)
    .pipe(z.string().max(140, "Use at most 140 characters."))
    .transform((value) => (value === "" ? null : value)),
});
export type RequestNoteInput = z.input<typeof requestNoteSchema>;
export type RequestNoteValues = z.output<typeof requestNoteSchema>;

export const groupNameSchema = z.object({
  name: z
    .string()
    .transform(plain)
    .pipe(z.string().min(1, "Enter a name.").max(30, "Use at most 30 characters.")),
});
export type GroupNameInput = z.input<typeof groupNameSchema>;
export type GroupNameValues = z.output<typeof groupNameSchema>;

export const nicknameSchema = z.object({
  nickname: z
    .string()
    .transform(plain)
    .pipe(z.string().max(100, "Use at most 100 characters."))
    .transform((value) => (value === "" ? null : value)),
});
export type NicknameInput = z.input<typeof nicknameSchema>;
export type NicknameValues = z.output<typeof nicknameSchema>;
