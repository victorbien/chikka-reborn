import { Sparkles } from "lucide-react";
import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  AiAssistantPanel,
  type AiAssistantPanelProps,
} from "@/features/ai/components/AiAssistantPanel";

/** The entry point composers embed: a button that opens the assistant above the message box.
 *  Closed by default, so the compose field is never blocked or crowded by it. */
export function AiAssistantToggle(props: Omit<AiAssistantPanelProps, "onClose">) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <div>
      <Button
        size="sm"
        variant="ghost"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <Sparkles aria-hidden className="size-4 text-ai" />
        AI assistant
      </Button>
      <div id={panelId}>
        {open ? (
          <AiAssistantPanel
            {...props}
            onUse={(text) => {
              props.onUse(text);
              setOpen(false);
            }}
            onClose={() => setOpen(false)}
          />
        ) : null}
      </div>
    </div>
  );
}
