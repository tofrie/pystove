"""Require precisely the six deferred failures, with no failures or skipped tests."""

from pathlib import Path
import sys
import xml.etree.ElementTree as ET

KNOWN = {
    "test_command_rejects_http_error_status[post-command]",
    "test_command_rejects_http_error_status[get-command]",
    "test_get_live_data_rejects_missing_body",
    "test_get_live_data_length_guard_matches_legacy_index_ranges",
    "test_get_live_data_rejects_undersized_accepted_body",
    "test_self_test_empty_replies_obey_retry_budget",
}


def verify(path):
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    if (
        not cases or next(root.iter("failure"), None) is not None
        or next(root.iter("error"), None) is not None
    ):
        raise ValueError("Test failure, strict XPASS, error, or empty test report")
    skipped = [case for case in cases if case.find("skipped") is not None]
    if len(skipped) != 6 or {case.get("name") for case in skipped} != KNOWN:
        raise ValueError("Expected exactly the six known xfails")
    if any(
        case.get("classname") != "tests.test_known_failures"
        or case.find("skipped").get("type") != "pytest.xfail"
        for case in skipped
    ):
        raise ValueError("Unexpected skipped test")
    return len(cases) - 6


if __name__ == "__main__":
    print(f"{verify(Path(sys.argv[1]))} passed, exactly 6 known xfails, 0 XPASS")
