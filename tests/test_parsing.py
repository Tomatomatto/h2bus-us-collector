"""판별 규칙(품목·연료·대수) 및 CSV 병합 규칙 테스트."""
from datetime import date

from collectors import common


# ---------------------------------------------------------------------------
# §3-3: 대수 추출 함정 4종 (패치오더에 명시된 실제 발생 오류)
# ---------------------------------------------------------------------------

def test_bus_count_trap_foot_length():
    assert common.extract_bus_count("PURCHASE OF 40-FOOT BUSES") is None


def test_bus_count_trap_capacity():
    assert common.extract_bus_count("Charging station with up to 120 buses capacity") is None


def test_bus_count_trap_fleet_of():
    assert common.extract_bus_count("MTA operates a fleet of 322 buses") is None


def test_bus_count_correct_extraction():
    assert common.extract_bus_count("ONE (1) 60-FOOT BUS") == 1


def test_bus_count_standalone_simple():
    assert common.extract_bus_count("Purchase of 5 buses") == 5


def test_bus_count_no_false_positive_from_notice_number():
    # "2026-12" 는 공고번호/연도 조각이지 대수가 아니다 -- 실사용(OCTA) 중 발견된 오탐 사례
    assert common.extract_bus_count("RFP 2026-12 Hydrogen Fuel Cell Bus Purchase") is None


def test_bus_count_none_when_absent():
    assert common.extract_bus_count("Lease of Mini Vans") is None


def test_bus_count_none_for_empty():
    assert common.extract_bus_count("") is None
    assert common.extract_bus_count(None) is None


def test_bus_count_multiple_units_parenthetical():
    assert common.extract_bus_count("TWO (2) 40-FOOT LOW FLOOR BUSES") == 2


# ---------------------------------------------------------------------------
# 연료 판별
# ---------------------------------------------------------------------------

def test_fuel_hydrogen_keyword():
    assert common.classify_fuel("Purchase of Fuel Cell Electric Buses (FCEB)") == "수소"


def test_fuel_hydrogen_h2():
    assert common.classify_fuel("H2 bus procurement") == "수소"


def test_fuel_battery_keyword():
    assert common.classify_fuel("Battery Electric Bus (BEB) Purchase") == "배터리"


def test_fuel_unknown_when_absent():
    assert common.classify_fuel("Purchase/Lease of Transit Tires") == "불명"


def test_fuel_hydrogen_priority_when_both_present():
    text = "Mixed fleet: battery electric buses and hydrogen fuel cell buses"
    assert common.classify_fuel(text) == "수소"


# ---------------------------------------------------------------------------
# 품목구분
# ---------------------------------------------------------------------------

def test_item_type_bus():
    assert common.classify_item_type("ONE (1) 60-FOOT BUS") == "버스"


def test_item_type_charging_infra():
    assert common.classify_item_type("Design-Build of Hydrogen Fueling Station") == "충전인프라"


def test_item_type_parts():
    assert common.classify_item_type("Purchase/Lease of Transit Tires") == "부품"


def test_item_type_service():
    assert common.classify_item_type("Consulting Study for Fleet Maintenance") == "용역"


def test_item_type_default_other():
    assert common.classify_item_type("Construction of Memorial Park") == "기타"


# ---------------------------------------------------------------------------
# 예산금액(USD)
# ---------------------------------------------------------------------------

def test_budget_extraction_with_dollar_sign():
    assert common.extract_budget_usd("Estimated cost: $1,234,567") == 1234567


def test_budget_extraction_absent():
    assert common.extract_budget_usd("Purchase of Engine Replacement") is None


def test_budget_extraction_usd_prefix():
    assert common.extract_budget_usd("Budget USD 500,000 for this contract") == 500000


# ---------------------------------------------------------------------------
# 공고번호 fallback
# ---------------------------------------------------------------------------

def test_fallback_notice_number_truncates_to_40_chars():
    title = "A" * 60
    assert common.fallback_notice_number(title) == "A" * 40


# ---------------------------------------------------------------------------
# 날짜 정규화
# ---------------------------------------------------------------------------

def test_parse_date_us_slash_format():
    assert common.parse_date_flexible("08/15/2026") == "2026-08-15"


def test_parse_date_invalid_returns_none():
    assert common.parse_date_flexible("not a date") is None


def test_parse_date_none_for_empty():
    assert common.parse_date_flexible("") is None


# ---------------------------------------------------------------------------
# §3-4: 누적 병합 규칙
# ---------------------------------------------------------------------------

def _row(**kwargs):
    base = {col: "" for col in common.NOTICE_COLUMNS}
    base.update(kwargs)
    return base


def test_merge_adds_new_record():
    existing = []
    new = [_row(확인일="2026-08-06", 기관="MTA Flint", 공고번호="IFB-2026-02", 제목="Tires", 상태="진행")]
    merged = common.merge_notices(existing, new, today=date(2026, 8, 6))
    assert len(merged) == 1
    assert merged[0]["공고번호"] == "IFB-2026-02"


