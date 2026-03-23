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

common_params = {
    "H_name": "tasks",
    "action": "ajax",
    "nowtime": "1717167492479",
    "verify": "5af36471",
}

ad_params = {**common_params, "actions": "job", "cid": "15"}
aw_params = {**common_params, "actions": "job", "cid": "14"}
cd_params = {**common_params, "actions": "job2", "cid": "15"}
cw_params = {**common_params, "actions": "job2", "cid": "14"}


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


def tasks(params: dict, headers: dict, action_desc: str) -> bool:
    response = requests.get(url, params=params, headers=headers)
    response.encoding = "utf-8"
    data = response.text

    root = ET.fromstring(data)
    cdata = root.text or ""

    values = cdata.split("\t")
    if "申请" in action_desc:
        value_len = 2
    else:
        value_len = 3

    if len(values) == value_len:
        message = values[1]
        print(action_desc + message)
    else:
        raise Exception("XML格式不正确，请检查COOKIE设置")

    return "还没超过" not in message


def run_for_cookie(cookie: str) -> str:
    """单账号执行签到任务并返回日志"""
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
            log = run_for_cookie(ck.replace("\n", "").replace(" ", ""))
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
