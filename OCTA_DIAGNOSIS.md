# W-02: OCTA 접속 진단 결과

진단일: 2026-08-06
진단 환경: 로컬 PC (Windows, Git Bash / curl, 사내망 경유)

## 1. 테스트 대상 URL

- `https://cammnet.octa.net/procurements`
- `https://cammnet.octa.net/procurements/landing/Default.aspx?id=54241`
- `http://cammnet.octa.net/procurements` (포트 80, 대조군)

## 2. 원시 결과 (그대로 기록)

### 2-1. DNS 조회 — 정상

```
이름:    cammnet.octa.net
Address:  136.179.6.168
```
역방향 조회 시 호스트명: `cust-136.179.6.168.switchnap.com` (공유 호스팅/데이터센터 IP로 추정)

### 2-2. HTTPS (443) 접속 시도 — `/procurements`

```
curl -v -m 25 https://cammnet.octa.net/procurements
* Host cammnet.octa.net:443 was resolved.
* IPv4: 136.179.6.168
*   Trying 136.179.6.168:443...
* Connection timed out after 20002 milliseconds
* closing connection #0
[STATUS=000] [TIME=21.07s]
```

### 2-3. HTTPS (443) 접속 시도 — 개별 공고 URL (`id=54241`)

```
curl -v -m 20 https://cammnet.octa.net/procurements/landing/Default.aspx?id=54241
* Trying 136.179.6.168:443...
* Connection timed out after 20001 milliseconds
[STATUS=000] exit code 35 (SSL/connect error 계열 — 실제로는 TCP 연결 자체가 미완료)
```

### 2-4. HTTP (80) 접속 시도 — 대조군

```
curl -v -m 15 http://cammnet.octa.net/procurements
*   Trying 136.179.6.168:80...
* Connection timed out after 15010 milliseconds
```
→ 포트 80/443 모두 **TCP 3-way handshake 자체가 완료되지 않음** (SYN에 대한 응답 없음). HTTP 상태 코드·응답 헤더·오류 페이지는 전혀 수신되지 않았음(서버 응답 자체가 없음).

### 2-5. Traceroute (참고)

```
tracert 136.179.6.168
  1  10.60.80.2   2ms
  2  10.60.1.44   4ms
  3  ... (사내망 구간에서 확인, 이후 홉 응답 없음/타임아웃)
```

### 2-6. 대조군 테스트 (같은 환경에서 다른 대상은 정상 접속됨)

이 로컬 PC의 curl(Windows schannel)은 인증서 폐기 확인(OCSP/CRL) 정책 때문에
`https://www.google.com`, `https://www.mtaflint.org/purchasing` 에 대해 기본 옵션으로는
`CRYPT_E_NO_REVOCATION_CHECK` 오류가 발생했으나, `--ssl-no-revoke` 옵션을 추가하면 즉시 정상 응답했다.

```
curl --ssl-no-revoke https://www.google.com
[STATUS=200] [TIME=0.43s]

curl --ssl-no-revoke https://www.mtaflint.org/purchasing
HTTP/1.1 301 Moved Permanently
Location: https://www.mtaflint.org/purchasing/
[STATUS=301] [TIME=1.40s]
```

즉, **일반 인터넷 접속 자체(및 MTA Flint 대상)는 이 환경에서 정상 동작**한다.
(단, 이 TLS 폐기확인 이슈는 로컬 Windows curl/schannel 고유의 사내망 정책 특성이며,
GitHub Actions(Ubuntu, OpenSSL)에서는 재현되지 않을 가능성이 높다 — 참고용으로만 기록.)

동일 방식(`--ssl-no-revoke` 포함)으로 OCTA를 재시도해도 **TCP 연결 자체가 타임아웃**되어
변화가 없었다(§2-2 결과와 동일).

## 3. 판정 (§2 판정표 적용)

| 증상 | 관측 결과 |
|---|---|
| 403 / 봇 차단 페이지 | **해당 없음** — HTTP 응답 자체를 받지 못함 (봇 차단이면 최소한 HTTP 레벨 응답은 온다) |
| 타임아웃 | **해당함** — 포트 80/443 모두 TCP 핸드셰이크 단계에서 20초 타임아웃, 응답 전무 |
| SSL 오류 | **해당 없음** — TLS 핸드셰이크 자체가 시작되지 못함 (TCP 연결이 안 됨) |
| 정상 응답 | 해당 없음 |

**판정: 타임아웃 → 원인 = 실행 환경(로컬 사내망)의 외부 접속 제약 가능성.**

대조군(google.com, mtaflint.org)은 동일 환경에서 정상 응답했으므로 "인터넷 자체가 끊김"은 아니다.
다만 OCTA(`cammnet.octa.net`, 136.179.6.168)만 포트 80/443 모두 응답이 없는 것은 다음 중 하나로 추정된다:

1. 사내망 방화벽/프록시가 해당 IP 대역(`switchnap.com` 호스팅사)을 차단
2. OCTA 측(또는 그 호스팅사)이 국가/기관 IP 대역 기준으로 접근을 차단(방화벽에서 조용히 드롭)
3. 서버 자체 다운/네트워크 경로 문제 (일시적)

**로컬 PC만으로는 원인 1·2·3을 확정적으로 구분할 수 없다.**
§2 규약에 따라 "타임아웃 → GitHub Actions에서 재시도해 확인"이 필요한 상황이다.
GitHub Actions(공용 클라우드 IP, 사내망 밖)에서 동일 요청을 실행했을 때:
- 정상 응답이 오면 → 원인 1(사내망 차단)이 맞았던 것 → **수집 대상 유지**, `octa.py` 구현(W-07) 진행
- 여전히 타임아웃/차단이면 → 원인 2 또는 서버 문제 → **수집 대상에서 제외**, 수기 확인으로 전환

## 4. 권고 및 대기 사항

W-02는 로컬 환경에서 가능한 진단을 완료했으나, **최종 판정에는 GitHub Actions 환경에서의 1회 재시도가 필요**하다.
이는 패치오더 §2 판정표의 "타임아웃" 행이 명시한 대응 절차와 일치한다.

두 가지 진행 경로 중 사용자 판단이 필요:

- (A) MTA Flint 1곳만으로 우선 W-03~W-11을 진행하고, GitHub Actions 워크플로가 만들어진 뒤 첫 실행 시 OCTA도 함께 시도해 그 결과로 최종 확정(로그로 판정 근거 남김)
- (B) 사용자가 사내망 외부(다른 네트워크/VPN 등)에서 즉시 1회 접속 테스트하여 지금 판정을 확정
