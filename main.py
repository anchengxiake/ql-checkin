"""
cron: 0 9 * * *
new Env('SouthPlus签到')
"""

import os
import re
import sys
import time
import random
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# ---------------- 统一通知模块加载 ----------------
hadsend = False
send = None
try:
    from notify import send
    hadsend = True
    print("✅ 已加载notify.py通知模块")
except ImportError:
    print("⚠️  未加载通知模块，跳过通知功能")

# 随机延迟配置
max_random_delay = int(os.getenv("MAX_RANDOM_DELAY", "3600"))
random_signin = os.getenv("RANDOM_SIGNIN", "true").lower() == "true"

url = "https://south-plus.net/plugin.php"

base_headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "priority": "u=0, i",
    "sec-ch-ua": '"Microsoft Edge";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
}

def build_task_params(verify: str):
    """构建任务参数，verify 需从当前会话页面实时提取。"""
    common_params = {
        "H_name": "tasks",
        "action": "ajax",
        "nowtime": str(int(time.time() * 1000)),
        "verify": verify,
    }

    ad_params = {**common_params, "actions": "job", "cid": "15"}
    aw_params = {**common_params, "actions": "job", "cid": "14"}
    cd_params = {**common_params, "actions": "job2", "cid": "15"}
    cw_params = {**common_params, "actions": "job2", "cid": "14"}
    return ad_params, aw_params, cd_params, cw_params


def format_time_remaining(seconds: int) -> str:
    """格式化时间显示"""
    if seconds <= 0:
        return "立即执行"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}小时{minutes}分{secs}秒"
    if minutes > 0:
        return f"{minutes}分{secs}秒"
    return f"{secs}秒"


def wait_with_countdown(delay_seconds: int):
    """带倒计时的等待"""
    if delay_seconds <= 0:
        return

    print(f"SouthPlus签到需要等待 {format_time_remaining(delay_seconds)}")
    remaining = delay_seconds
    while remaining > 0:
        if remaining <= 10 or remaining % 10 == 0:
            print(f"倒计时: {format_time_remaining(remaining)}")

        sleep_time = 1 if remaining <= 10 else min(10, remaining)
        time.sleep(sleep_time)
        remaining -= sleep_time


def Push(title: str, message: str):
    if hadsend:
        try:
            send(title, message)
            print("✅ notify.py推送成功")
        except Exception as e:
            print(f"❌ notify.py推送失败: {e}")
    else:
        print(f"📢 {title}")
        print(f"📄 {message}")


def get_cookies():
    """读取环境变量 COOKIE，支持多账号换行或 && 分隔"""
    if "COOKIE" not in os.environ:
        print("❌ 未设置 COOKIE 环境变量")
        Push("SouthPlus签到", "❌ 未设置 COOKIE 环境变量")
        sys.exit(0)

    raw = os.environ.get("COOKIE", "").strip()
    if not raw:
        print("❌ COOKIE 内容为空")
        Push("SouthPlus签到", "❌ COOKIE 内容为空")
        sys.exit(0)

    cookie_list = [c.strip() for c in re.split(r"\n|&&", raw) if c.strip()]
    return cookie_list


def normalize_cookie(raw_cookie: str) -> str:
    """清洗 Cookie，移除无效片段并规范空格。"""
    pairs = []
    for item in raw_cookie.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            pairs.append(f"{key}={value}")
    return "; ".join(pairs)


def parse_message_from_response(data: str) -> str:
    """尽量从返回内容中提取任务提示消息。"""
    data = data or ""

    # 优先按原接口 XML 解析
    try:
        root = ET.fromstring(data)
        cdata = root.text or ""
        values = [v for v in cdata.split("\t") if v is not None and v != ""]
        if len(values) >= 2:
            return values[1].strip()
        if cdata.strip():
            return cdata.strip()
    except ET.ParseError:
        pass

    # 返回了 HTML 页面（例如 Cloudflare/未登录/权限页）
    if "<html" in data.lower():
        if "cf-challenge" in data.lower() or "just a moment" in data.lower() or "cloudflare" in data.lower():
            return "触发 Cloudflare 验证，Cookie 或 cf_clearance 可能失效"

        m_title = re.search(r"<title>(.*?)</title>", data, flags=re.IGNORECASE | re.DOTALL)
        if m_title:
            return f"返回HTML页面: {m_title.group(1).strip()}"

        return "返回HTML页面，未获取到任务接口XML数据"

    # 兜底：去掉多余空白，仅展示前 120 字符
    plain = re.sub(r"\s+", " ", data).strip()
    return plain[:120] if plain else "接口返回为空"


