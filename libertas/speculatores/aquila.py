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
import json
import random
import sqlite3
import time
from dataclasses import dataclass
from datetime import timedelta

from ..common.timeutil import now, now_iso
from ..config import Settings
from ..lex.policy import Lex
from .adapters import ADAPTERS, ItemRef, ParseDrift
from .fetcher import FetchResult, WatchSession
from .heartbeat import Heartbeat, deadline_interval, nearest_deadline
from .walls import Wall, detect_wall

PRIO_NEW, PRIO_RETRY, PRIO_REVISIT = 0, 5, 10
THROTTLE_S, THROTTLE_GAP_S, THROTTLE_MAX_GAP_S = 300.0, 3.0, 30.0


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
                 pulsus=None, log=print, heartbeat_onion: str | None = None):
        self.conn, self.lex, self.settings, self.pipeline = conn, lex, settings, pipeline
        self.sources = {s.id: s for s in sources}
        self.pulsus, self.log = pulsus, log
        self.sessions: dict[str, WatchSession] = {}
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=settings.max_queue)
        self.inflight: set[tuple[str, str]] = set()
        self._seq = itertools.count()
        self.health = {s.id: {"state": "starting", "pulses": 0, "consecutive_failures": 0, "last_pulse_at": None,
                              "last_pulse_s": None, "last_outcome": None, "descriptor": None,
                              "isolation_id": None, "wall": None, "deadline_watch": None} for s in sources}
        self.cooldown_until: dict[str, float] = {}
        self.throttle: dict[str, tuple[float, float]] = {}
        self._spacing: dict[str, asyncio.Lock] = {}
        self._last_request: dict[str, float] = {}
        self._throttle_set: dict[str, float] = {}
        self.heartbeat = Heartbeat(onion=heartbeat_onion or "")
        self._heartbeat_session: WatchSession | None = None

    # ---------- walls: recognised, recorded, waited out; never solved ----------
    def _hit_wall(self, s: Source, wall: Wall, stage: str) -> None:
        h = self.health[s.id]
        self.cooldown_until[s.id] = time.monotonic() + wall.cooldown_s
        h["state"] = f"{wall.detail}; waiting {wall.cooldown_s} s"
        if wall.kind == "rate_limit":
            # Stay polite for five minutes. A 429 that arrives after we already slowed down doubles the gap
            # (3 s, 6 s, 12 s, up to 30 s). Several 429s from one burst sent before the first one came back count
            # once, so a single burst never jumps straight to the slowest pace.
            t = time.monotonic()
            until, gap = self.throttle.get(s.id, (0.0, 0.0))
            fresh_violation = t < until and t - self._throttle_set.get(s.id, 0.0) > wall.cooldown_s
            if t >= until or not gap:
                gap = THROTTLE_GAP_S
                self._throttle_set[s.id] = t
            elif fresh_violation:
                gap = min(THROTTLE_MAX_GAP_S, gap * 2)
                self._throttle_set[s.id] = t
            self.throttle[s.id] = (t + THROTTLE_S, gap)
            h["throttled_until"] = (now() + timedelta(seconds=THROTTLE_S)).isoformat(timespec="seconds")
            h["throttle_gap_s"] = gap
        episode = h.get("wall")
        if not episode or episode["kind"] != wall.kind:
            h["wall"] = {"kind": wall.kind, "detail": wall.detail, "since": now_iso(), "hits": 1}
            self.pipeline.audit.append("speculatores", "wall_encountered", s.id, wall.kind,
                                       {"stage": stage, "detail": wall.detail, "cooldown_s": wall.cooldown_s})
            self.log(f"{s.id}: {wall.detail} ({stage}); cooling down {wall.cooldown_s} s")
        else:
            episode["hits"] += 1

    def _clear_wall(self, s: Source) -> None:
        h = self.health[s.id]
        ep = h.get("wall")
        if ep:
            h["wall"] = None
            self.pipeline.audit.append("speculatores", "wall_cleared", s.id, ep["kind"],
                                       {"since": ep["since"], "hits": ep["hits"]})
            self.log(f"{s.id}: {ep['kind']} cleared after {ep['hits']} refusals; collection resumes")

    def _throttled(self, s: Source) -> bool:
        return time.monotonic() < self.throttle.get(s.id, (0.0, 0.0))[0]

    async def _wait_cooldown(self, s: Source) -> None:
        left = self.cooldown_until.get(s.id, 0) - time.monotonic()
        if left > 0:
            await asyncio.sleep(left)
        until, gap = self.throttle.get(s.id, (0.0, 0.0))
        if time.monotonic() < until:  # after a rate limit: space requests out instead of bursting again
            async with self._spacing.setdefault(s.id, asyncio.Lock()):
                wait = gap - (time.monotonic() - self._last_request.get(s.id, 0.0))
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last_request[s.id] = time.monotonic()

    def _deadline_pulse(self, s: Source) -> float:
        """Deadline-aware scheduling: a countdown nearing its end tightens this source's pulse."""
        base = self.settings.pulse_interval_s
        if not ADAPTERS[s.adapter].pulse_is_complete:
            return base
        rows = [(r["id"], r["title"], json.loads(r["extra_json"] or "{}")) for r in self.conn.execute(
            "SELECT id, title, extra_json FROM items WHERE source_id=? AND deleted_at IS NULL AND extra_json LIKE ?",
            (s.id, '%"deadline"%'))]
        near = nearest_deadline(rows)
        if not near:
            self.health[s.id]["deadline_watch"] = None
            return base
        interval = deadline_interval(near["remaining_s"], base)
        self.health[s.id]["deadline_watch"] = {**near, "interval_s": interval}
        return interval

    async def run(self) -> None:
        for s in self.sources.values():
            self.sessions[s.id] = WatchSession(s.id, self.settings, self.lex)
            self.health[s.id]["isolation_id"] = self.sessions[s.id].isolation_id
        tasks = [self._pulse_loop(s) for s in self.sources.values()]
        tasks += [self._worker() for _ in range(self.settings.max_concurrent_fetches)]
        tasks.append(self._revisit_loop())
        if self.heartbeat.onion:
            tasks.append(self._heartbeat_loop())
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
            await self._wait_cooldown(s)
            session = self.sessions[s.id]
            res = await session.get(adapter.pulse_url(s.base), conditional=False)
            self.pipeline.record_capture(s.id, res, "pulse")
            h.update(last_pulse_at=now_iso(), last_pulse_s=res.elapsed_s, last_outcome=res.outcome,
                     pulses=h["pulses"] + 1, isolation_id=session.isolation_id)
            if self.lex.kill_engaged():  # severed or refused by the switch: that is a halt, not a failing source
                h["state"] = "halted (kill switch)"
                continue
            wall = None if res.refused or res.error else detect_wall(res)
            if wall:
                self._hit_wall(s, wall, "pulse")
                if wall.kind != "rate_limit":
                    await session.rotate()
                continue
            if res.ok:
                self._clear_wall(s)
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
            await asyncio.sleep(self._deadline_pulse(s) * jitter * backoff)

    async def _worker(self) -> None:
        while True:
            prio, _, s, ref, role, attempt = await self.queue.get()
            key, requeued = (s.id, ref.key), False
            try:
                if self.lex.kill_engaged():
                    continue
                if role == "revisit" and self._throttled(s):
                    continue  # revisits wait until the site's rate limit has passed
                await self._wait_cooldown(s)
                adapter = ADAPTERS[s.adapter]
                res = await self.sessions[s.id].get(ref.url)
                sha = self.pipeline.record_capture(s.id, res, role)
                if res.refused:
                    self.pipeline.touch_checked(s.id, ref.key)
                    continue
                wall = None if res.error else detect_wall(res)
                if wall:  # the item stays pending; the next pulse after the cooldown asks for it again
                    self._hit_wall(s, wall, role)
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
                    drift = self.health[s.id].get("drift") or {"since": now_iso(), "count": 0}
                    drift.update(count=drift["count"] + 1, last_error=str(exc)[:160])
                    self.health[s.id]["drift"] = drift
                    continue
                self.health[s.id]["drift"] = None  # pages parse again: the layout drift is over
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
                if s and not self._throttled(s):  # a rate-limited site's few requests go to its feed and new posts
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

    async def _heartbeat_loop(self) -> None:
        """Read the canary onion on the normal pulse cadence; each new minute seen gives a true time to detect."""
        url = f"http://{self.heartbeat.onion}.onion/"
        self._heartbeat_session = WatchSession("heartbeat", self.settings, self.lex)
        hb = self.heartbeat
        await asyncio.sleep(random.uniform(1, 4))
        while True:
            if self.lex.kill_engaged():
                hb.state = "halted (kill switch)"
                await asyncio.sleep(3)
                continue
            before = hb.state
            res: FetchResult = await self._heartbeat_session.get(url)
            if res.ok:
                lag = hb.observe(res.body.decode("utf-8", "replace"), time.time())
                if lag is not None:
                    self.pipeline.bus.publish({"type": "heartbeat", "lag_s": lag})
            else:
                hb.failed()
                if hb.consecutive_failures % 3 == 0:
                    await self._heartbeat_session.rotate()
            hb.refresh(time.time())
            if hb.state != before and before != "starting":
                self.pipeline.audit.append("speculatores", "heartbeat_state", "heartbeat", hb.state, {"was": before})
                self.log(f"heartbeat: {before} -> {hb.state}")
            jitter = 1 + random.uniform(-self.settings.pulse_jitter, self.settings.pulse_jitter)
            await asyncio.sleep(self.settings.pulse_interval_s * jitter)

    async def sever(self) -> int:
        """Kill switch: Lex already refuses every new request; this also cuts the ones already on the wire."""
        cut = 0
        for s_id, session in self.sessions.items():
            cut += await session.sever()
            self.health[s_id]["state"] = "halted (kill switch)"
        if self._heartbeat_session:
            cut += await self._heartbeat_session.sever()
        if cut:
            self.pipeline.audit.append("lex", "kill_switch_severed", "collection", "cut", {"requests_in_flight": cut})
        return cut

    async def close(self) -> None:
        if self._heartbeat_session:
            await self._heartbeat_session.aclose()
        for session in self.sessions.values():
            await session.aclose()