def test_merge_updates_only_deadline_and_status_keeps_check_date():
    existing = [
        _row(확인일="2026-01-01", 기관="MTA Flint", 공고번호="IFB-2026-02", 제목="Tires",
             상태="진행", 마감일="")
    ]
    new = [_row(확인일="2026-08-06", 기관="MTA Flint", 공고번호="IFB-2026-02", 제목="Tires (변경됨)",
                상태="낙찰", 마감일="2026-08-01", 낙찰자="ACME Corp")]
    merged = common.merge_notices(existing, new, today=date(2026, 8, 6))
    assert len(merged) == 1
    row = merged[0]
    assert row["확인일"] == "2026-01-01"  # 확인일은 유지
    assert row["제목"] == "Tires"  # 제목은 갱신 대상 아님
    assert row["마감일"] == "2026-08-01"
    assert row["상태"] == "낙찰"
    assert row["낙찰자"] == "ACME Corp"


def test_merge_does_not_delete_rows():
    existing = [
        _row(확인일="2026-01-01", 기관="MTA Flint", 공고번호="A", 제목="Old", 상태="마감"),
    ]
    new = [_row(확인일="2026-08-06", 기관="MTA Flint", 공고번호="B", 제목="New", 상태="진행")]
    merged = common.merge_notices(existing, new, today=date(2026, 8, 6))
    numbers = {r["공고번호"] for r in merged}
    assert numbers == {"A", "B"}


def test_merge_no_duplicate_on_rerun_with_identical_data():
    existing = [
        _row(확인일="2026-01-01", 기관="MTA Flint", 공고번호="A", 제목="Old", 상태="진행"),
    ]
    new = [_row(확인일="2026-08-06", 기관="MTA Flint", 공고번호="A", 제목="Old", 상태="진행")]
    merged = common.merge_notices(existing, new, today=date(2026, 8, 6))
    assert len(merged) == 1


def test_apply_deadline_expiry_marks_past_deadline_as_closed():
    rows = [_row(기관="MTA Flint", 공고번호="A", 상태="진행", 마감일="2026-01-01")]
    common.apply_deadline_expiry(rows, today=date(2026, 8, 6))
    assert rows[0]["상태"] == "마감"


def test_apply_deadline_expiry_leaves_future_deadline_open():
    rows = [_row(기관="MTA Flint", 공고번호="A", 상태="진행", 마감일="2099-01-01")]
    common.apply_deadline_expiry(rows, today=date(2026, 8, 6))
    assert rows[0]["상태"] == "진행"


# ---------------------------------------------------------------------------
# run_log 조용한 실패 감지
# ---------------------------------------------------------------------------

def test_check_consecutive_zero_true_when_two_zero_runs():
    rows = [
        common.make_run_log_entry("OCTA", "성공", 0, "", when="2026-08-01 00:00:00"),
        common.make_run_log_entry("OCTA", "성공", 0, "", when="2026-08-08 00:00:00"),
    ]
    assert common.check_consecutive_zero(rows, "OCTA", n=2) is True


def test_check_consecutive_zero_false_when_recent_run_has_results():
    rows = [
        common.make_run_log_entry("OCTA", "성공", 0, "", when="2026-08-01 00:00:00"),
        common.make_run_log_entry("OCTA", "성공", 3, "", when="2026-08-08 00:00:00"),
    ]
    assert common.check_consecutive_zero(rows, "OCTA", n=2) is False


def test_check_consecutive_zero_ignores_other_institution():
    rows = [
        common.make_run_log_entry("OCTA", "성공", 0, "", when="2026-08-01 00:00:00"),
        common.make_run_log_entry("OCTA", "성공", 0, "", when="2026-08-08 00:00:00"),
    ]
    assert common.check_consecutive_zero(rows, "MTA Flint", n=2) is False


# ---------------------------------------------------------------------------
# 신규 수소버스 공고 감지 (이메일 알림 트리거)
# ---------------------------------------------------------------------------

def test_find_new_hydrogen_bus_rows_detects_new_match():
    existing = []
    new = [_row(기관="MTA Flint", 공고번호="A", 품목구분="버스", 연료="수소")]
    found = common.find_new_hydrogen_bus_rows(existing, new)
    assert len(found) == 1
    assert found[0]["공고번호"] == "A"


def test_find_new_hydrogen_bus_rows_ignores_already_known():
    existing = [_row(기관="MTA Flint", 공고번호="A", 품목구분="버스", 연료="수소")]
    new = [_row(기관="MTA Flint", 공고번호="A", 품목구분="버스", 연료="수소")]
    assert common.find_new_hydrogen_bus_rows(existing, new) == []


def test_find_new_hydrogen_bus_rows_requires_both_fuel_and_item_type():
    existing = []
    new = [
        _row(기관="MTA Flint", 공고번호="B", 품목구분="부품", 연료="수소"),  # 버스 아님
        _row(기관="MTA Flint", 공고번호="C", 품목구분="버스", 연료="불명"),  # 수소 아님
    ]
    assert common.find_new_hydrogen_bus_rows(existing, new) == []


def test_find_new_hydrogen_bus_rows_empty_when_no_new_rows():
    assert common.find_new_hydrogen_bus_rows([], []) == []
