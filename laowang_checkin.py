#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
老王论坛自动签到（青龙精简版，仅保留浏览器模式，直接处理滑块）

环境变量：
- LAOWANG_ACCOUNT=username:password&user2:pwd2   # 必填，多账号用 & 或换行分隔
- LAOWANG_BROWSER_PATH=/usr/bin/chromium         # 可选，默认自动探测
- LAOWANG_USER_DATA_DIR=/tmp/laowang_dp          # 可选，用户数据目录基路径
- LAOWANG_PROXY=http://ip:port                   # 可选，国内需代理时设置

cron: 0 9 * * *
"""

import os
import time
import random
import logging
from pathlib import Path

import DrissionPage

BASE_URL = "https://laowang.vip/plugin.php?id=k_misign:sign"
# 可选自定义解析 IP（用于 hosts 绑定）
CUSTOM_HOST = os.getenv("LAOWANG_CUSTOM_HOST", "104.21.14.105").strip()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_browser_path():
    env_paths = [
        os.getenv("LAOWANG_BROWSER_PATH", "").strip(),
        os.getenv("BROWSER_PATH", "").strip(),
    ]
    for p in env_paths:
        if p and os.path.exists(p):
            logger.info(f"✅ 使用环境变量指定的浏览器: {p}")
            return p
    common = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    for p in common:
        if os.path.exists(p):
            logger.info(f"✅ 自动找到浏览器: {p}")
            return p
    logger.warning("⚠️ 未找到浏览器，可设置 LAOWANG_BROWSER_PATH")
    return None


def pass_slide_verification(browser):
    max_attempts = 100
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        browser.wait.ele_displayed(".slide_block")
        slider = browser.ele(".slide_block")
        time.sleep(0.1)
        for distance in range(80, 161, 10):
            try:
                browser.actions.move_to(slider)
                time.sleep(0.05)
                browser.actions.hold()
                steps = 3
                step_d = distance / steps
                for _ in range(steps):
                    browser.actions.move(step_d, 0)
                    time.sleep(0.05)
                browser.actions.release()
                time.sleep(0.6)
                try:
                    tncode_div = browser.ele("#tncode_div")
                    display_style = browser.run_js("return arguments[0].style.display", tncode_div)
                    if display_style == "none":
                        logger.info("✅ 滑块验证通过")
                        return True
                    time.sleep(0.5)
                except Exception:
                    pass
            except Exception:
                continue
    logger.error(f"❌ 滑块验证失败，已达 {max_attempts} 次尝试")
    return False


def build_chromium_options():
    co = DrissionPage.ChromiumOptions()
    browser_path = get_browser_path()
    if browser_path:
        try:
            co.set_browser_path(browser_path)
        except Exception:
            co.browser_path = browser_path

    co.set_user_agent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.6723.92 Safari/537.36"
    )
    co.set_pref("credentials_enable_service", False)
    co.set_argument("--hide-crash-restore-bubble")

    # 容器兼容参数
    co.headless(True)
    co.set_argument("--headless=new")
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-setuid-sandbox")
    co.set_argument("--disable-gpu")
    co.set_argument("--disable-dev-shm-usage")
    co.set_argument("--no-zygote")
    co.set_argument("--disable-software-rasterizer")
    co.set_argument("--no-first-run")
    co.set_argument("--no-default-browser-check")
    co.set_argument("--disable-extensions")
    co.set_argument("--disable-background-networking")
    co.set_argument("--disable-features=TranslateUI,site-per-process,AutomationControlled")
    co.set_argument("--remote-allow-origins=*")

    # 自定义 hosts 绑定
    if CUSTOM_HOST:
        co.set_argument(f"--host-resolver-rules=MAP laowang.vip {CUSTOM_HOST}")
        logger.info(f"🌐 hosts 绑定: laowang.vip -> {CUSTOM_HOST}")

    proxy = os.getenv("LAOWANG_PROXY", "").strip()
    if proxy:
        co.set_argument(f"--proxy-server={proxy}")
        logger.info(f"🌐 使用代理: {proxy}")

    base_dir = os.getenv("LAOWANG_USER_DATA_DIR", "/tmp/laowang_dp")
    rand_suffix = f"run-{int(time.time())}-{random.randint(1000,9999)}"
    user_dir = os.path.join(base_dir, rand_suffix)
    Path(user_dir).mkdir(parents=True, exist_ok=True)
    co.set_argument(f"--user-data-dir={user_dir}")
    try:
        co.set_user_data_path(user_dir)
    except Exception:
        pass

    # 显式占用本地空闲端口，避免端口被占或为 0
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
        co.set_local_port(free_port)
        co.set_argument(f"--remote-debugging-port={free_port}")
        co.set_argument("--remote-debugging-address=127.0.0.1")
        logger.info(f"🛠️ 远程调试端口: {free_port}")
    except Exception as e:
        logger.warning(f"⚠️ 端口分配失败，使用 auto_port: {e}")
        co.auto_port()
    return co


def sign_one(account, pwd):
    co = build_chromium_options()
    browser = DrissionPage.ChromiumPage(co)
    try:
        browser.get(BASE_URL)
        time.sleep(1)
        try:
            btn = browser.ele("@class=btn J_chkitot", timeout=5)
            btn.click()
            time.sleep(0.5)
        except Exception:
            pass

        browser.ele("@name=username").input(account)
        browser.ele("@name=password").input(pwd)

        try:
            tn = browser.ele("@class=tncode", timeout=3)
            tn.click()
            if not pass_slide_verification(browser):
                return False, "滑块验证失败(登录)"
        except Exception:
            logger.debug("登录阶段未触发滑块")

        browser.ele("@name=loginsubmit").click()
        time.sleep(2)

        browser.get(BASE_URL)
        time.sleep(1)

        if any(x in browser.html for x in ["今日已签", "btnvisted", "签到成功", "恭喜您签到成功"]):
            return True, "今日已签到"

        try:
            btn = browser.ele("@class=btn J_chkitot", timeout=5)
            btn.click()
            time.sleep(0.5)
        except Exception as e:
            return False, f"找不到签到按钮: {e}"

        try:
            tn = browser.ele("@class=tncode", timeout=3)
            tn.click()
            if not pass_slide_verification(browser):
                return False, "滑块验证失败(签到)"
        except Exception:
            logger.debug("签到阶段未触发滑块")

        try:
            browser.ele("@id=submit-btn", timeout=5).click()
        except Exception:
            pass
        time.sleep(2)

        if any(x in browser.html for x in ["今日已签", "btnvisted", "签到成功", "恭喜您签到成功"]):
            return True, "签到成功"
        return False, "签到状态未知"
    finally:
        try:
            browser.quit()
        except Exception:
            pass


def parse_accounts():
    env_str = os.getenv("LAOWANG_ACCOUNT", "").strip()
    if not env_str:
        return []
    accounts = []
    for item in env_str.replace("\n", "&").split("&"):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            user, pwd = item.split(":", 1)
            accounts.append((user.strip(), pwd.strip()))
    return accounts


def main():
    accounts = parse_accounts()
    if not accounts:
        print("❌ 未配置 LAOWANG_ACCOUNT=账号:密码 (&分隔多账号)")
        return

    results = []
    for idx, (user, pwd) in enumerate(accounts, 1):
        print("─" * 40)
        print(f"账号 {idx}: {user}")
        ok, msg = sign_one(user, pwd)
        results.append((user, ok, msg))
        print(("✅" if ok else "❌"), msg)
        if idx < len(accounts):
            time.sleep(random.uniform(2, 5))

    print("\n结果汇总：")
    for user, ok, msg in results:
        print(f"{ '✅' if ok else '❌' } {user}: {msg}")


if __name__ == "__main__":
    main()
