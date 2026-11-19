"""Summarize a local ComWinTop RTU traffic log without exporting private frames.

The output is aggregate-only. A missing captured RTU recv line is *not* proof
that a device never transmitted; logger resets can also hide frame records.
"""

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
STAMP = re.compile(r"(?P<stamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+[+-]\d{2}:\d{2})")
FRAME = re.compile(r"RTU (?P<direction>sent|recv):\s+(?P<bytes>(?:[0-9A-Fa-f]{2}\s*)+)")


def summarize(lines):
    tx = []
    rx = []
    pending = []
    matched = []
    unanswered = 0
    orphan = 0
    by_unit = Counter()
    for line in lines:
        clean = ANSI.sub("", line)
        time_match, frame = STAMP.search(clean), FRAME.search(clean)
        if time_match is None or frame is None:
            continue
        stamp = datetime.fromisoformat(time_match.group("stamp"))
        data = bytes.fromhex(frame.group("bytes"))
        if not data:
            continue
        # Expire requests before accepting another event. This only
        # estimates missing responses; logger gaps can mimic bus faults.
        expired = [request for request in pending if (stamp - request[0]).total_seconds() > 4.0]
        unanswered += len(expired)
        pending = [request for request in pending if request not in expired]
        if frame.group("direction") == "sent":
            tx.append((stamp, data[0]))
            pending.append((stamp, data[0]))
            by_unit[data[0]] += 1
        else:
            rx.append((stamp, data[0]))
            index = next((i for i, req in enumerate(pending) if req[1] == data[0]), None)
            if index is None:
                orphan += 1
            else:
                request = pending.pop(index)
                matched.append((stamp - request[0]).total_seconds() * 1000)
    return {
        "requests": len(tx),
        "recorded_responses": len(rx),
        "candidate_pairs": len(matched),
        "missing_or_unmatched_requests": unanswered + len(pending),
        "unmatched_at_log_end": len(pending),
        "orphan_responses": orphan,
        "median_pair_latency_ms": sorted(matched)[len(matched) // 2] if matched else None,
        "max_pair_latency_ms": round(max(matched), 2) if matched else None,
        "by_unit_requests": dict(sorted(by_unit.items())),
        "warning": "RX/TX pairing uses a 4 s window; logger gaps and delayed frames can look alike",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="Local HA log export (never commit it)")
    args = parser.parse_args()
    with args.log.open(encoding="utf-8", errors="replace") as handle:
        print(json.dumps(summarize(handle), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
