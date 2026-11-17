"""Start and talk to Libertas-owned tor instances.

Uses the official tor binary (Tor Browser's copy in development) with Libertas's own config and data
directories, never the user's browser session. Each instance runs at below-normal priority and exits by
itself when its parent Python process dies (__OwningControllerProcess), so no orphans are left behind.
"""
from __future__ import annotations

import asyncio
import binascii
import os
import subprocess
from pathlib import Path


class ControlError(Exception):
    pass


def list_modules(tor_exe: str) -> dict[str, bool]:
    try:
        out = subprocess.run([tor_exe, "--list-modules"], capture_output=True, text=True, timeout=30,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    mods = {}
    for line in out.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            mods[key.strip()] = value.strip().lower() == "yes"
    return mods


def write_torrc(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def start_tor(tor_exe: str, torrc: Path, log_path: Path) -> subprocess.Popen:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    flags = 0
    if os.name == "nt":
        flags = subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW
    log = open(log_path, "ab")
    return subprocess.Popen([tor_exe, "-f", str(torrc), "__OwningControllerProcess", str(os.getpid())],
                            stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=flags)


class TorControl:
    """Minimal async Tor control-port client (cookie auth)."""

    def __init__(self, port: int, cookie_path: Path, host: str = "127.0.0.1"):
        self.port, self.cookie_path, self.host = port, Path(cookie_path), host
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    async def connect(self, timeout: float = 10.0) -> "TorControl":
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port, limit=8 * 1024 * 1024), timeout)
        cookie = binascii.hexlify(self.cookie_path.read_bytes()).decode()
        reply = await self.command(f"AUTHENTICATE {cookie}")
        if not reply[-1].startswith("250"):
            raise ControlError(f"authentication failed: {reply[-1]}")
        return self

    async def _readline(self) -> str:
        raw = await self.reader.readline()
        if not raw:
            raise ControlError("control connection closed")
        return raw.decode(errors="replace").rstrip("\r\n")

    async def _read_reply(self) -> list[str]:
        lines: list[str] = []
        while True:
            line = await self._readline()
            if len(line) >= 4 and line[3] == "+":
                lines.append(line)
                while True:
                    data = await self._readline()
                    if data == ".":
                        break
                    lines.append(data[1:] if data.startswith("..") else data)
                continue
            lines.append(line)
            if len(line) >= 4 and line[3] == " ":
                return lines

    async def command(self, line: str) -> list[str]:
        async with self._lock:
            self.writer.write((line + "\r\n").encode())
            await self.writer.drain()
            return await self._read_reply()

    async def getinfo(self, key: str) -> str:
        reply = await self.command(f"GETINFO {key}")
        if not reply[-1].startswith("250"):
            raise ControlError(reply[-1])
        first = reply[0]
        if first.startswith("250+"):
            return "\n".join(reply[1:-1])
        prefix = f"250-{key}="
        return first[len(prefix):] if first.startswith(prefix) else first[4:]

    async def subscribe(self, events: str) -> None:
        reply = await self.command(f"SETEVENTS {events}")
        if not reply[-1].startswith("250"):
            raise ControlError(reply[-1])

    async def next_event(self) -> str:
        """For a dedicated event connection after subscribe(): return the next asynchronous event line."""
        while True:
            line = await self._readline()
            if line.startswith("650"):
                return line

    async def close(self) -> None:
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except OSError:
                pass


async def bootstrap_progress(port: int, cookie_path: Path) -> int:
    ctl = await TorControl(port, cookie_path).connect()
    try:
        phase = await ctl.getinfo("status/bootstrap-phase")
    finally:
        await ctl.close()
    for part in phase.split():
        if part.startswith("PROGRESS="):
            return int(part.split("=", 1)[1])
    return 0


async def wait_bootstrapped(port: int, cookie_path: Path, timeout: float = 300.0, log=print) -> float:
    loop = asyncio.get_running_loop()
    started, last = loop.time(), -1
    while True:
        try:
            if Path(cookie_path).exists():
                progress = await bootstrap_progress(port, cookie_path)
                if progress != last:
                    log(f"tor bootstrap {progress}%")
                    last = progress
                if progress >= 100:
                    return round(loop.time() - started, 1)
        except (OSError, ControlError, asyncio.TimeoutError):
            pass
        if loop.time() - started > timeout:
            raise TimeoutError(f"tor did not bootstrap within {timeout:.0f}s")
        await asyncio.sleep(2)
