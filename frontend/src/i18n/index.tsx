import {
  useCallback,
  useEffect,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { commonMessages } from "./common";
import { entityMessages } from "./entities";
import { graphMessages } from "./graph";
import { shellMessages } from "./shell";

export type Language = "en" | "ru";
export type MessageValues = Record<string, string | number>;
export const LANGUAGE_STORAGE_KEY = "iz2-language";
const messages: Record<string, string> = {
  ...commonMessages,
  ...entityMessages,
  ...graphMessages,
  ...shellMessages,
};
const listeners = new Set<() => void>();

function readPreference(): Language {
  try {
    return localStorage.getItem(LANGUAGE_STORAGE_KEY) === "ru" ? "ru" : "en";
  } catch {
    return "en";
  }
}
let language: Language = readPreference();
export function getLanguage(): Language {
  return language;
}
export function setLanguage(next: Language): void {
  if (next !== "en" && next !== "ru") return;
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, next);
  } catch {
    /* The in-memory preference remains usable. */
  }
  if (next === language) return;
  language = next;
  listeners.forEach((notify) => notify());
}
function storageChanged(event: StorageEvent): void {
  if (event.key !== LANGUAGE_STORAGE_KEY && event.key !== null) return;
  const next = readPreference();
  if (next === language) return;
  language = next;
  listeners.forEach((notify) => notify());
}
function subscribe(notify: () => void): () => void {
  if (listeners.size === 0) window.addEventListener("storage", storageChanged);
  listeners.add(notify);
  return () => {
    listeners.delete(notify);
    if (listeners.size === 0)
      window.removeEventListener("storage", storageChanged);
  };
}

/** Translate application messages only. Source values and saved prose remain original. */
export function translate(
  message: string,
  values?: MessageValues,
  selected: Language = language,
): string {
  const pattern =
    selected === "ru" && Object.prototype.hasOwnProperty.call(messages, message)
      ? messages[message]
      : message;
  return pattern.replace(/\{(\w+)\}/g, (placeholder, key: string) =>
    values && Object.prototype.hasOwnProperty.call(values, key)
      ? String(values[key])
      : placeholder,
  );
}
export function useI18n() {
  const selected = useSyncExternalStore(
    subscribe,
    getLanguage,
    () => "en" as Language,
  );
  const t = useCallback(
    (message: string, values?: MessageValues) =>
      translate(message, values, selected),
    [selected],
  );
  return {
    language: selected,
    locale: selected === "ru" ? ("ru-RU" as const) : ("en-US" as const),
    t,
    setLanguage,
  };
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const { language: selected } = useI18n();
  useEffect(() => {
    document.documentElement.lang = selected;
  }, [selected]);
  return children;
}

export function LanguageSwitch() {
  const { language: selected, t } = useI18n();
  return (
    <button
      type="button"
      className="language-switch"
      onClick={() => setLanguage(selected === "en" ? "ru" : "en")}
      aria-label={
        selected === "en" ? "Switch to Russian" : "Переключить на английский"
      }
      title={t("Interface language")}
      data-language={selected}
    >
      <span lang="en" className={selected === "en" ? "active" : ""}>
        EN
      </span>
      <span aria-hidden="true" className="language-divider">
        /
      </span>
      <span lang="ru" className={selected === "ru" ? "active" : ""}>
        RU
      </span>
    </button>
  );
}
