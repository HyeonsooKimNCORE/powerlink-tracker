# -*- coding: utf-8 -*-
"""
네이버 파워링크 순위 추적 + 텔레그램 알림 스크립트 (깃허브 액션즈용)

수정이 필요한 부분은 딱 2곳입니다. 아래 "여기만 수정하세요" 표시를 찾으세요.
"""

import os
import time
import random
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ============================================================
# 여기만 수정하세요 (1) : 추적하고 싶은 키워드와 내 업체명
# ============================================================
KEYWORDS = [
    "인테리어 견적",
    "강남 치과",
]

MY_NAME = "우리회사"       # 광고 제목/설명에 들어가는 상호명
MY_DOMAIN = None          # 도메인으로 찾고 싶으면 "example.com" 처럼 입력, 아니면 None
# ============================================================


DB_PATH = "powerlink_rank.db"
SLEEP_SEC = 4

# 텔레그램 토큰/챗ID는 코드에 직접 쓰지 않고, 깃허브의 "비밀 값(Secrets)"에서 가져옵니다.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rank_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checked_at TEXT,
            keyword TEXT,
            rank INTEGER
        )
        """
    )
    conn.commit()
    return conn


def fetch_search_html(keyword: str) -> str:
    url = "https://search.naver.com/search.naver"
    resp = requests.get(url, params={"query": keyword}, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.text


def parse_powerlink_rank(html: str):
    soup = BeautifulSoup(html, "html.parser")
    ad_items = soup.select("li.lst_item") or soup.select("div.ad_section li")
    if not ad_items:
        return None
    for idx, item in enumerate(ad_items, start=1):
        text = item.get_text(" ", strip=True)
        link_tag = item.select_one("a")
        href = link_tag["href"] if link_tag and link_tag.has_attr("href") else ""
        if MY_NAME and MY_NAME in text:
            return idx
        if MY_DOMAIN and MY_DOMAIN in href:
            return idx
    return None


def save_rank(conn, keyword, rank):
    conn.execute(
        "INSERT INTO rank_history (checked_at, keyword, rank) VALUES (?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), keyword, rank),
    )
    conn.commit()


def get_previous_rank(conn, keyword):
    cur = conn.execute(
        "SELECT rank FROM rank_history WHERE keyword = ? ORDER BY id DESC LIMIT 1 OFFSET 1",
        (keyword,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[알림 미발송] 텔레그램 설정이 안 되어 있습니다:", message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
    except requests.RequestException as e:
        print("텔레그램 전송 실패:", e)


def check_keyword(conn, keyword):
    html = fetch_search_html(keyword)
    current_rank = parse_powerlink_rank(html)
    previous_rank = get_previous_rank(conn, keyword)
    save_rank(conn, keyword, current_rank)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    if current_rank is None:
        if previous_rank is not None:
            msg = f"[{now_str}] '{keyword}' 파워링크 노출이 사라졌습니다. (이전 순위: {previous_rank}위)"
            print(msg)
            send_telegram(msg)
        else:
            print(f"[{now_str}] '{keyword}' 파워링크에 노출되지 않음 (기존 기록 없음)")
        return

    print(f"[{now_str}] '{keyword}' 현재 순위: {current_rank}위 (이전: {previous_rank})")

    if previous_rank is not None and current_rank > previous_rank:
        msg = (
            f"[{now_str}] '{keyword}' 순위 하락 감지!\n"
            f"이전 순위: {previous_rank}위 → 현재 순위: {current_rank}위"
        )
        send_telegram(msg)


def main():
    conn = init_db()
    try:
        for kw in KEYWORDS:
            try:
                check_keyword(conn, kw)
            except Exception as e:
                print(f"'{kw}' 처리 중 오류:", e)
            time.sleep(SLEEP_SEC + random.uniform(0, 2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
