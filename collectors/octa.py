"""OCTA(Orange County Transportation Authority) 조달공고 수집기.

W-02 진단(OCTA_DIAGNOSIS.md) 결과: 로컬 사내망에서는 `cammnet.octa.net`의
포트 80/443 모두 TCP 핸드셰이크 단계에서 무응답 타임아웃이 발생해 최종 판정을
내리지 못했다. GitHub Actions(사내망 밖 클라우드 IP)에서 동일 요청을 시도해
그 결과로 최종 확정한다:

  - 정상 응답 → 사내망 차단이 원인이었던 것 → 계속 수집 대상 유지
  - 여전히 타임아웃/차단 → 원격 차단 또는 서버 문제 → 수집 대상에서 제외 검토

이 수집기는 실패를 삼키지 않는다: 접속 실패 시 예외를 그대로 올려
collect.py가 run_log.csv에 상태 코드/오류 메시지를 기록하고 Actions를
실패로 종료하도록 한다 (§4-3 조용한 실패 금지).

페이지 구조를 확인하지 못한 상태이므로(§0-3 원칙: 추정 금지), 파싱 로직은
패치오더에 제시된 개별 공고 URL 패턴(`landing/Default.aspx?id=NNN`)을 근거로
한 최소 추정만 수행한다. 접속에 성공했는데 이 패턴의 링크가 전혀 없다면
0건으로 보고한다(가짜 데이터를 만들지 않는다) — 조용한 실패 방지는
common.check_consecutive_zero()가 2회 연속 0건일 때 처리한다.

[2026-08-07 최종 판정 -- 수집 대상에서 제외됨]
GitHub Actions에서 실행한 결과 `cammnet.octa.net`은 정상 접속됐다(사내망 문제였음이
확인됨). 그러나 실제 페이지에는 `landing/Default.aspx?id=` 패턴의 공고 링크가 전혀
없었고, 대신 페이지 안내에 따라 이동한 신규 조달 시스템
`https://procurement.opengov.com/portal/octa` 은 Cloudflare 봇 차단으로 자동
접근이 아예 불가능했다(403 / "Sorry, you have been blocked"). 패치오더 §2
판정표의 "403/봇 차단 → 수집 대상 제외" 케이스에 해당하여, collect.py의
COLLECTORS 목록에서 제외했다. 이 파일은 향후 참고용으로 남겨둔다.
"""
import re

import requests
from bs4 import BeautifulSoup

from . import common

INSTITUTION = "OCTA"
URL = "https://cammnet.octa.net/procurements"
USER_AGENT = "H2BusRadarUSCollector/1.0 (+https://github.com/; procurement monitoring)"
TIMEOUT = 30

_NOTICE_LINK_PATTERN = re.compile(r"landing/Default\.aspx\?id=(\d+)", re.IGNORECASE)


def fetch_html(timeout=TIMEOUT):
    resp = requests.get(URL, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def parse_notices(html, run_date):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    seen_ids = set()
    for a in soup.find_all("a", href=True):
        m = _NOTICE_LINK_PATTERN.search(a["href"])
        if not m:
            continue
        notice_id = m.group(1)
        if notice_id in seen_ids:
            continue
        seen_ids.add(notice_id)

        title = a.get_text(strip=True)
        if not title:
            continue

        notice_url = a["href"]
        if notice_url.startswith("/"):
            notice_url = "https://cammnet.octa.net" + notice_url
        elif not notice_url.lower().startswith("http"):
            notice_url = URL.rsplit("/", 1)[0] + "/" + notice_url

        row = {
            "확인일": run_date,
            "기관": INSTITUTION,
            "공고번호": notice_id,
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
            "원본URL": notice_url,
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
