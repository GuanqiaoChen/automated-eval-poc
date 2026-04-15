"""
Collects, stores and summarises conversation results from all three
automation strategies (API, Web, Mobile).
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from config.settings import RESULTS_DIR

logger = logging.getLogger(__name__)

Strategy = Literal["api", "web", "mobile"]


@dataclass
class TurnResult:
    message_id: int
    message_text: str
    response_text: str
    strategy: Strategy
    character_id: str
    latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SessionResult:
    session_id: str
    strategy: Strategy
    character_id: str
    started_at: str
    finished_at: str = ""
    turns: list[TurnResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def add_turn(self, turn: TurnResult) -> None:
        self.turns.append(turn)

    def finalise(self) -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()
        successful = [t for t in self.turns if t.error is None]
        failed = [t for t in self.turns if t.error is not None]
        latencies = [t.latency_ms for t in successful]

        self.summary = {
            "total_messages": len(self.turns),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate_pct": round(len(successful) / max(len(self.turns), 1) * 100, 1),
            "avg_latency_ms": round(sum(latencies) / max(len(latencies), 1), 1),
            "min_latency_ms": round(min(latencies, default=0), 1),
            "max_latency_ms": round(max(latencies, default=0), 1),
        }


class ResultHandler:
    """Thread-safe collector that writes results to JSON on disk."""

    def __init__(self, strategy: Strategy, character_id: str) -> None:
        self.session = SessionResult(
            session_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
            strategy=strategy,
            character_id=character_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._output_path: Path | None = None

    # -- public API ------------------------------------------------------------

    def record(self, turn: TurnResult) -> None:
        self.session.add_turn(turn)
        status = "OK" if turn.error is None else f"ERR({turn.error})"
        logger.info(
            "[%s] msg=%d  latency=%.0fms  status=%s",
            self.session.strategy.upper(),
            turn.message_id,
            turn.latency_ms,
            status,
        )

    def save(self) -> Path:
        self.session.finalise()
        filename = f"{self.session.strategy}_{self.session.session_id}.json"
        self._output_path = RESULTS_DIR / filename
        with open(self._output_path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self.session), fh, indent=2, ensure_ascii=False)
        logger.info("Results saved → %s", self._output_path)
        return self._output_path

    def print_summary(self) -> None:
        s = self.session.summary
        if not s:
            self.session.finalise()
            s = self.session.summary

        border = "-" * 56
        print(f"\n{border}")
        print(f"  Strategy   : {self.session.strategy.upper()}")
        print(f"  Character  : {self.session.character_id}")
        print(f"  Messages   : {s['total_messages']}  "
              f"(OK {s['successful']}  ERR {s['failed']})")
        print(f"  Success    : {s['success_rate_pct']}%")
        print(f"  Latency    : avg {s['avg_latency_ms']} ms  "
              f"(min {s['min_latency_ms']} / max {s['max_latency_ms']})")
        if self._output_path:
            print(f"  Report     : {self._output_path}")
        print(border)

        for turn in self.session.turns:
            icon = "OK" if turn.error is None else "ERR"
            preview_q = turn.message_text[:60].replace("\n", " ")
            preview_a = (turn.response_text or "")[:80].replace("\n", " ")
            print(f"\n  {icon} [{turn.message_id:02d}] Q: {preview_q!r}")
            if turn.error:
                print(f"       ERR: {turn.error}")
            else:
                print(f"       A: {preview_a!r}")
        print()
