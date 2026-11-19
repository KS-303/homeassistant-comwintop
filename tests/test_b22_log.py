"""Hardware-log summary must never export hostnames or claim frame freshness."""

from scripts.analyze_rtu_log import summarize


def test_rtu_log_summary_uses_bounded_pairs_and_redacts_payloads():
    lines = [
        "2026-11-18 09:11:15.546+01:00 DEBUG [tmodbus.raw_traffic] RTU sent: 02 03 00 20 00 02 C5 F2\n",
        "2026-11-18 09:11:15.574+01:00 DEBUG [tmodbus.raw_traffic] RTU recv: 02 03 04 00 DE 00 DA 28 92\n",
        "2026-11-18 09:11:30.577+01:00 DEBUG [tmodbus.raw_traffic] RTU sent: 02 03 00 20 00 02 C5 F2\n",
        "2026-11-18 09:11:45.603+01:00 DEBUG [tmodbus.raw_traffic] RTU sent: 02 03 00 20 00 02 C5 F2\n",
        "2026-11-18 09:11:45.631+01:00 DEBUG [tmodbus.raw_traffic] RTU recv: 02 03 04 00 DE 00 DA 28 92\n",
    ]
    report = summarize(lines)
    assert report["requests"] == 3
    assert report["recorded_responses"] == 2
    assert report["candidate_pairs"] == 2
    assert report["missing_or_unmatched_requests"] == 1
    assert report["orphan_responses"] == 0
    assert report["median_pair_latency_ms"] == 28
    assert "127.0.0.1" not in str(report)
    assert "00 DE" not in str(report)