def fetch_verify(cookie: str) -> str:
    """进入任务页提取 verify 参数。"""
    headers = {
        **base_headers,
        "cookie": cookie,
        "referer": "https://south-plus.net/",
    }
    params = {"H_name": "tasks"}
    response = requests.get(url, params=params, headers=headers, timeout=20)
    response.encoding = "utf-8"
    html = response.text or ""

    if "您还没有登录或注册" in html or "登录" in html and "tasks" not in html:
        raise Exception("Cookie 无效或已过期：站点返回未登录")

    patterns = [
        r"verify=([0-9a-fA-F]{6,32})",
        r"['\"]verify['\"]\s*[:=]\s*['\"]([0-9a-zA-Z]{6,64})['\"]",
        r"var\s+verify\s*=\s*['\"]([0-9a-zA-Z]{6,64})['\"]",
    ]
    for p in patterns:
        m = re.search(p, html)
        if m:
            return m.group(1)

    raise Exception("未能从任务页提取 verify，可能触发风控或页面结构变化")


def tasks(params: dict, headers: dict, action_desc: str) -> bool:
    response = requests.get(url, params=params, headers=headers)
    response.encoding = "utf-8"
    data = response.text

    message = parse_message_from_response(data)
    print(action_desc + message)

    fail_keywords = ["未登录", "没有登录", "错误", "失败", "非法", "权限", "验证", "Cloudflare"]
    if any(k in message for k in fail_keywords):
        raise Exception(message)

    return "还没超过" not in message


def run_for_cookie(cookie: str) -> str:
    """单账号执行签到任务并返回日志"""
    verify = fetch_verify(cookie)
    ad_params, aw_params, cd_params, cw_params = build_task_params(verify)

    headers_apply = {**base_headers, "cookie": cookie, "referer": url + "?H_name-tasks-actions-newtasks.html.html"}
    headers_finish = {
        **base_headers,
        "cookie": cookie,
        "authority": "south-plus.net",
        "method": "GET",
        "path": "/plugin.php?H_name-tasks-actions-newtasks.html.html",
        "scheme": "https",
        "Referer": url + "?H_name-tasks.html.html",
    }

    log = ""
    if tasks(ad_params, headers_apply, "申请-日常: "):
        tasks(cd_params, headers_finish, "完成-日常: ")
        log += "日常任务完成\n"
    else:
        log += "日常任务已完成或未达时间\n"

    if tasks(aw_params, headers_apply, "申请-周常: "):
        tasks(cw_params, headers_finish, "完成-周常: ")
        log += "周常任务完成\n"
    else:
        log += "周常任务已完成或未达时间\n"

    return log.rstrip()


def main():
    cookies = get_cookies()
    print("✅ 检测到", len(cookies), "个 SouthPlus 账号\n")

    summary = []
    for idx, ck in enumerate(cookies, start=1):
        print(f"🙍🏻‍♂️ 第{idx}个账号开始")
        try:
            clean_cookie = normalize_cookie(ck)
            if not clean_cookie:
                raise Exception("COOKIE 清洗后为空，请检查环境变量格式")
            log = run_for_cookie(clean_cookie)
            summary.append(f"账号{idx}: \n{log}")
        except Exception as e:
            err_msg = f"账号{idx} 失败: {e}"
            summary.append(err_msg)
            print(f"❌ {err_msg}")

    result = "\n\n".join(summary)
    try:
        Push("SouthPlus签到", result)
    except Exception as err:
        print(f"❌ 推送失败: {err}")

    return result


if __name__ == "__main__":
    print(f"==== SouthPlus 签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")

    if random_signin:
        delay_seconds = random.randint(0, max_random_delay)
        if delay_seconds > 0:
            signin_time = datetime.now() + timedelta(seconds=delay_seconds)
            print(f"随机模式: 延迟 {format_time_remaining(delay_seconds)} 后签到")
            print(f"预计签到时间: {signin_time.strftime('%H:%M:%S')}")
            wait_with_countdown(delay_seconds)

    print("----------SouthPlus 开始签到----------")
    main()
    print("----------SouthPlus 签到完毕----------")
    print(f"==== SouthPlus 签到完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
