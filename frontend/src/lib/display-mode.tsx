import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type DisplayMode = "modern" | "classic";

export const DISPLAY_MODE_STORAGE_KEY = "chikka.displayMode";

function isDisplayMode(value: unknown): value is DisplayMode {
  return value === "modern" || value === "classic";
}

export function readStoredMode(): DisplayMode {
  try {
    const stored = window.localStorage.getItem(DISPLAY_MODE_STORAGE_KEY);
    return isDisplayMode(stored) ? stored : "modern";
  } catch {
    // Storage can be unavailable (private mode); fall back to the default.
    return "modern";
  }
}

interface DisplayModeContextValue {
  mode: DisplayMode;
  setMode: (mode: DisplayMode) => void;
}

const DisplayModeContext = createContext<DisplayModeContextValue | null>(null);

export function DisplayModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<DisplayMode>(readStoredMode);

  useEffect(() => {
    document.documentElement.dataset.mode = mode;
  }, [mode]);

  const setMode = useCallback((next: DisplayMode) => {
    setModeState(next);
    try {
      window.localStorage.setItem(DISPLAY_MODE_STORAGE_KEY, next);
    } catch {
      // Preference still applies for this session.
    }
  }, []);

  const value = useMemo(() => ({ mode, setMode }), [mode, setMode]);
  return <DisplayModeContext.Provider value={value}>{children}</DisplayModeContext.Provider>;
}

export function useDisplayMode(): DisplayModeContextValue {
  const context = useContext(DisplayModeContext);
  if (!context) {
    throw new Error("useDisplayMode must be used within DisplayModeProvider");
  }
  return context;
}
