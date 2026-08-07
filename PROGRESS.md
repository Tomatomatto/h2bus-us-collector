# Progress: h2bus-us-collector (M9.0 미국 조달 공고 수집기)
Updated: 2026-08-06 00:00

| # | Task | Status | Start | End | Summary |
|---|------|--------|-------|-----|---------|
| W-01 | 저장소 초기화 · PROGRESS.md 생성 | DONE | 2026-08-06 00:00 | 2026-08-06 00:01 | git init + 폴더 구조(collectors/data/raw/tests/.github/workflows) 생성, PROGRESS.md 작성 |
| W-02 | OCTA 접속 진단 (§2) → 보고 후 대기 | DONE | 2026-08-06 00:01 | 2026-08-06 00:15 | 진단 완료(OCTA_DIAGNOSIS.md) — 판정: 타임아웃(TCP 핸드셰이크 무응답, 포트 80/443 동일). 사용자 지시로 옵션(A) 채택: MTA Flint 우선 구현 + octa.py는 시도 후 실패시 로그로 판정, GH Actions 1회 실행 결과로 최종 확정 |
| W-03 | common.py — CSV 읽기/쓰기 · 누적 병합 | DONE | 2026-08-06 00:16 | 2026-08-06 00:30 | load/save_notices(15열 고정, UTF-8 BOM), merge_notices(§3-4: 신규추가/기존은 마감일·상태·낙찰자만 갱신/삭제없음), apply_deadline_expiry, run_log 헬퍼 |
| W-04 | common.py — 판별 규칙 (품목 · 연료 · 대수) | DONE | 2026-08-06 00:16 | 2026-08-06 00:30 | classify_item_type(버스>충전인프라>부품>용역>기타), classify_fuel(수소 우선), extract_bus_count(FOOT/capacity/fleet of 함정 제외), extract_budget_usd($/USD만) |
| W-05 | tests — 대수 함정 4종 · 연료 판별 테스트 | DONE | 2026-08-06 00:16 | 2026-08-06 01:10 | tests/test_parsing.py 35개(대수 함정 4종+오탐 재현 케이스 포함) — pytest 35 passed. 최초 구현 버그 3건 발견·수정: (1) tire 단수형 \b 경계 버그, (2) standalone 대수패턴 개재어 허용시 실사용 오탐("2026-12"→12대 오인) 재발견 후 회귀, (3) 괄호 대수 패턴을 영문 수사(ONE/TWO..) 선행 조건으로 재한정 |
| W-06 | mta_flint.py 수집기 | DONE | 2026-08-06 00:36 | 2026-08-06 00:50 | robots.txt 확인(/purchasing 비차단), 실제 페이지 구조 확인(Gravity Forms 체크박스 목록), 실 데이터로 스모크테스트 성공(6건: RFP-2026-05 등, IFB-2026-02 Tires→부품 정상 분류, 대수/예산 모두 미기재 원문대로 공란) |
| W-07 | octa.py 수집기 (W-02 결과에 따라 생략 가능) | DONE | 2026-08-06 01:10 | 2026-08-06 01:25 | 실제 페이지 구조 미확인 상태(접속불가)이므로 패치오더 제시 URL패턴(landing/Default.aspx?id=N) 기반 최소 파서 구현. 접속 실패는 예외로 올려 collect.py가 실패 처리하도록 설계(조용한 실패 금지). 합성 HTML로 스모크테스트, 위에서 발견한 오탐 케이스로 회귀 확인 |
| W-08 | run_log.csv · 조용한 실패 방지 | DONE | 2026-08-06 01:25 | 2026-08-06 01:35 | collect.py 작성: 기관별 실행→run_log.csv 기록(append, 이력삭제없음), 접속실패는 예외를 잡아 실패로 기록 후 sys.exit(1), 2회 연속 0건 감지 시에도 exit(1). check_consecutive_zero는 W-05에서 이미 단위테스트 완료 |
| W-09 | GitHub Actions 워크플로 | DONE | 2026-08-06 01:35 | 2026-08-06 01:40 | .github/workflows/collect.yml — 주1회(월 09:00 UTC) + workflow_dispatch, collect.py 실패시 스텝 실패→잡 실패(알림), 성공분은 always()로 커밋·푸시 |
| W-10 | README.md | DONE | 2026-08-06 01:40 | 2026-08-06 01:50 | README 6항목 작성(엑셀주소/대상기관/주기/15열정의/2곳뿐인이유/개인계정유의). 엑셀 연결주소는 GitHub 계정·저장소명 미확정으로 TODO 플레이스홀더 — 미해결 항목으로 보고 |
| W-11 | 실행 1회 · CSV 생성 확인 · 엑셀 연결 주소 검증 | DONE | 2026-08-06 01:50 | 2026-08-06 02:10 | collect.py 1회 실행 → notices.csv 6건(15열·UTF-8 BOM 정확), run_log.csv 누적 기록(성공/실패 각각 정확한 예외 메시지 원문 보존), raw/MTA Flint/2026-08-06.html 보존 확인. OCTA는 실 네트워크로 재시도했고 여전히 타임아웃(§2 판정과 일치) → 실패로 기록되고 종료코드 1. 엑셀 연결주소는 GitHub 저장소 미생성으로 실주소 검증 불가 — 미해결 |
| W-12 | GitHub 저장소 연결 · OCTA 최종 판정 | DONE | 2026-08-07 09:40 | 2026-08-07 09:50 | 저장소 https://github.com/Tomatomatto/h2bus-us-collector 로 push(main), README 엑셀 연결주소 실제값 확정. Actions 수동 실행 결과: MTA Flint 6건 성공, **OCTA는 접속 성공(사내망 문제 아니었음)했으나 실제 페이지에 공고 링크 없음+이전된 신규 시스템(OpenGov)이 Cloudflare 봇차단** → §2 판정표 "403/봇차단→제외" 케이스로 최종 확정. collect.py COLLECTORS에서 OCTA 제거(파일은 조사기록으로 보존), README §2/§5 갱신 |

## 지침 (PATCH_ORDER_M9_0에서 발췌)

- W-02 완료 후 반드시 멈추고 OCTA 진단 결과를 보고한다. 그 결과가 수집 대상을 확정한다.
- 추정 금지: 대수·금액이 원문에 없으면 빈칸.
- robots.txt 준수, 원문 보존(raw/), 조용한 실패 금지.
- 기존 H2BusRadar 코드는 수정하지 않는다 (별개 저장소).
