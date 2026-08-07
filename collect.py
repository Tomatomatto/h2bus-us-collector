#!/usr/bin/env python3
"""M9.0 미국 조달 공고 수집기 — 실행 진입점.

기관별 수집기를 순서대로 실행하고, notices.csv에 누적 병합하며,
매 실행을 run_log.csv에 기록한다.

조용한 실패 방지(§4-3):
  1) 개별 기관 수집이 예외를 던지면(접속 실패 등) 그 즉시 실패로 기록하고
     이 스크립트는 0이 아닌 코드로 종료한다 (GitHub Actions가 실패로 표시).
  2) 예외 없이 성공했더라도 특정 기관이 2회 연속 0건을 반환하면 마찬가지로
     경고를 남기고 실패로 종료한다.
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from collectors import common, mta_flint  # noqa: E402

NOTICES_CSV = ROOT / "data" / "notices.csv"
RUN_LOG_CSV = ROOT / "data" / "run_log.csv"

# OCTA는 2026-08-07 GitHub Actions 실행으로 최종 제외 확정 (collectors/octa.py, OCTA_DIAGNOSIS.md 참고):
#   - 사내망 타임아웃이 원인이 아니었음 -- 클라우드(GH Actions)에서는 정상 접속됨
#   - 그러나 예전 CAMMNET 목록 페이지에는 공고 링크가 더 이상 없고, 안내에 따라 이동한
#     새 조달 시스템(procurement.opengov.com/portal/octa)은 Cloudflare 봇 차단으로
#     자동 접근 자체가 불가능함 (403 / "Sorry, you have been blocked")
#   -> 패치오더 §2 판정표의 "403/봇 차단 → 수집 대상 제외" 케이스. 수기 확인 대상으로 전환.
COLLECTORS = [
    ("MTA Flint", mta_flint.run),
]


def main():
    today = date.today()
    run_date = today.isoformat()

    existing_rows = common.load_notices(NOTICES_CSV)
    new_rows = []
    run_log_entries = []
    any_failed = False

    for institution, collector_fn in COLLECTORS:
        try:
            rows = collector_fn(run_date)
        except Exception as exc:  # noqa: BLE001 - 원인 그대로 기록 후 재노출하지 않고 로그로 남긴다
            any_failed = True
            err_msg = f"{type(exc).__name__}: {exc}"
            run_log_entries.append(common.make_run_log_entry(institution, "실패", 0, err_msg))
            print(f"[{institution}] 실패: {err_msg}", file=sys.stderr)
            continue

        run_log_entries.append(common.make_run_log_entry(institution, "성공", len(rows), ""))
        print(f"[{institution}] 수집 {len(rows)}건")
        new_rows.extend(rows)

    merged = common.merge_notices(existing_rows, new_rows, today)
    common.save_notices(NOTICES_CSV, merged)

    for entry in run_log_entries:
        common.append_run_log(RUN_LOG_CSV, entry)

    run_log_all = common.load_run_log(RUN_LOG_CSV)
    silent_failure = False
    for institution, _ in COLLECTORS:
        if common.check_consecutive_zero(run_log_all, institution, n=2):
            print(f"[경고] {institution}: 최근 2회 연속 수집 0건 -- 조용한 실패 의심", file=sys.stderr)
            silent_failure = True

    if any_failed or silent_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
