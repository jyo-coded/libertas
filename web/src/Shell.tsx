import {
  FolderOpen,
  Inbox,
  Landmark,
  Network,
  Power,
  Projector,
  RadioTower,
  Scale,
  Search,
  ShieldCheck,
  ShieldExclamationPoint,
  Stamp,
  UserSearch,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import { errorText, isUnacked, istTime, istWeekday, precedence, PRECEDENCE_ORDER, seconds } from "./format";
import { readPref, writePref } from "./hooks";
import { useNow, useStore } from "./store";

export interface NavItem {
  id: string;
  label: string;
  latin: string;
  icon: LucideIcon;
}

export const NAV: NavItem[] = [
  { id: "log", label: "Message log", latin: "Vigiles", icon: Inbox },
  { id: "incidents", label: "Incidents", latin: "Codex", icon: FolderOpen },
  { id: "actors", label: "Actors", latin: "Stilus", icon: UserSearch },
  { id: "graph", label: "Graph", latin: "Nexus", icon: Network },
  { id: "money", label: "Money", latin: "Moneta", icon: Landmark },
  { id: "explorer", label: "Explorer", latin: "Interpres", icon: Search },
  { id: "evidence", label: "Evidence", latin: "Tabularium", icon: Stamp },
  { id: "sources", label: "Sources", latin: "Speculatores", icon: RadioTower },
  { id: "lex", label: "Policy & audit", latin: "Lex", icon: Scale },
];

function ExerciseStrip() {
  return (
    <div className="exercise" role="note" aria-label="Exercise: all data is simulated">
      <span className="exercise-words" aria-hidden>
        <span>Exercise</span>
        <span>Exercise</span>
        <span>Exercise</span>
      </span>
      <span className="exercise-text">
        Every site, post, person and wallet on this console is simulated (ShadowNet). No real victims and no real criminal
        sites.
      </span>
    </div>
  );
}

function KillSwitch({ engaged }: { engaged: boolean }) {
  const { refreshStatus } = useStore();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!confirming) return;
    const t = window.setTimeout(() => setConfirming(false), 8000);
    return () => window.clearTimeout(t);
  }, [confirming]);

  const act = async () => {
    setBusy(true);
    setError(null);
    try {
      if (engaged) await api.resume();
      else await api.kill("Halted from the Forum console");
      await refreshStatus();
      setConfirming(false);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  if (confirming) {
    return (
      <div className="kill-confirm" role="group" aria-label={engaged ? "Confirm resume" : "Confirm halt"}>
        <span>{engaged ? "Resume collection?" : "Halt all collection?"}</span>
        <button type="button" className={`btn btn--sm ${engaged ? "btn--primary-light" : "btn--danger"}`} onClick={act} disabled={busy}>
          {busy ? "Working" : engaged ? "Resume" : "Halt now"}
        </button>
        <button type="button" className="btn btn--sm btn--on-rail" onClick={() => setConfirming(false)} disabled={busy}>
          Cancel
        </button>
        {error && <span className="kill-error">{error}</span>}
      </div>
    );
  }
  return (
    <button type="button" className={`kill${engaged ? " kill--engaged" : ""}`} onClick={() => setConfirming(true)}>
      <Power size={15} strokeWidth={2.25} aria-hidden />
      <span>{engaged ? "Resume collection" : "Halt collection"}</span>
    </button>
  );
}

function DisplayToggle() {
  const [projector, setProjector] = useState(() => readPref("display") === "projector");
  useEffect(() => {
    document.documentElement.dataset.display = projector ? "projector" : "desk";
    writePref("display", projector ? "projector" : "desk");
  }, [projector]);
  return (
    <button
      type="button"
      className="mast-toggle"
      aria-pressed={projector}
      onClick={() => setProjector((p) => !p)}
      title="Larger type and stronger rules for a projector"
    >
      <Projector size={16} aria-hidden />
      <span>Projector</span>
    </button>
  );
}

function Masthead() {
  const { status, statusError, alerts, socket } = useStore();
  const now = useNow();

  const unacked = useMemo(() => {
    const c: Record<string, number> = { FLASH: 0, IMMEDIATE: 0, PRIORITY: 0, ROUTINE: 0 };
    for (const a of alerts ?? []) if (isUnacked(a)) c[precedence(a.severity).name] += 1;
    return c;
  }, [alerts]);

  const sources = status?.sources ?? [];
  const watching = sources.filter((s) => s.health?.state === "watching").length;
  const halted = !!status?.kill_engaged;

  let collection: { tone: string; text: string };
  if (statusError) collection = { tone: "bad", text: "Libertas not answering" };
  else if (!status) collection = { tone: "idle", text: "Connecting" };
  else if (halted) collection = { tone: "bad", text: "Collection halted" };
  else if (watching < sources.length) collection = { tone: "warn", text: `Collecting · ${watching}/${sources.length} sources` };
  else collection = { tone: "ok", text: `Collecting · ${watching}/${sources.length} sources` };

  return (
    <header className="mast">
      <a className="brand" href="#/log" aria-label="Libertas Forum, message log">
        <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden>
          <rect x="1" y="1" width="30" height="30" rx="5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M12 9.5v12.5h8.5" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="square" />
        </svg>
        <span className="brand-text">
          <span className="brand-name">
            Libertas <span className="brand-forum">Forum</span>
          </span>
          <span className="brand-unit">{status?.unit ?? "Cyber Crime Wing"}</span>
        </span>
      </a>

      <div className="mast-counts" aria-label="Unacknowledged messages by precedence" aria-live="polite">
        <span className="mast-label">Unacknowledged</span>
        <ul>
          {PRECEDENCE_ORDER.map((name) => (
            <li key={name} className={unacked[name] ? "" : "is-zero"}>
              <a href="#/log" className={`count count--${name.toLowerCase()}`}>
                <span className="count-name">{name}</span>
                <span className="count-n">{unacked[name]}</span>
              </a>
            </li>
          ))}
        </ul>
      </div>

      <div className="mast-state">
        <span className={`collect collect--${collection.tone}`}>
          <span className="collect-dot" aria-hidden />
          {collection.text}
        </span>
        <span className="mast-sub">
          {socket === "open" ? "Live feed connected" : socket === "connecting" ? "Live feed connecting" : "Live feed reconnecting"}
          {status?.ttd && (
            <>
              {" · "}
              <span title={`Median time from posting to alert across ${status.ttd.n} posts; p95 ${seconds(status.ttd.p95_s)}`}>
                Time to detect <b className="mono">{seconds(status.ttd.median_s)}</b>
              </span>
            </>
          )}
        </span>
      </div>

      <div className="mast-clock" aria-label="Indian Standard Time">
        <span className="clock-time mono">{istTime(now)}</span>
        <span className="clock-zone">IST · {istWeekday(now)}</span>
      </div>

      <div className="mast-actions">
        <DisplayToggle />
        <KillSwitch engaged={halted} />
      </div>
    </header>
  );
}

function Rail({ active }: { active: string }) {
  const { status } = useStore();
  const audit = status?.audit;
  return (
    <nav className="rail" aria-label="Sections">
      <ul className="rail-list">
        {NAV.map((n) => {
          const Icon = n.icon;
          const current = n.id === active;
          return (
            <li key={n.id}>
              <a href={`#/${n.id}`} className={`rail-item${current ? " is-current" : ""}`} aria-current={current ? "page" : undefined} title={`${n.label} (${n.latin})`}>
                <Icon size={18} strokeWidth={1.75} aria-hidden />
                <span className="rail-label">{n.label}</span>
                <span className="rail-latin">{n.latin}</span>
              </a>
            </li>
          );
        })}
      </ul>
      <div className="rail-foot">
        {audit ? (
          <a href="#/lex" className={`rail-audit${audit.ok ? "" : " is-broken"}`}>
            {audit.ok ? <ShieldCheck size={16} aria-hidden /> : <ShieldExclamationPoint size={16} aria-hidden />}
            <span>
              {audit.ok ? "Audit chain intact" : `Audit chain broken at #${audit.broken_at_seq}`}
              <span className="rail-audit-n mono">{audit.entries_checked} entries</span>
            </span>
          </a>
        ) : null}
        {status?.lex && (
          <p className="rail-policy">
            Policy: {status.lex.mode} mode · {status.lex.allowlist_size} allowlisted onions
          </p>
        )}
      </div>
    </nav>
  );
}

export function Shell({ active, children }: { active: string; children: ReactNode }) {
  return (
    <div className="app">
      <button type="button" className="skip" onClick={() => document.getElementById("main")?.focus()}>
        Skip to content
      </button>
      <ExerciseStrip />
      <Masthead />
      <div className="frame">
        <Rail active={active} />
        <main id="main" className="main" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
