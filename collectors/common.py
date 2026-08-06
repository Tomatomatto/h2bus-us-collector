"""CSV I/O, 누적 병합, 품목/연료/대수 판별 규칙 공통 모듈.

이 모듈은 순수 함수로만 구성한다 (네트워크 접근 없음).
네트워크 접근은 각 기관별 수집기(mta_flint.py, octa.py)에서만 수행한다.
"""
import csv
import re
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- §3-2: notices.csv 열 이름 · 순서 고정 (15개) ---
NOTICE_COLUMNS = [
    "확인일",
    "기관",
    "공고번호",
    "제목",
    "품목구분",
    "연료",
    "대수",
    "예산금액(USD)",
    "게시일",
    "마감일",
    "상태",
    "낙찰자",
    "수집방식",
    "원본URL",
    "비고",
]

RUN_LOG_COLUMNS = ["실행시각", "기관", "상태", "수집건수", "오류메시지"]

VALID_STATUS = {"진행", "마감", "낙찰", "취소"}


# ---------------------------------------------------------------------------
# CSV 읽기/쓰기
# ---------------------------------------------------------------------------

def load_notices(path):
    """notices.csv를 읽어 dict 리스트로 반환한다. 파일이 없으면 빈 리스트."""
    path = Path(path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def save_notices(path, rows):
    """15개 열을 정확한 이름·순서로 기록한다 (UTF-8 BOM 포함)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=NOTICE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            normalized = {col: row.get(col, "") for col in NOTICE_COLUMNS}
            for col in normalized:
                if normalized[col] is None:
                    normalized[col] = ""
            writer.writerow(normalized)


def load_run_log(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def append_run_log(path, entry):
    """run_log.csv에 한 행을 추가한다 (기존 이력을 지우지 않음)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_LOG_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow({col: entry.get(col, "") for col in RUN_LOG_COLUMNS})


def make_run_log_entry(institution, status, count, error_message, when=None):
    when = when or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "실행시각": when,
        "기관": institution,
        "상태": status,
        "수집건수": count,
        "오류메시지": error_message,
    }


def check_consecutive_zero(run_log_rows, institution, n=2):
    """해당 기관의 최근 n회 '성공' 실행이 모두 수집건수 0이면 True."""
    rows = [r for r in run_log_rows if r.get("기관") == institution and r.get("상태") == "성공"]
    if len(rows) < n:
        return False
    recent = rows[-n:]
    for r in recent:
        try:
            if int(r.get("수집건수") or 0) != 0:
                return False
        except ValueError:
            return False
    return True


# ---------------------------------------------------------------------------
# 누적 병합 (§3-4)
# ---------------------------------------------------------------------------

def _key(row):
    return (row.get("기관", ""), row.get("공고번호", ""))


def apply_deadline_expiry(rows, today=None):
    """마감일이 지난 '진행' 건의 상태를 '마감'으로 바꾼다 (in-place)."""
    today = today or date.today()
    for row in rows:
        deadline = (row.get("마감일") or "").strip()
        if not deadline or row.get("상태") != "진행":
            continue
        try:
            d = datetime.strptime(deadline, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d < today:
            row["상태"] = "마감"
    return rows


def merge_notices(existing_rows, new_rows, today=None):
    """§3-4 누적 규칙: 신규 건 추가, 기존 건은 마감일·상태·낙찰자만 갱신, 삭제 없음."""
    merged = [dict(r) for r in existing_rows]
    index = {_key(r): i for i, r in enumerate(merged)}

    for new in new_rows:
        key = _key(new)
        if key in index:
            i = index[key]
            existing = merged[i]
            if (new.get("마감일") or "").strip():
                existing["마감일"] = new["마감일"]
            if (new.get("상태") or "").strip():
                existing["상태"] = new["상태"]
            if (new.get("낙찰자") or "").strip():
                existing["낙찰자"] = new["낙찰자"]
        else:
            merged.append(dict(new))
            index[key] = len(merged) - 1

    apply_deadline_expiry(merged, today)
    return merged


# ---------------------------------------------------------------------------
# 판별 규칙 (§3-3)
# ---------------------------------------------------------------------------

_BUS_KEYWORDS = re.compile(r"\b(bus|buses|coach|coaches|transit vehicle)\b", re.IGNORECASE)
_CHARGING_KEYWORDS = re.compile(
    r"\b(charging|fueling station|hydrogen station|dispenser)\b", re.IGNORECASE
)
_PARTS_KEYWORDS = re.compile(r"\b(parts?|components?|tires?|battery pack)\b", re.IGNORECASE)
_SERVICE_KEYWORDS = re.compile(r"\b(service|consulting|study|maintenance)\b", re.IGNORECASE)

_HYDROGEN_KEYWORDS = re.compile(r"\b(hydrogen|fuel cell|fceb|h2)\b", re.IGNORECASE)
_BATTERY_KEYWORDS = re.compile(r"\b(battery electric|beb|bev)\b", re.IGNORECASE)


def classify_item_type(text):
    """품목구분: 버스 > 충전인프라 > 부품 > 용역 > 기타 (§3-3 우선순위)."""
    text = text or ""
    if _BUS_KEYWORDS.search(text):
        return "버스"
    if _CHARGING_KEYWORDS.search(text):
        return "충전인프라"
    if _PARTS_KEYWORDS.search(text):
        return "부품"
    if _SERVICE_KEYWORDS.search(text):
        return "용역"
    return "기타"


def classify_fuel(text):
    """연료: 수소/배터리 키워드 둘 다 있으면 수소 우선, 없으면 불명."""
    text = text or ""
    has_h2 = bool(_HYDROGEN_KEYWORDS.search(text))
    has_batt = bool(_BATTERY_KEYWORDS.search(text))
    if has_h2:
        return "수소"
    if has_batt:
        return "배터리"
    return "불명"


# --- 대수(§3-3 함정) ---

_FOOT_PATTERN = re.compile(r"\d+\s*-?\s*(?:foot|ft)\b", re.IGNORECASE)
_CAPACITY_CONTEXT = re.compile(r"\bcapacity\b", re.IGNORECASE)
_FLEET_CONTEXT = re.compile(r"\bfleet\s+of\b", re.IGNORECASE)
_BUS_UNIT_WORD = re.compile(r"\b(?:bus|buses|coach|coaches|transit vehicles?)\b", re.IGNORECASE)

# "ONE (1) 60-FOOT BUS" 형태만 매칭한다 — 괄호 바로 앞에 영문 수사(number word)가 있는
# 경우로 한정해, "Contract (2026) ... bus ..." 같은 임의의 괄호 숫자를 대수로 오탐하지 않는다.
_NUMBER_WORD_PAREN_QTY_PATTERN = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|qty|quantity)\s*\(\s*(\d+)\s*\)",
    re.IGNORECASE,
)
_STANDALONE_QTY_PATTERN = re.compile(
    r"\b(\d+)\s+(?:buses|bus|coaches|coach|transit vehicles?)\b", re.IGNORECASE
)


