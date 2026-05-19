#!/usr/bin/env python3
"""AitoEarn task monitor — scans market, auto-accepts eligible tasks, notifies."""

import os, json, time, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests

# ── config ──────────────────────────────────────────────────────────
API_URL  = "https://aitoearn.cn/api/unified/mcp"
API_KEY  = os.environ["AITOEARN_API_KEY"]
HEADERS  = {
    "Content-Type": "application/json",
    "Accept":       "application/json, text/event-stream",
    "x-api-key":    API_KEY,
}

QQ_EMAIL    = os.environ["QQ_EMAIL"]
QQ_AUTH     = os.environ["QQ_SMTP_AUTH_CODE"]

# ── account map  ────────────────────────────────────────────────────
ACCOUNTS = {
    "douyin":  {"id": "douyin__000mVP2MHcc9arWWMylO2Du-yTPNWSO8IpC", "fans": 153},
    "xhs":     {"id": "xhs_6757b931000000001d02f36e_web",             "fans":   0},
    "bilibili":{"id": "bilibili_683278ca380c4d369ed623c63e91af7c",    "fans":  20},
    "KWAI":    {"id": "KWAI_f1b6d99b9252a17314bf572443aa4215",        "fans":   4},
}

# ── helpers ─────────────────────────────────────────────────────────

def rpc(method: str, params: dict | None = None) -> dict:
    """Call the aitoearn JSON-RPC endpoint."""
    body = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000) % 100000,
        "method": method,
        "params": params or {},
    }
    r = requests.post(API_URL, json=body, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data.get("result", data)


def send_email(subject: str, body: str):
    """Send notification via QQ SMTP."""
    msg = MIMEMultipart("alternative")
    msg["From"]    = QQ_EMAIL
    msg["To"]      = QQ_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP("smtp.qq.com", 587, timeout=15) as s:
        s.starttls()
        s.login(QQ_EMAIL, QQ_AUTH)
        s.sendmail(QQ_EMAIL, [QQ_EMAIL], msg.as_string())


# ── task filter ─────────────────────────────────────────────────────

def is_eligible(task: dict) -> tuple[bool, str | None]:
    """Return (eligible, account_id) for a single task."""
    ttype = task.get("type", "")
    if ttype not in ("interaction", "promotion"):
        return False, None
    # only fixed-interaction or fixed-promotion
    tags = task.get("tags", [])
    if "fixed" not in tags and ttype != "interaction":
        # interaction tasks often have no tags — allow all interaction
        if ttype != "interaction":
            return False, None

    reward = task.get("reward", 0)
    if reward <= 0:
        return False, None

    cur  = task.get("currentRecruits", 0)
    max_ = task.get("maxRecruits", 0)
    if cur >= max_:
        return False, None

    platforms = task.get("accountTypes", [])
    rules     = task.get("acceptRules", {})
    required  = rules.get("fansNum", 0)

    for plat in platforms:
        if plat not in ACCOUNTS:
            continue
        if ACCOUNTS[plat]["fans"] >= required:
            return True, ACCOUNTS[plat]["id"]

    return False, None


# ── main ────────────────────────────────────────────────────────────

def main():
    eligible = []
    for page in (1, 2, 3):
        result = rpc("tools/call", {
            "name": "listTaskMarket",
            "arguments": {"pageNo": page, "pageSize": 20},
        })
        # MCP tools/call response may nest under content
        items = result
        if isinstance(result, dict) and "content" in result:
            for c in result["content"]:
                if c.get("type") == "text":
                    items = json.loads(c["text"])
                    break
        for task in items.get("list", []):
            ok, aid = is_eligible(task)
            if ok:
                eligible.append((task, aid))

    if not eligible:
        print(f"[{time.ctime()}] No eligible tasks found.")
        return

    accepted = []
    for task, aid in eligible:
        tid   = task["id"]
        title = task["title"]
        plat  = task.get("accountTypes", [])
        reward= task.get("reward", 0)
        ttype = task.get("type", "")

        try:
            rpc("tools/call", {
                "name": "acceptTask",
                "arguments": {"taskId": tid, "accountId": aid},
            })
            accepted.append((title, plat, reward, ttype, tid))
            print(f"ACCEPTED: {title} [{plat}] ¥{reward} ({ttype})")
            time.sleep(1)  # gentle rate limit
        except Exception as e:
            print(f"FAILED: {title} — {e}")

    if not accepted:
        return

    # build email
    lines = ["接取到以下任务：", ""]
    promo_lines = []
    has_promotion = False
    for title, plat, reward, ttype, tid in accepted:
        lines.append(f"  • {title}  [{', '.join(plat) if isinstance(plat, list) else plat}]  ¥{reward}  ({ttype})")
        lines.append(f"    id: {tid}")
        if ttype == "promotion":
            has_promotion = True
            promo_lines.append(f"  ⚡ {title} — 需手动发布，请登录 https://aitoearn.cn 完成")

    if has_promotion:
        lines.append("")
        lines.append("⚠ 以下为推广类任务，需要你登录网页端完成发布：")
        lines.extend(promo_lines)

    body = "\n".join(lines)
    print(body)
    send_email(f"[AitoEarn] 接取 {len(accepted)} 个任务", body)


if __name__ == "__main__":
    main()
