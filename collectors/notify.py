"""신규 수소버스 공고 발견 시 이메일 알림.

GitHub Actions(Ubuntu 클라우드 러너, Outlook 미설치)에서 실행되므로
Outlook COM 자동화(로컬 전용, CV News Clipping 프로젝트의 현재 운영 방식)는
쓸 수 없다. 대신 표준 라이브러리 smtplib 기반의 순수 SMTP 방식만 사용한다
(같은 프로젝트의 email_sender.py가 지원하는 두 방식 중 이식 가능한 쪽).

자격증명은 코드/저장소에 절대 넣지 않고 GitHub Actions Secrets를 통해
환경변수로만 주입받는다. 필요한 환경변수:
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, FROM_EMAIL, TO_EMAIL

alert 대상이 없으면(rows가 비어있으면) 환경변수를 읽지도 않는다 — 아직 이
기능을 설정하지 않은 상태에서도 평소 실행(신규 수소버스 공고 없음)은
그대로 성공해야 하기 때문이다.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_new_hydrogen_bus_alert(rows):
    """rows: find_new_hydrogen_bus_rows()가 반환한 신규 수소버스 공고 목록."""
    if not rows:
        return

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]
    from_email = os.environ.get("FROM_EMAIL", username)
    to_email = os.environ["TO_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[수소버스 신규 공고] {len(rows)}건 발견"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(_build_html(rows), "html", "utf-8"))

    server = smtplib.SMTP_SSL(host, port, timeout=15)
    try:
        server.login(username, password)
        server.sendmail(from_email, [to_email], msg.as_bytes())
    finally:
        server.quit()


def _build_html(rows):
    items = "".join(
        "<li><b>{기관}</b> {공고번호} — {제목} (마감 {마감일}) "
        '<a href="{원본URL}">원문 보기</a></li>'.format(
            기관=r.get("기관", ""),
            공고번호=r.get("공고번호", ""),
            제목=r.get("제목", ""),
            마감일=r.get("마감일") or "미상",
            원본URL=r.get("원본URL", ""),
        )
        for r in rows
    )
    return (
        "<html><body style='font-family:sans-serif;'>"
        f"<h3>신규 수소버스 공고 {len(rows)}건 발견</h3>"
        f"<ul>{items}</ul>"
        "</body></html>"
    )
