import { Check, Copy, PencilLine } from "lucide-react";
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { precedence, prob, shortHash, truthLabel, type ClearingState } from "./format";

/** FLASH / IMMEDIATE / PRIORITY / ROUTINE: the message precedence decides the order of handling. */
export function PrecedenceTag({ severity, className = "" }: { severity: string; className?: string }) {
  const p = precedence(severity);
  return <span className={`prec prec--${p.name.toLowerCase()} ${className}`}>{p.name}</span>;
}

/** Small per-message tilt so stamps read as struck by hand, never as identical badges. */
export const tiltFor = (id: number) => -(0.6 + (id % 5) * 0.42);

/** The deep lane's verdict, struck like a clearing-house stamp. UNCLEARED stays in pencil until the ink lands. */
export function Stamp({
  state,
  size = "sm",
  landing = false,
  tilt = -1.5,
}: {
  state: ClearingState;
  size?: "sm" | "lg";
  landing?: boolean;
  tilt?: number;
}) {
  if (state === "UNCLEARED") {
    return <span className={`stamp stamp--uncleared stamp--${size}`}>Uncleared</span>;
  }
  return (
    <span
      className={`stamp stamp--${state.toLowerCase()} stamp--${size}${landing ? " stamp--landing" : ""}`}
      style={size === "lg" ? ({ "--tilt": `${tilt}deg` } as CSSProperties) : undefined}
    >
      {state === "CLEARED" ? "Cleared" : "Returned"}
    </span>
  );
}

export function AckMark({ status }: { status: string }) {
  if (status === "new") {
    return (
      <span className="ack ack--pending" title="Awaiting acknowledgement">
        <span className="sr">Unacknowledged</span>
      </span>
    );
  }
  if (status === "acknowledged") {
    return (
      <span className="ack ack--done" title="Acknowledged">
        <Check size={14} strokeWidth={2.25} aria-hidden />
        <span className="sr">Acknowledged</span>
      </span>
    );
  }
  return (
    <span className="ack ack--backfill" title="Backfill: older than 24 hours when first seen">
      <span className="sr">Backfill</span>
    </span>
  );
}

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!done) return;
    const t = window.setTimeout(() => setDone(false), 1400);
    return () => window.clearTimeout(t);
  }, [done]);
  return (
    <button
      type="button"
      className="icon-btn"
      aria-label={done ? "Copied" : label}
      title={done ? "Copied" : label}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setDone(true);
        } catch {
          /* clipboard refused: the full value stays visible in the tooltip */
        }
      }}
    >
      {done ? <Check size={13} strokeWidth={2.25} aria-hidden /> : <Copy size={13} aria-hidden />}
    </button>
  );
}

/** A digest or address: shortened in the middle, full value on hover, one-click copy. */
export function HashText({ value, head = 8, tail = 8 }: { value: string | null | undefined; head?: number; tail?: number }) {
  if (!value) return <span className="mono pencil">—</span>;
  return (
    <span className="hash">
      <span className="mono" title={value}>
        {shortHash(value, head, tail)}
      </span>
      <CopyButton value={value} label="Copy full value" />
    </span>
  );
}

export function ViewHeader({ title, latin, children }: { title: string; latin?: string; children?: ReactNode }) {
  return (
    <header className="view-head">
      <h1>
        {title}
        {latin && <span className="latin">{latin}</span>}
      </h1>
      {children && <div className="view-head-aside">{children}</div>}
    </header>
  );
}

export function Section({
  title,
  note,
  tone = "ink",
  children,
  id,
}: {
  title: string;
  note?: ReactNode;
  tone?: "ink" | "pencil";
  children: ReactNode;
  id?: string;
}) {
  return (
    <section className={`sec sec--${tone}`} aria-labelledby={id}>
      <header className="sec-head">
        <h3 id={id}>
          {tone === "pencil" && <PencilLine size={14} aria-hidden className="sec-icon" />}
          {title}
        </h3>
        {note && <span className="sec-note">{note}</span>}
      </header>
      {children}
    </section>
  );
}

export function Facts({ children }: { children: ReactNode }) {
  return <dl className="facts">{children}</dl>;
}

export function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/** A pencilled inference: graded by truth level and probability, never shown in ink. */
export function Lead({ title, truth, p, children }: { title: ReactNode; truth?: string; p?: number; children?: ReactNode }) {
  return (
    <li className="lead">
      <div className="lead-body">
        <p className="lead-title">{title}</p>
        {children}
      </div>
      {(truth || p !== undefined) && (
        <span className="lead-grade">
          {truth && (
            <span title={truthLabel(truth)}>
              {truth} {truthLabel(truth)}
            </span>
          )}
          {p !== undefined && <span className="mono">P {prob(p)}</span>}
        </span>
      )}
    </li>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <p className="state state--loading" role="status">
      <span className="state-dots" aria-hidden />
      {label}
    </p>
  );
}

export function ErrorNote({ error, retry }: { error: string; retry?: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <p>{error}</p>
      {retry && (
        <button type="button" className="btn btn--quiet btn--sm" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state state--empty">
      <p className="state-title">{title}</p>
      {children && <div className="state-body">{children}</div>}
    </div>
  );
}
