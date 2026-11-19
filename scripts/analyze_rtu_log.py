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
    matched = []
    unanswered = []
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
        if frame.group("direction") == "sent":
            tx.append((stamp, data[0], data[1] if len(data) > 1 else None))
            by_unit[data[0]] += 1
        else:
            rx.append((stamp, data[0]))
            # Sequential capture correlation only; NOT a Modbus freshness proof.
            if len(matched) + len(unanswered) < len(tx):
                for candidate in tx[len(matched) + len(unanswered):]:
                    if candidate[1] == data[0]:
                        matched.append((stamp - candidate[0]).total_seconds() * 1000)
                        break
                    unanswered.append(candidate[0].isoformat())
    return {
        "requests": len(tx),
        "recorded_responses": len(rx),
        "candidate_pairs": len(matched),
        "unmatched_requests_lower_bound": max(0, len(tx) - len(matched)),
        "median_pair_latency_ms": sorted(matched)[len(matched) // 2] if matched else None,
        "max_pair_latency_ms": round(max(matched), 2) if matched else None,
        "by_unit_requests": dict(sorted(by_unit.items())),
        "warning": "RX/TX log pairing is an estimate, not proof of frame freshness",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="Local HA log export (never commit it)")
    args = parser.parse_args()
    with args.log.open(encoding="utf-8", errors="replace") as handle:
        print(json.dumps(summarize(handle), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
