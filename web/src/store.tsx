import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, type Alert, type Status } from "./api";
import { clearing, errorText, isUnacked, precedence, type ClearingState } from "./format";

export type SocketState = "connecting" | "open" | "closed";

interface LiveEvent {
  type: string;
  alert?: Alert;
  deep?: boolean;
}

type Channel = "alerts" | "deep" | "sources" | "items";

interface Store {
  status: Status | null;
  statusError: string | null;
  alerts: Alert[] | null;
  alertsError: string | null;
  socket: SocketState;
  versions: Record<Channel, number>;
  /** alert id → when its clearing stamp landed in this session (drives the one authored motion). */
  landed: Record<number, number>;
  refreshStatus: () => Promise<void>;
  refreshAlerts: () => Promise<void>;
  patchAlert: (a: Alert) => void;
}

const StoreContext = createContext<Store | null>(null);
const NowContext = createContext<number>(Date.now());

export function useStore(): Store {
  const s = useContext(StoreContext);
  if (!s) throw new Error("useStore outside StoreProvider");
  return s;
}

/** Source id → readable site name (without the SIM suffix; the EXERCISE strip already says so). */
export function useSourceName(): (id: string) => string {
  const { status } = useStore();
  return useMemo(() => {
    const names = new Map<string, string>();
    for (const s of status?.sources ?? []) names.set(s.id, s.name.replace(/\s*\(SIM\)\s*$/i, ""));
    return (id: string) => names.get(id) ?? id;
  }, [status]);
}

/** A clock that ticks once a second, isolated so only time-aware parts re-render. */
export const useNow = () => useContext(NowContext);

function NowProvider({ children }: { children: ReactNode }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  return <NowContext.Provider value={now}>{children}</NowContext.Provider>;
}

function useLiveSocket(onEvent: (e: LiveEvent) => void): SocketState {
  const handler = useRef(onEvent);
  useEffect(() => {
    handler.current = onEvent;
  }, [onEvent]);
  const [state, setState] = useState<SocketState>("connecting");
  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry: number | undefined;
    let attempts = 0;
    let stopped = false;
    const open = () => {
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${window.location.host}/ws`);
      socket.onopen = () => {
        attempts = 0;
        setState("open");
      };
      socket.onmessage = (m) => {
        try {
          handler.current(JSON.parse(String(m.data)) as LiveEvent);
        } catch {
          /* a malformed frame is dropped, never evaluated */
        }
      };
      socket.onclose = () => {
        if (stopped) return;
        setState("closed");
        attempts += 1;
        retry = window.setTimeout(open, Math.min(10_000, 800 * 2 ** Math.min(attempts, 4)));
      };
    };
    open();
    return () => {
      stopped = true;
      window.clearTimeout(retry);
      socket?.close();
    };
  }, []);
  return state;
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [alertsError, setAlertsError] = useState<string | null>(null);
  const [versions, setVersions] = useState<Record<Channel, number>>({ alerts: 0, deep: 0, sources: 0, items: 0 });
  const [landed, setLanded] = useState<Record<number, number>>({});
  const previous = useRef<Map<number, ClearingState> | null>(null);

  const bump = useCallback((...channels: Channel[]) => {
    setVersions((v) => {
      const next = { ...v };
      for (const c of channels) next[c] += 1;
      return next;
    });
  }, []);

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await api.status());
      setStatusError(null);
    } catch (e) {
      setStatusError(errorText(e));
    }
  }, []);

  const refreshAlerts = useCallback(async () => {
    try {
      setAlerts(await api.alerts());
      setAlertsError(null);
    } catch (e) {
      setAlertsError(errorText(e));
    }
  }, []);

  const patchAlert = useCallback((a: Alert) => {
    setAlerts((list) => {
      if (!list) return list;
      const i = list.findIndex((x) => x.id === a.id);
      if (i === -1) return [a, ...list];
      const next = list.slice();
      next[i] = a;
      return next;
    });
  }, []);

  const onEvent = useCallback(
    (e: LiveEvent) => {
      switch (e.type) {
        case "alert_new":
        case "alert_updated":
          if (e.alert?.id) patchAlert(e.alert);
          bump(...((e.deep ? ["alerts", "deep"] : ["alerts"]) as Channel[]));
          break;
        case "item_gone":
          if (e.alert?.id) patchAlert(e.alert);
          bump("alerts", "items");
          break;
        case "deep_pass":
          bump("deep");
          void refreshAlerts();
          break;
        case "kill_switch":
          void refreshStatus();
          break;
        case "descriptor":
          bump("sources");
          break;
        case "item":
        case "item_edited":
          bump("items");
          break;
        default:
          break;
      }
    },
    [bump, patchAlert, refreshAlerts, refreshStatus],
  );

  const socket = useLiveSocket(onEvent);

  // A message logged UNCLEARED whose verdict arrives while the console is open gets its stamp landed in place.
  // Layout effect: the landing class must be set before the browser paints the new stamp, or it flashes once.
  useLayoutEffect(() => {
    if (!alerts) return;
    const prev = previous.current;
    const next = new Map<number, ClearingState>();
    const now = Date.now();
    const fresh: Record<number, number> = {};
    for (const a of alerts) {
      const state = clearing(a).state;
      next.set(a.id, state);
      if (prev?.get(a.id) === "UNCLEARED" && state !== "UNCLEARED") fresh[a.id] = now;
    }
    previous.current = next;
    if (Object.keys(fresh).length) setLanded((l) => ({ ...l, ...fresh }));
  }, [alerts]);

  useEffect(() => {
    void refreshStatus();
    const s = window.setInterval(refreshStatus, 5000);
    const a = window.setInterval(refreshAlerts, 30_000);
    return () => {
      window.clearInterval(s);
      window.clearInterval(a);
    };
  }, [refreshStatus, refreshAlerts]);

  useEffect(() => {
    if (socket === "open" || socket === "connecting") void refreshAlerts();
  }, [socket, refreshAlerts]);

  // The tab title carries the count of unacknowledged FLASH and IMMEDIATE traffic.
  useEffect(() => {
    const urgent = (alerts ?? []).filter((a) => isUnacked(a) && precedence(a.severity).rank <= 1).length;
    document.title = urgent ? `(${urgent}) Libertas · Forum` : "Libertas · Forum";
  }, [alerts]);

  const value = useMemo<Store>(
    () => ({ status, statusError, alerts, alertsError, socket, versions, landed, refreshStatus, refreshAlerts, patchAlert }),
    [status, statusError, alerts, alertsError, socket, versions, landed, refreshStatus, refreshAlerts, patchAlert],
  );
  return (
    <StoreContext.Provider value={value}>
      <NowProvider>{children}</NowProvider>
    </StoreContext.Provider>
  );
}
