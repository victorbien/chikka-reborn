import { Smile } from "lucide-react";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";

/** A compact, dependency-free picker. Emoji are plain Unicode, so any font can render them. */
export const EMOJI: readonly { char: string; name: string }[] = [
  { char: "😀", name: "grinning face" },
  { char: "😂", name: "face with tears of joy" },
  { char: "🥰", name: "smiling face with hearts" },
  { char: "😊", name: "smiling face" },
  { char: "😉", name: "winking face" },
  { char: "😎", name: "smiling face with sunglasses" },
  { char: "🤔", name: "thinking face" },
  { char: "😮", name: "face with open mouth" },
  { char: "😢", name: "crying face" },
  { char: "😭", name: "loudly crying face" },
  { char: "😡", name: "angry face" },
  { char: "😴", name: "sleeping face" },
  { char: "🤗", name: "hugging face" },
  { char: "🙏", name: "folded hands" },
  { char: "👍", name: "thumbs up" },
  { char: "👎", name: "thumbs down" },
  { char: "👋", name: "waving hand" },
  { char: "👏", name: "clapping hands" },
  { char: "💪", name: "flexed biceps" },
  { char: "🤝", name: "handshake" },
  { char: "❤️", name: "red heart" },
  { char: "💔", name: "broken heart" },
  { char: "✨", name: "sparkles" },
  { char: "🔥", name: "fire" },
  { char: "🎉", name: "party popper" },
  { char: "🎂", name: "birthday cake" },
  { char: "☕", name: "hot beverage" },
  { char: "🍚", name: "cooked rice" },
  { char: "🌧️", name: "cloud with rain" },
  { char: "☀️", name: "sun" },
  { char: "🇵🇭", name: "flag of the Philippines" },
  { char: "✅", name: "check mark" },
];

const COLUMNS = 8;

export interface EmojiPickerProps {
  onPick: (emoji: string) => void;
  disabled?: boolean;
}

/** Keyboard accessible (FR-MSG-006 AC2): arrow keys move, Enter picks, Escape closes and
 *  returns focus to the button. */
export function EmojiPicker({ onPick, disabled = false }: EmojiPickerProps) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const panelId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    if (open) itemRefs.current[active]?.focus();
  }, [open, active]);

  function close() {
    setOpen(false);
    triggerRef.current?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const moves: Record<string, number> = {
      ArrowRight: 1,
      ArrowLeft: -1,
      ArrowDown: COLUMNS,
      ArrowUp: -COLUMNS,
    };
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    const move = moves[event.key];
    if (move !== undefined) {
      event.preventDefault();
      setActive((current) => Math.min(EMOJI.length - 1, Math.max(0, current + move)));
    }
  }

  return (
    <div className="relative">
      <Button
        ref={triggerRef}
        size="icon"
        variant="ghost"
        aria-label="Insert emoji"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        disabled={disabled}
        onClick={() => (open ? close() : setOpen(true))}
      >
        <Smile aria-hidden className="size-4" />
      </Button>
      {open ? (
        <div
          id={panelId}
          role="group"
          aria-label="Emoji"
          onKeyDown={onKeyDown}
          className="absolute bottom-12 left-0 z-30 grid w-72 grid-cols-8 gap-1 rounded-panel border border-border bg-surface p-2 bevel"
        >
          {EMOJI.map((emoji, index) => (
            <button
              key={emoji.char}
              ref={(node) => {
                itemRefs.current[index] = node;
              }}
              type="button"
              tabIndex={index === active ? 0 : -1}
              aria-label={emoji.name}
              title={emoji.name}
              onClick={() => {
                onPick(emoji.char);
                close();
              }}
              className="inline-flex size-8 items-center justify-center rounded-control text-lg hover:bg-surface-raised focus-visible:outline-2 focus-visible:outline-accent"
            >
              <span aria-hidden>{emoji.char}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
