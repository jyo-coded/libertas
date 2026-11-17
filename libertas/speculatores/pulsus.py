"""Pulsus: the content-free sensor (blueprint §11.13).

Asks Tor for a service's descriptor (HSFETCH), listens for HS_DESC events, then decrypts the cached
descriptor with the public onion address, exactly as any Tor client does before connecting. No connection
is made to the service itself, and no page content is ever touched.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass

from .torproc import ControlError, TorControl


@dataclass
class DescriptorObservation:
    onion: str
    result: str  # RECEIVED | NOT_FOUND | TIMEOUT | ERROR
    seconds: float
    hsdirs_asked: int = 0
    intro_points: int | None = None
    pow_enabled: bool | None = None
    pow_effort: int | None = None
    single_onion: bool | None = None
    private: bool | None = None
    error: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _inspect_descriptor(onion: str, raw: str) -> dict:
    """Runs in a worker thread: stem's v3 decryption is CPU-bound pure Python."""
    from stem.descriptor.hidden_service import HiddenServiceDescriptorV3

    desc = HiddenServiceDescriptorV3(raw.encode() + (b"" if raw.endswith("\n") else b"\n"))
    try:
        inner = desc.decrypt(onion + ".onion")
    except Exception as exc:  # inner layer encrypted to authorised clients only (restricted discovery)
        return {"private": True, "error": f"inner layer not readable without client credentials ({type(exc).__name__})"}
    lines = str(inner).splitlines()
    pow_line = next((l for l in lines if l.startswith("pow-params")), None)
    parts = pow_line.split() if pow_line else []
    return {"private": False, "intro_points": len(inner.introduction_points), "pow_enabled": bool(pow_line),
            "pow_effort": int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None,
            "single_onion": "single-onion-service" in lines}


class Pulsus:
    def __init__(self, control_port: int, cookie_path):
        self._cmd = TorControl(control_port, cookie_path)
        self._evt = TorControl(control_port, cookie_path)
        self._waiters: dict[str, asyncio.Queue] = {}
        self._task: asyncio.Task | None = None

    async def start(self) -> "Pulsus":
        await self._cmd.connect()
        await self._evt.connect()
        await self._evt.subscribe("HS_DESC")
        self._task = asyncio.create_task(self._pump())
        return self

    async def _pump(self) -> None:
        while True:
            try:
                line = await self._evt.next_event()
            except ControlError:
                return
            parts = line.split()  # 650 HS_DESC <Action> <Address> <AuthType> <HsDir> ...
            if len(parts) >= 4:
                queue = self._waiters.get(parts[3])
                if queue:
                    queue.put_nowait((time.perf_counter(), parts[2], line))

    async def probe(self, onion: str, timeout: float = 60.0) -> DescriptorObservation:
        queue: asyncio.Queue = asyncio.Queue()
        self._waiters[onion] = queue
        started = time.perf_counter()
        requested = failed = 0
        reasons: set[str] = set()
        last_event = started
        try:
            reply = await self._cmd.command(f"HSFETCH {onion}")
            if not reply[-1].startswith("250"):
                return DescriptorObservation(onion, "ERROR", 0.0, error=reply[-1][:200])
            while True:
                elapsed = time.perf_counter() - started
                if elapsed > timeout:
                    return DescriptorObservation(onion, "TIMEOUT", round(elapsed, 2), requested)
                try:
                    ts, action, line = await asyncio.wait_for(queue.get(), 0.5)
                except asyncio.TimeoutError:
                    # Tor asks responsible directories one after another; only call it "not found" once
                    # every request so far has failed and no new one has started for a few seconds.
                    if requested and failed >= requested and (failed >= 6 or time.perf_counter() - last_event > 4.0):
                        return DescriptorObservation(onion, "NOT_FOUND", round(last_event - started, 2), requested,
                                                     error=",".join(sorted(reasons)))
                    continue
                last_event = ts
                if action == "REQUESTED":
                    requested += 1
                elif action == "FAILED":
                    failed += 1
                    if "REASON=" in line:
                        reasons.add(line.split("REASON=", 1)[1].split()[0])
                elif action == "RECEIVED":
                    obs = DescriptorObservation(onion, "RECEIVED", round(ts - started, 2), max(requested, 1))
                    await self._read_descriptor(onion, obs)
                    return obs
        except ControlError as exc:
            return DescriptorObservation(onion, "ERROR", round(time.perf_counter() - started, 2), requested,
                                         error=str(exc)[:200])
        finally:
            self._waiters.pop(onion, None)

    async def _read_descriptor(self, onion: str, obs: DescriptorObservation) -> None:
        try:
            raw = await self._cmd.getinfo(f"hs/client/desc/id/{onion}")
            info = await asyncio.to_thread(_inspect_descriptor, onion, raw)
        except Exception as exc:
            obs.error = f"descriptor parse failed: {type(exc).__name__}: {exc}"[:200]
            return
        for key, value in info.items():
            setattr(obs, key, value)

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
        await self._cmd.close()
        await self._evt.close()