def _in_span(pos, spans):
    return any(s <= pos < e for s, e in spans)


def extract_bus_count(text):
    """원문에 명시된 구매 대수만 추출한다. 함정(길이/용량/보유대수)은 제외, 없으면 None."""
    if not text:
        return None

    foot_spans = [m.span() for m in _FOOT_PATTERN.finditer(text)]

    # 1) "WORD (N) ... BUS" 형태 (예: "ONE (1) 60-FOOT BUS") — 가장 신뢰도 높은 패턴
    for m in _NUMBER_WORD_PAREN_QTY_PATTERN.finditer(text):
        num_start = m.start(1)
        if _in_span(num_start, foot_spans):
            continue
        window_after = text[m.end():m.end() + 60]
        if not _BUS_UNIT_WORD.search(window_after):
            continue
        window_before = text[max(0, m.start() - 80):m.start()]
        if _CAPACITY_CONTEXT.search(window_before) or _FLEET_CONTEXT.search(window_before):
            continue
        return int(m.group(1))

    # 2) "N BUS(ES)" 형태 (단, FOOT/FT·capacity·fleet of 문맥 제외)
    for m in _STANDALONE_QTY_PATTERN.finditer(text):
        num_start = m.start(1)
        if _in_span(num_start, foot_spans):
            continue
        window_before = text[max(0, m.start() - 40):m.start()]
        window_after = text[m.end():m.end() + 40]
        if _CAPACITY_CONTEXT.search(window_before) or _CAPACITY_CONTEXT.search(window_after):
            continue
        if _FLEET_CONTEXT.search(window_before):
            continue
        return int(m.group(1))

    return None


# --- 예산금액(USD) ---

_BUDGET_PATTERN = re.compile(r"(?:\$|USD)\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)


def extract_budget_usd(text):
    """원문에 '$' 또는 'USD'로 명시된 금액만 추출한다 (숫자만, 쉼표 제거). 없으면 None."""
    if not text:
        return None
    m = _BUDGET_PATTERN.search(text)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    return int(value) if value == int(value) else value


# --- 날짜 ---

_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y", "%m-%d-%Y"]


def parse_date_flexible(text):
    """여러 표기 형식을 시도해 YYYY-MM-DD로 정규화한다. 실패하면 None (추정 금지)."""
    if not text:
        return None
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def fallback_notice_number(title):
    """공고번호가 원문에 없을 때: 제목 앞 40자."""
    title = title or ""
    return title[:40]


# ---------------------------------------------------------------------------
# 원문 보존 (raw/{기관}/{날짜}.html)
# ---------------------------------------------------------------------------

def save_raw_html(institution, date_str, html):
    raw_dir = ROOT / "raw" / institution
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{date_str}.html"
    path.write_text(html, encoding="utf-8")
    return path
