import { ArrowLeft } from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { api, type Alert } from "../api";
import { AckMark, Empty, ErrorNote, Loading, PrecedenceTag, Stamp, tiltFor } from "../components";
import {
  ago,
  clearing,
  compareMessages,
  isUnacked,
  istDay,
  istTime,
  msgNo,
  sameIstDay,
  sourceLabel,
} from "../format";
import { href, readPref, replaceRoute, useMedia, writePref } from "../hooks";
import { useNow, useStore } from "../store";
import { Voucher } from "./Voucher";

type Filter = "all" | "unack" | "backfill";
const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "unack", label: "Unacknowledged" },
  { id: "backfill", label: "Backfill" },
];
const LANDING_MS = 1600;

function MessageRow({ a, selected, landing, now }: { a: Alert; selected: boolean; landing: boolean; now: number }) {
  const c = clearing(a);
  const to = href(["log", a.item_id]);
  return (
    <li>
      <a
        href={to}
        data-msg={a.item_id}
        className={`msg${selected ? " is-selected" : ""}${isUnacked(a) ? " is-unacked" : ""}${a.deleted ? " is-gone" : ""}`}
        aria-current={selected ? "true" : undefined}
        onClick={(e) => {
          e.preventDefault();
          replaceRoute(to);
        }}
      >
        <AckMark status={a.status} />
        <PrecedenceTag severity={a.severity} />
        <span className="msg-dtg">
          <span className="mono msg-time">{istTime(a.first_seen)}</span>
          <span className="msg-age">{sameIstDay(a.first_seen, now) ? ago(a.first_seen, now) : istDay(a.first_seen)}</span>
        </span>
        <span className="msg-subject">
          <span className="msg-title">{a.title}</span>
          <span className="msg-meta">
            <span className="mono">{msgNo(a.item_id)}</span>
            <span>{sourceLabel(a.source_name)}</span>
            <span className="mono">{a.author ?? "unknown"}</span>
            {a.deleted ? <span className="msg-gone">Removed from site</span> : null}
          </span>
        </span>
        <span className="msg-clear">
          <Stamp state={c.state} landing={landing} tilt={tiltFor(a.id)} />
        </span>
      </a>
    </li>
  );
}

