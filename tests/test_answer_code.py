import pytest

from benchmarks.answer_code import checksum, decode, encode, scenario_order

GROUPS = {"pilot": [["a1", "a2", "a3", "a4", "a5"], ["b1", "b2", "b3", "b4", "b5"]]}
LABELS = {"a1": "necessary", "a2": "unnecessary", "a3": "uncertain", "a4": "skip", "b1": "necessary"}


def test_encode_produces_documented_layout() -> None:
    code = encode(GROUPS["pilot"], LABELS, "pilot", programmer=False)
    lines = code.splitlines()
    assert lines[0] == "V1-P-L"
    assert lines[1] == "01:1230- 02:1----"
    assert lines[-1] == f"CHK {checksum('1230-1----'):02d}"


def test_round_trip_keeps_answers_and_background() -> None:
    decoded = decode(encode(GROUPS["pilot"], LABELS, "pilot", programmer=True), GROUPS)
    assert decoded.labels == LABELS
    assert decoded.programmer is True
    assert decoded.task_set == "pilot"


def test_decode_tolerates_reflowed_whitespace() -> None:
    code = encode(GROUPS["pilot"], LABELS, "pilot", programmer=None)
    assert decode("  " + code.replace("\n", "   ") + "\n", GROUPS).labels == LABELS


def test_a_single_misread_digit_is_caught() -> None:
    code = encode(GROUPS["pilot"], LABELS, "pilot", programmer=False)
    misread = code.replace("01:1230-", "01:1220-")
    with pytest.raises(ValueError, match="checksum"):
        decode(misread, GROUPS)


@pytest.mark.parametrize(
    "text",
    ["01:12345 CHK 10", "V1-P-L 01:11111 CHK 10", "V1-P-L 02:11111 01:11111 CHK 10", "V1-X-L 01:11111 02:11111 CHK 1"],
)
def test_malformed_codes_are_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        decode(text, GROUPS)


def test_scenario_order_follows_dataset_order_not_pilot_list_order() -> None:
    assert scenario_order(["c1", "c1", "c2", "c3"], ["c3", "c1"], "pilot") == ["c1", "c3"]
    assert scenario_order(["c1", "c2"], ["c2"], "full") == ["c1", "c2"]
