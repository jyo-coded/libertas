import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { errorText } from "./format";

// ---------- hash routing (the API serves one page; views live after the #) ----------
export interface Route {
  parts: string[];
  query: URLSearchParams;
}

function parseHash(hash: string): Route {
  const raw = hash.replace(/^#\/?/, "");
  const [path, q = ""] = raw.split("?");
  return {
    parts: path.split("/").filter(Boolean).map((p) => {
      try {
        return decodeURIComponent(p);
      } catch {
        return p;
      }
    }),
    query: new URLSearchParams(q),
  };
}

const subscribeHash = (cb: () => void) => {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
};

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribeHash, () => window.location.hash);
  return useMemo(() => parseHash(hash), [hash]);
}

export function href(parts: (string | number)[], query?: Record<string, string>): string {
  const path = parts.map((p) => encodeURIComponent(String(p))).join("/");
  const q = query ? new URLSearchParams(query).toString() : "";
  return `#/${path}${q ? `?${q}` : ""}`;
}

/** Move without stacking history entries (selection changes inside a view). */
export const replaceRoute = (to: string) => window.location.replace(to);

// ---------- media queries ----------
export function useMedia(query: string): boolean {
  const subscribe = useCallback(
    (cb: () => void) => {
      const m = window.matchMedia(query);
      m.addEventListener("change", cb);
      return () => m.removeEventListener("change", cb);
    },
    [query],
  );
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches);
}

// ---------- display mode (desk or projector), set on <html data-display> ----------
const subscribeDisplay = (cb: () => void) => {
  const mo = new MutationObserver(cb);
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-display"] });
  return () => mo.disconnect();
};

export function useProjector(): boolean {
  return useSyncExternalStore(subscribeDisplay, () => document.documentElement.dataset.display === "projector");
}

// ---------- data loading ----------
export interface Resource<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/** Loads on mount and whenever `deps` change; keeps the last good data while a reload is in flight. */
export function useResource<T>(load: () => Promise<T>, deps: unknown[]): Resource<T> {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({
    data: null,
    error: null,
    loading: true,
  });
  const seq = useRef(0);
  const loader = useRef(load);
  loader.current = load;
  const reload = useCallback(() => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true }));
    loader.current().then(
      (data) => {
        if (id === seq.current) setState({ data, error: null, loading: false });
      },
      (err: unknown) => {
        if (id === seq.current) setState((s) => ({ data: s.data, error: errorText(err), loading: false }));
      },
    );
  }, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(reload, deps);
  return { ...state, reload };
}

// ---------- small local preferences (never required for the page to work) ----------
export function readPref(key: string): string | null {
  try {
    return window.localStorage.getItem(`libertas.${key}`);
  } catch {
    return null;
  }
}

export function writePref(key: string, value: string): void {
  try {
    window.localStorage.setItem(`libertas.${key}`, value);
  } catch {
    /* private window or blocked storage: the preference simply does not persist */
  }
}
