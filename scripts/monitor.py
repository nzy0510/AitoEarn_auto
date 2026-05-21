#!/usr/bin/env python3
"""AitoEarn auto-pilot — scan, accept, generate, publish, submit."""

import os, sys, re, time, smtplib, html as html_mod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
import yaml

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── config ──────────────────────────────────────────────────────────
API_URL = "https://aitoearn.cn/api/unified/mcp"
API_KEY = os.environ["AITOEARN_API_KEY"]
HEADERS = {
    "Content-Type": "application/json",
    "Accept":       "application/json, text/event-stream",
    "x-api-key":    API_KEY,
}
QQ_EMAIL = os.environ["QQ_EMAIL"]
QQ_AUTH  = os.environ["QQ_SMTP_AUTH_CODE"]

# ── account map ─────────────────────────────────────────────────────
ACCOUNTS = {
    "douyin":  {"id": "douyin__000mVP2MHcc9arWWMylO2Du-yTPNWSO8IpC", "fans": 153},
    "xhs":     {"id": "xhs_6757b931000000001d02f36e_web",             "fans":   0},
    "bilibili":{"id": "bilibili_683278ca380c4d369ed623c63e91af7c",    "fans":  20},
    "KWAI":    {"id": "KWAI_f1b6d99b9252a17314bf572443aa4215",        "fans":   4},
}

# Platforms that can publish directly via MCP (no mobile step)
PUBLISH_FUNCTIONS = {
    "bilibili": "publishPostToBilibili",
    "KWAI":     "publishPostToKwai",
    "tiktok":   "publishPostToTiktok",
    "youtube":  "publishPostToYoutube",
    "facebook": "publishPostToFacebook",
    "instagram":"publishPostToInstagram",
    "pinterest":"publishPostToPinterest",
    "threads":  "publishPostToThreads",
    "twitter":  "publishPostToTwitter",
    "wxGzh":    "publishPostToWxGzh",
}
DOUYIN_NEEDS_PHONE = True

# ── helpers ─────────────────────────────────────────────────────────