function SourceStrip() {
  const { status } = useStore();
  const now = useNow();
  if (!status) return null;
  return (
    <section className="health" aria-labelledby="health-title">
      <h2 id="health-title" className="health-title">
        Sources
      </h2>
      <ul className="health-list">
        {status.sources.map((s) => {
          const h = s.health ?? {};
          const ok = h.state === "watching";
          const d = h.descriptor;
          let descriptor = "Descriptor not yet read";
          if (d) {
            if (d.result !== "RECEIVED") descriptor = `Descriptor ${d.result.toLowerCase()}`;
            else if (d.private) descriptor = "Descriptor received · client auth";
            else descriptor = `Descriptor received${d.pow_enabled ? " · PoW defence on" : ""}${d.intro_points ? ` · ${d.intro_points} intro points` : ""}`;
          }
          return (
            <li key={s.id}>
              <a href="#/sources" className="health-cell">
                <span className="health-name">{sourceLabel(s.name)}</span>
                <span className={`health-state${ok ? "" : " is-bad"}`}>
                  <span className="health-dot" aria-hidden />
                  {ok ? "Watching" : h.state ?? "Starting"}
                </span>
                <span className="health-line">
                  Pulse {h.last_pulse_at ? ago(h.last_pulse_at, now) : "pending"}
                  {h.last_pulse_s ? <span className="mono"> · {h.last_pulse_s.toFixed(1)} s</span> : null}
                </span>
                <span className="health-line">{descriptor}</span>
                <span className="health-line">
                  <span className="mono">{s.items}</span> posts captured
                </span>
              </a>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function LogView({ selectedId }: { selectedId: number | null }) {
  const { alerts, alertsError, refreshAlerts, landed, patchAlert } = useStore();
  const now = useNow();
  const wide = useMedia("(min-width: 761px)");
  const [filter, setFilter] = useState<Filter>(() => {
    const f = readPref("logFilter");
    return f === "unack" || f === "backfill" ? f : "all";
  });
  const listRef = useRef<HTMLOListElement>(null);

  useEffect(() => writePref("logFilter", filter), [filter]);

  const groups = useMemo(() => {
    const list = alerts ?? [];
    const live = list.filter((a) => a.status !== "historical").sort(compareMessages);
    const backfill = list.filter((a) => a.status === "historical").sort(compareMessages);
    return { live, all: [...live, ...backfill], unack: live.filter(isUnacked), backfill };
  }, [alerts]);

  const rows = groups[filter];
  const explicit = selectedId !== null ? (alerts ?? []).find((a) => a.item_id === selectedId) : undefined;
  const selected = explicit ?? (wide && selectedId === null ? rows[0] : undefined);

  const move = useCallback(
    (delta: number) => {
      if (!rows.length) return;
      const i = selected ? rows.findIndex((r) => r.id === selected.id) : -1;
      const next = rows[Math.min(rows.length - 1, Math.max(0, i + delta))];
      replaceRoute(href(["log", next.item_id]));
      window.requestAnimationFrame(() => {
        listRef.current?.querySelector<HTMLAnchorElement>(`[data-msg="${next.item_id}"]`)?.focus();
      });
    },
    [rows, selected],
  );

  const onKey = async (e: KeyboardEvent<HTMLOListElement>) => {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === "ArrowDown" || e.key === "j") {
      e.preventDefault();
      move(1);
    } else if (e.key === "ArrowUp" || e.key === "k") {
      e.preventDefault();
      move(-1);
    } else if ((e.key === "a" || e.key === "A") && selected && isUnacked(selected)) {
      e.preventDefault();
      try {
        patchAlert(await api.ack(selected.id));
      } catch {
        /* the voucher's Acknowledge button reports errors; the shortcut stays silent */
      }
    }
  };

  const landingFor = (id: number) => !!landed[id] && now - landed[id] < LANDING_MS;
  const showVoucherOnly = !wide && !!selected;

  return (
    <div className={`log-view${showVoucherOnly ? " is-reading" : ""}`}>
      <section className="log" aria-labelledby="log-title">
        <header className="log-head">
          <h1 id="log-title">Message log</h1>
          <div className="seg" role="group" aria-label="Which messages to show">
            {FILTERS.map((f) => (
              <button key={f.id} type="button" className="seg-btn" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
                {f.label}
                <span className="seg-n mono">{groups[f.id].length}</span>
              </button>
            ))}
          </div>
        </header>

        <div className="log-cols" aria-hidden>
          <span />
          <span>Precedence</span>
          <span>DTG, IST</span>
          <span>Subject</span>
          <span className="log-cols-end">Clearing</span>
        </div>

        <div className="log-scroll">
          {alertsError && !alerts ? (
            <ErrorNote error={alertsError} retry={refreshAlerts} />
          ) : !alerts ? (
            <Loading label="Opening the message log" />
          ) : rows.length === 0 ? (
            <Empty title={filter === "unack" ? "Nothing awaits acknowledgement" : filter === "backfill" ? "No backfill entries" : "No messages yet"}>
              {filter === "unack"
                ? "Every live message has been acknowledged. New traffic appears here the moment it is logged."
                : filter === "backfill"
                  ? "Posts older than 24 hours at first sight are logged here, so a new source never floods the duty officer."
                  : "Libertas is watching its sources. A message is logged here within seconds of a matching post."}
            </Empty>
          ) : (
            <ol className="msg-list" ref={listRef} onKeyDown={onKey} aria-label="Messages, highest precedence first">
              {rows.map((a, i) => (
                <Fragment key={a.id}>
                  {filter === "all" && i === groups.live.length && i > 0 && (
                    <li className="msg-divider" role="presentation">
                      <span>Backfill</span> Posted more than a day before Libertas first saw them: logged, never paged.
                    </li>
                  )}
                  <MessageRow a={a} selected={selected?.id === a.id} landing={landingFor(a.id)} now={now} />
                </Fragment>
              ))}
            </ol>
          )}
        </div>
        <p className="log-keys">
          <kbd>↑</kbd> <kbd>↓</kbd> move · <kbd>A</kbd> acknowledge · stamps are the deep lane's verdict
        </p>
        <SourceStrip />
      </section>

      <div className="voucher-pane">
        {showVoucherOnly && (
          <a className="back" href="#/log">
            <ArrowLeft size={16} aria-hidden /> Message log
          </a>
        )}
        {selected ? (
          <Voucher key={selected.id} alert={selected} landing={landingFor(selected.id)} />
        ) : selectedId !== null && alerts ? (
          <Empty title={`No message for ${msgNo(selectedId)}`}>It may have been filtered out or not logged yet.</Empty>
        ) : wide ? (
          <Empty title="Select a message">Its facts, leads and next actions open here.</Empty>
        ) : null}
      </div>
    </div>
  );
}
