"""MTA Flint 구매공고(Purchasing) 수집기.

https://www.mtaflint.org/purchasing — robots.txt 상 /purchasing 은 차단되어 있지 않음
(Disallow: /wp-admin/ 만 존재, 확인일 2026-08-06).

페이지 구조: Gravity Forms 문의 양식 안의 체크박스 목록(`input.gfield-choice-input`)에
"RFP - 2026-05 Construction of Memorial Park" 형식의 값으로 현재 진행 중인 RFP/IFB 목록이 담겨 있다.
개별 공고마다 별도의 정적 URL은 없음(문의 양식 제출 후 파일이 제공되는 구조) — 원본URL은
목록 페이지 자체를 사용한다 (없는 URL을 지어내지 않는다: §0-3 원칙 1).
"""
import re

import requests
from bs4 import BeautifulSoup

from . import common

INSTITUTION = "MTA Flint"
URL = "https://www.mtaflint.org/purchasing"
USER_AGENT = "H2BusRadarUSCollector/1.0 (+https://github.com/; procurement monitoring)"
TIMEOUT = 30

_CHOICE_PATTERN = re.compile(
    r"^(?P<type>RFP|IFB|RFQ|ITB|RFI)\s*-\s*(?P<num>[\w./-]+)\s+(?P<title>.+)$",
    re.IGNORECASE,
)


def fetch_html(timeout=TIMEOUT):
    resp = requests.get(URL, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def _extract_choice_values(html):
    soup = BeautifulSoup(html, "html.parser")
    values = []
    seen = set()
    for inp in soup.select("input.gfield-choice-input[value]"):
        val = (inp.get("value") or "").strip()
        if val and val not in seen:
            seen.add(val)
            values.append(val)
    return values


def parse_notices(html, run_date):
    rows = []
    for val in _extract_choice_values(html):
        m = _CHOICE_PATTERN.match(val)
        if m:
            notice_no = f"{m.group('type').upper()}-{m.group('num')}"
            title = m.group("title").strip()
        else:
            notice_no = ""
            title = val

        row = {
            "확인일": run_date,
            "기관": INSTITUTION,
            "공고번호": notice_no or common.fallback_notice_number(title),
            "제목": title,
            "품목구분": common.classify_item_type(title),
            "연료": common.classify_fuel(title),
            "대수": common.extract_bus_count(title),
            "예산금액(USD)": common.extract_budget_usd(title),
            "게시일": "",
            "마감일": "",
            "상태": "진행",
            "낙찰자": "",
            "수집방식": "자동",
            "원본URL": URL,
            "비고": "",
        }
        for key in ("대수", "예산금액(USD)"):
            if row[key] is None:
                row[key] = ""
        rows.append(row)
    return rows


def run(run_date):
    html = fetch_html()
    common.save_raw_html(INSTITUTION, run_date, html)
    return parse_notices(html, run_date)


if __name__ == "__main__":
    from datetime import date

    for r in run(date.today().isoformat()):
        print(r)