def rpc(method: str, params: dict | None = None) -> dict:
    body = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000) % 100000,
        "method": method,
        "params": params or {},
    }
    r = requests.post(API_URL, json=body, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data.get("result", data)


def rpc_text(method: str, params: dict) -> str:
    """Call RPC and extract text from content[0].text."""
    result = rpc(method, params)
    if isinstance(result, dict) and "content" in result:
        for c in result["content"]:
            if c.get("type") == "text":
                return c["text"]
    return str(result)


def send_email(subject: str, body: str):
    msg = MIMEMultipart("alternative")
    msg["From"]    = QQ_EMAIL
    msg["To"]      = QQ_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    with smtplib.SMTP("smtp.qq.com", 587, timeout=15) as s:
        s.starttls()
        s.login(QQ_EMAIL, QQ_AUTH)
        s.sendmail(QQ_EMAIL, [QQ_EMAIL], msg.as_string())


def strip_html(raw: str) -> str:
    if not raw:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", raw)
    text = html_mod.unescape(text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_user_task_id(response_text: str) -> str | None:
    m = re.search(r"userTaskId=(\S+)", response_text)
    return m.group(1) if m else None


# ── task filter ─────────────────────────────────────────────────────

def is_eligible(task: dict) -> tuple[bool, str | None]:
    ttype = task.get("type", "")
    if ttype not in ("interaction", "promotion"):
        return False, None
    tags = task.get("tags", [])
    if "fixed" not in tags and ttype != "interaction":
        if ttype != "interaction":
            return False, None
    reward = task.get("reward", 0)
    if reward <= 0:
        return False, None
    cur, max_ = task.get("currentRecruits", 0), task.get("maxRecruits", 0)
    if cur >= max_:
        return False, None
    rules = task.get("acceptRules", {})
    required = rules.get("fansNum", 0)
    total_fans = sum(a["fans"] for a in ACCOUNTS.values())
    if total_fans < required:
        return False, None
    for plat in task.get("accountTypes", []):
        if plat in ACCOUNTS:
            return True, ACCOUNTS[plat]["id"]
    return False, None


# ── content generation ─────────────────────────────────────────────

def generate_content(task: dict, platforms: list[str]) -> dict | None:
    """Generate AI image-text draft. Returns dict with media URLs and text."""
    desc = strip_html(task.get("description", ""))
    title = task.get("title", "")
    product_info = f"{title}. {desc}" if desc else title

    # Extract hashtag requirements from description
    hashtags = re.findall(r"#[^\s#]+", desc) if desc else []
    hashtag_str = " ".join(hashtags[:10]) if hashtags else ""

    caption_prompt = (
        f"为以下产品创作一条{platforms[0] if platforms else '社交'}平台推广文案:\n"
        f"产品信息: {product_info}\n"
        f"必须带上话题: {hashtag_str}\n" if hashtag_str else "" +
        f"要求: 标题吸引人, 描述自然像朋友推荐, 20-100字, 结尾引导行动.\n"
        f"平台: {', '.join(platforms)}"
    )
    image_prompt = (
        f"Professional marketing image for: {title}. "
        f"Product context: {desc[:300] if desc else title}. "
        f"Clean, eye-catching, suitable for {platforms[0] if platforms else 'social media'}."
    )

    print(f"  [gen] Creating draft for: {title}")
    result_text = rpc_text("tools/call", {
        "name": "createImageTextDraft",
        "arguments": {
            "prompt": image_prompt[:2000],
            "captionPrompt": caption_prompt[:2000],
            "imageModel": "gpt-image-2",
            "imageCount": 3,
            "imageSize": "1K",
            "aspectRatio": "3:4",
            "platforms": platforms,
            "draftType": "draft",
            "disableMemory": True,
        },
    })
    # Parse task IDs from result
    task_ids = re.findall(r"[a-f0-9]{24,}", result_text)
    if not task_ids:
        print(f"  [gen] No draft task ids found in: {result_text[:200]}")
        return None

    print(f"  [gen] Draft tasks: {task_ids}")
    # Wait for completion
    for attempt in range(30):
        time.sleep(10)
        all_done = True
        for tid in task_ids:
            status_text = rpc_text("tools/call", {
                "name": "getDraftTaskStatus",
                "arguments": {"taskId": tid},
            })
            if "generating" in status_text.lower():
                all_done = False
                break
            if "failed" in status_text.lower():
                print(f"  [gen] Draft {tid} failed: {status_text[:200]}")
                return None
        if all_done:
            print(f"  [gen] All drafts completed after {(attempt+1)*10}s")
            break
    else:
        print("  [gen] Timeout waiting for drafts")
        return None

    # Get the latest drafts to find media
    drafts_text = rpc_text("tools/call", {
        "name": "listDrafts",
        "arguments": {"pageNo": 1, "pageSize": 5},
    })
    # Parse draft info from YAML response
    try:
        drafts = yaml.safe_load(drafts_text)
    except Exception:
        print(f"  [gen] Failed to parse drafts YAML")
        return None

    draft_list = drafts.get("list", []) if isinstance(drafts, dict) else []
    if not draft_list:
        print("  [gen] No drafts found")
        return None

    # Use the most recent draft
    draft = draft_list[0]
    draft_id = draft.get("id", "")
    cover_url = draft.get("coverUrl", "")
    media_list = draft.get("mediaList", [])
    draft_title = draft.get("title", title)
    draft_desc = draft.get("desc", "")

    # Build full media URLs
    base_url = "https://assets.aitoearn.cn/"
    media_urls = [m.get("url", "") for m in media_list]
    full_urls = [
        (base_url + u if not u.startswith("http") else u)
        for u in media_urls if u
    ]

    result = {
        "draft_id": draft_id,
        "title": draft_title,
        "desc": draft_desc,
        "cover_url": (base_url + cover_url if cover_url and not cover_url.startswith("http") else cover_url),
        "media_urls": full_urls,
        "video_url": next((u for m, u in zip(media_list, full_urls) if m.get("type") == "video"), full_urls[0] if full_urls else ""),
        "img_urls": full_urls,
    }
    print(f"  [gen] Draft ready: {draft_id}, {len(full_urls)} media files")
    return result


# ── publish ─────────────────────────────────────────────────────────

def publish_to_platform(plat: str, account_id: str, draft: dict,
                        task_desc: str, user_task_id: str) -> str | None:
    """Publish draft to a platform. Returns work link or None."""
    func_name = PUBLISH_FUNCTIONS.get(plat)
    if not func_name:
        print(f"  [pub] No publish function for {plat}")
        return None

    hashtags = re.findall(r"#[^\s#]+", task_desc) if task_desc else []
    topics = hashtags[:10] if hashtags else []

    title = draft["title"][:100] if draft["title"] else "New post"
    desc = draft["desc"][:800] if draft["desc"] else ""
    video_url = draft.get("video_url", "")
    cover_url = draft.get("cover_url", "")
    img_urls = draft.get("img_urls", [])

    args = {
        "accountId": account_id,
        "title": title,
        "desc": desc,
        "coverUrl": cover_url,
        "topics": topics,
    }
    if plat == "bilibili":
        args["videoUrl"] = video_url or (img_urls[0] if img_urls else "")

    elif plat == "KWAI":
        args["videoUrl"] = video_url or (img_urls[0] if img_urls else "")
        args["coverUrl"] = cover_url or ""

    elif plat in ("tiktok", "youtube", "facebook", "twitter"):
        args["videoUrl"] = video_url or (img_urls[0] if img_urls else "")

    elif plat in ("instagram", "pinterest", "threads"):
        if img_urls:
            args["imgUrlList"] = img_urls[:9]
        elif video_url:
            args["videoUrl"] = video_url

    elif plat == "wxGzh":
        # WeChat official account
        pass

    print(f"  [pub] Publishing to {plat}...")
    try:
        result_text = rpc_text("tools/call", {
            "name": func_name,
            "arguments": args,
        })
        print(f"  [pub] {plat} result: {result_text[:300]}")
        # Try to extract work link
        link = re.search(r"https?://[^\s]+", result_text)
        if link:
            return link.group(0)
    except Exception as e:
        print(f"  [pub] {plat} failed: {e}")

    return None


def publish_douyin_semi(account_id: str, draft: dict, task_desc: str) -> str | None:
    """Call publishPostToDouyin, return the mobile-confirmation URL."""
    hashtags = re.findall(r"#[^\s#]+", task_desc) if task_desc else []
    topics = hashtags[:5]

    video_url = draft.get("video_url", "")
    img_urls = draft.get("img_urls", [])

    args = {
        "accountId": account_id,
        "title": (draft["title"] or "New post")[:800],
        "desc": (draft["desc"] or "")[:800],
        "coverUrl": draft.get("cover_url", ""),
        "topics": topics,
    }
    if video_url:
        args["videoUrl"] = video_url
    elif img_urls:
        args["imgUrlList"] = img_urls[:9]

    try:
        result_text = rpc_text("tools/call", {
            "name": "publishPostToDouyin",
            "arguments": args,
        })
        print(f"  [douyin] Mobile URL: {result_text[:500]}")
        link = re.search(r"https?://[^\s]+", result_text)
        return link.group(0) if link else result_text[:500]
    except Exception as e:
        print(f"  [douyin] Publish failed: {e}")
    return None


# ── main ────────────────────────────────────────────────────────────

def main():
    # ── Phase 1: Scan & Accept ─────────────────────────────────────
    eligible = []
    for page in (1, 2, 3):
        result = rpc("tools/call", {
            "name": "listTaskMarket",
            "arguments": {"pageNo": page, "pageSize": 20},
        })
        items = result
        if isinstance(result, dict) and "content" in result:
            for c in result["content"]:
                if c.get("type") == "text":
                    items = yaml.safe_load(c["text"])
                    break
        for task in items.get("list", []):
            ok, aid = is_eligible(task)
            if ok:
                eligible.append((task, aid))

    if not eligible:
        print(f"[{time.ctime()}] No eligible tasks.")
        return

    accepted = []  # (title, platforms, reward, ttype, task_id, account_id, user_task_id, full_task)
    for task, aid in eligible:
        tid = task["id"]
        title = task["title"]
        plat = task.get("accountTypes", [])
        reward = task.get("reward", 0)
        ttype = task.get("type", "")

        try:
            resp_text = rpc_text("tools/call", {
                "name": "acceptTask",
                "arguments": {"taskId": tid, "accountId": aid},
            })
            utid = parse_user_task_id(resp_text)
            if utid:
                accepted.append((title, plat, reward, ttype, tid, aid, utid, task))
                print(f"[+] {title} [{plat}] Y{reward} ({ttype}) utid={utid}")
            else:
                print(f"[?] Accepted but no utid: {resp_text[:100]}")
            time.sleep(1)
        except Exception as e:
            print(f"[-] {title}: {e}")

    if not accepted:
        return

    # ── Phase 2: Fulfill promotions ─────────────────────────────────
    report_lines = ["接取到以下任务：", ""]
    douyin_urls = []
    done_count = 0

    for title, plats, reward, ttype, tid, aid, utid, task in accepted:
        report_lines.append(
            f"  - {title}  [{', '.join(plats)}]  Y{reward}  ({ttype})"
        )
        report_lines.append(f"    id: {tid}")

        if ttype != "promotion":
            report_lines.append(f"    [互动任务] 需要截图提交")
            continue

        desc = strip_html(task.get("description", ""))
        if not desc:
            desc = title

        can_auto = [p for p in plats if p in PUBLISH_FUNCTIONS]
        has_douyin = "douyin" in plats
        has_xhs = "xhs" in plats

        if not can_auto and not has_douyin:
            report_lines.append(f"    [需手动] 平台不支持自动发布")
            continue

        # Generate content
        draft = generate_content(task, plats)
        if not draft:
            report_lines.append(f"    [!] 内容生成失败")
            continue

        published = False

        # Auto-publish to full-auto platforms
        for plat in can_auto:
            work_link = publish_to_platform(plat, aid, draft, desc, utid)
            if work_link:
                # Submit the task
                try:
                    sub_resp = rpc_text("tools/call", {
                        "name": "submitTask",
                        "arguments": {"userTaskId": utid, "workLink": work_link},
                    })
                    print(f"  [done] Submitted {title} to {plat}: {sub_resp[:200]}")
                    report_lines.append(f"    [完成] {plat}: {work_link}")
                    done_count += 1
                    published = True
                except Exception as e:
                    report_lines.append(f"    [提交失败] {plat}: {e}")
            time.sleep(2)

        # Semi-auto: douyin (needs phone confirm)
        if has_douyin:
            douyin_url = publish_douyin_semi(aid, draft, desc)
            if douyin_url:
                douyin_urls.append((title, douyin_url))
                report_lines.append(f"    [抖音] 请在手机上打开: {douyin_url}")
                published = True

        if has_xhs:
            report_lines.append(f"    [小红书] 需手动发布: https://aitoearn.cn")

        if not published:
            report_lines.append(f"    [未完成] 发布失败")

        time.sleep(3)

    # ── Phase 3: Report ────────────────────────────────────────────
    if douyin_urls:
        report_lines.append("")
        report_lines.append("=== 抖音待确认 (请用手机打开) ===")
        for t, url in douyin_urls:
            report_lines.append(f"  {t}: {url}")

    body = "\n".join(report_lines)
    print(body)

    subject = f"[AitoEarn] {len(accepted)} tasks"
    if done_count:
        subject += f", {done_count} auto-completed"
    send_email(subject, body)


if __name__ == "__main__":
    main()
