"""Aquila: the pulse scheduler (blueprint §11.2).

* One warm, isolated watch session per source (keep-alive over its own Tor circuit).
* Pulse polling of each source's cheapest signal (RSS/JSON/list page) every ~20 s with ±20% jitter.
* Event-triggered bursts: a new item on the pulse is fetched immediately (highest priority).
* Revisits of recent items to catch edits and deletions quickly.
* Pulsus descriptor probes on a slower cycle.
* Back-off and circuit rotation on repeated failures. Kill switch honoured everywhere.
"""
from __future__ import annotations

import asyncio
import itertools
import random
import sqlite3
from dataclasses import dataclass
from datetime import timedelta

from ..common.timeutil import now, now_iso
from ..config import Settings
from ..lex.policy import Lex
from .adapters import ADAPTERS, ItemRef, ParseDrift
from .fetcher import WatchSession

PRIO_NEW, PRIO_RETRY, PRIO_REVISIT = 0, 5, 10


@dataclass
class Source:
    id: str
    name: str
    kind: str
    onion: str
    adapter: str
    simulated: bool = True
    private: bool = False

    @property
    def base(self) -> str:
        return f"http://{self.onion}.onion"


class Aquila:
    def __init__(self, conn: sqlite3.Connection, lex: Lex, settings: Settings, pipeline, sources: list[Source],
                 pulsus=None, log=print):
        self.conn, self.lex, self.settings, self.pipeline = conn, lex, settings, pipeline
        self.sources = {s.id: s for s in sources}
        self.pulsus, self.log = pulsus, log
        self.sessions: dict[str, WatchSession] = {}
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=settings.max_queue)
        self.inflight: set[tuple[str, str]] = set()
        self._seq = itertools.count()
        self.health = {s.id: {"state": "starting", "pulses": 0, "consecutive_failures": 0, "last_pulse_at": None,
                              "last_pulse_s": None, "last_outcome": None, "descriptor": None,
                              "isolation_id": None} for s in sources}

    async def run(self) -> None:
        for s in self.sources.values():
            self.sessions[s.id] = WatchSession(s.id, self.settings, self.lex)
            self.health[s.id]["isolation_id"] = self.sessions[s.id].isolation_id
        tasks = [self._pulse_loop(s) for s in self.sources.values()]
        tasks += [self._worker() for _ in range(self.settings.max_concurrent_fetches)]
        tasks.append(self._revisit_loop())
        if self.pulsus:
            tasks.append(self._pulsus_loop())
        await asyncio.gather(*tasks)

    def _enqueue(self, prio: int, source: Source, ref: ItemRef, role: str, attempt: int = 0) -> None:
        key = (source.id, ref.key)
        if key in self.inflight:
            return
        try:
            self.queue.put_nowait((prio, next(self._seq), source, ref, role, attempt))
            self.inflight.add(key)
        except asyncio.QueueFull:
            self.log("queue full; dropping fetch (will be retried by a later pulse)")

    async def _pulse_loop(self, s: Source) -> None:
        adapter, h = ADAPTERS[s.adapter], self.health[s.id]
        await asyncio.sleep(random.uniform(0, 3))
        while True:
            if self.lex.kill_engaged():
                h["state"] = "halted (kill switch)"
                await asyncio.sleep(3)
                continue
            session = self.sessions[s.id]
            res = await session.get(adapter.pulse_url(s.base), conditional=False)
            self.pipeline.record_capture(s.id, res, "pulse")
            h.update(last_pulse_at=now_iso(), last_pulse_s=res.elapsed_s, last_outcome=res.outcome,
                     pulses=h["pulses"] + 1, isolation_id=session.isolation_id)
            if res.ok:
                h["consecutive_failures"], h["state"] = 0, "watching"
                try:
                    refs = adapter.parse_pulse(s.base, res)
                except Exception as exc:  # layout drift: log it, never guess past it
                    refs = None
                    h["state"] = "parse drift"
                    self.pipeline.audit.append("speculatores", "parse_drift", s.id, "warn",
                                               {"stage": "pulse", "error": f"{type(exc).__name__}: {exc}"[:200]})
                if refs is not None:
                    for ref in self.pipeline.triage(s, refs, complete=adapter.pulse_is_complete):
                        self._enqueue(PRIO_NEW, s, ref, "detail")
                    if not adapter.pulse_is_complete:
                        for ref in self.pipeline.absence_suspects(s, refs):
                            self._enqueue(PRIO_NEW, s, ref, "verify_absence")
            else:
                h["consecutive_failures"] += 1
                h["state"] = f"degraded: {res.refused or res.error or res.status}"[:160]
                if h["consecutive_failures"] % 3 == 0:
                    await session.rotate()
                    self.log(f"{s.id}: rotated to a fresh circuit after {h['consecutive_failures']} failures")
            backoff = min(4, 1 + h["consecutive_failures"])
            jitter = 1 + random.uniform(-self.settings.pulse_jitter, self.settings.pulse_jitter)
            await asyncio.sleep(self.settings.pulse_interval_s * jitter * backoff)

    async def _worker(self) -> None:
        while True:
            prio, _, s, ref, role, attempt = await self.queue.get()
            key, requeued = (s.id, ref.key), False
            try:
                if self.lex.kill_engaged():
                    continue
                adapter = ADAPTERS[s.adapter]
                res = await self.sessions[s.id].get(ref.url)
                sha = self.pipeline.record_capture(s.id, res, role)
                if res.refused:
                    self.pipeline.touch_checked(s.id, ref.key)
                    continue
                if res.error or res.status >= 500 or res.status == 0:
                    if attempt < 3:
                        await asyncio.sleep(2 * (attempt + 1))
                        self.queue.put_nowait((PRIO_RETRY, next(self._seq), s, ref, role, attempt + 1))
                        requeued = True
                    continue
                try:
                    content = adapter.parse_detail(s.base, ref, res)
                except ParseDrift as exc:
                    self.pipeline.audit.append("speculatores", "parse_drift", s.id, "warn",
                                               {"stage": "detail", "url": ref.url[:200], "error": str(exc)[:200]})
                    continue
                if content is None:
                    self.pipeline.mark_deleted(s, ref, sha)
                else:
                    self.pipeline.on_content(s, ref, content, sha)
            except Exception as exc:
                self.log(f"worker error on {ref.url}: {type(exc).__name__}: {exc}")
            finally:
                if not requeued:
                    self.inflight.discard(key)
                self.queue.task_done()

    async def _revisit_loop(self) -> None:
        while True:
            await asyncio.sleep(max(5.0, self.settings.revisit_interval_s / 3))
            if self.lex.kill_engaged():
                continue
            t = now()
            recent = (t - timedelta(seconds=self.settings.revisit_window_s)).isoformat(timespec="milliseconds")
            stale = (t - timedelta(seconds=self.settings.revisit_interval_s)).isoformat(timespec="milliseconds")
            rows = self.conn.execute(
                "SELECT source_id, item_key, url, kind, title, author, posted_at FROM items WHERE deleted_at IS NULL "
                "AND content_hash IS NOT NULL AND COALESCE(posted_at, first_seen) >= ? AND "
                "(last_checked IS NULL OR last_checked < ?) ORDER BY last_checked LIMIT 30", (recent, stale)).fetchall()
            for r in rows:
                s = self.sources.get(r["source_id"])
                if s:
                    self._enqueue(PRIO_REVISIT, s, ItemRef(r["item_key"], r["url"], r["kind"], r["title"] or "",
                                                           r["author"] or "", r["posted_at"]), "revisit")

    async def _pulsus_loop(self) -> None:
        await asyncio.sleep(1)
        while True:
            for s in self.sources.values():
                if self.lex.kill_engaged():
                    break
                obs = await self.pulsus.probe(s.onion)
                self.pipeline.record_descriptor(s.id, obs)
                self.health[s.id]["descriptor"] = obs.as_dict()
                await asyncio.sleep(1)
            await asyncio.sleep(self.settings.pulsus_interval_s)

    async def close(self) -> None:
        for session in self.sessions.values():
            await session.aclose()
