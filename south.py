"""
cron: 0 9 * * *
new Env('SouthPlus签到')

参考: SouthPlusQianDao_WebDriver-main 项目
使用 DrissionPage 替代 Selenium
"""

import os
import re
import sys
import time
import random
import json
import platform
from datetime import datetime, timedelta

# ============ DrissionPage 配置 ============
USE_DRISSIONPAGE = False
try:
    import DrissionPage
    USE_DRISSIONPAGE = True
    print("✅ 已加载 DrissionPage")
except ImportError:
    print("❌ 未安装 DrissionPage，请执行: pip install DrissionPage")
    sys.exit(1)

# ---------------- 统一通知模块加载 ----------------
hadsend = False
send = None
try:
    from notify import send
    hadsend = True
    print("✅ 已加载notify.py通知模块")
except ImportError:
    print("⚠️  未加载通知模块，跳过通知功能")

# 配置
DRISSIONPAGE_HEADLESS = os.getenv("DRISSIONPAGE_HEADLESS", "true").lower() == "true"
DRISSIONPAGE_CHROME_PATH = os.getenv("DRISSIONPAGE_CHROME_PATH", "").strip()

# 随机延迟配置
max_random_delay = int(os.getenv("MAX_RANDOM_DELAY", "3600"))
random_signin = os.getenv("RANDOM_SIGNIN", "true").lower() == "true"

# 站点配置
DEFAULT_SITE = "https://south-plus.net"


def find_chrome_path() -> str:
    """自动检测 Chrome/Chromium 浏览器路径"""
    system = platform.system()
    
    if DRISSIONPAGE_CHROME_PATH:
        return DRISSIONPAGE_CHROME_PATH
    
    paths = []
    
    if system == "Windows":
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        local_app_data = os.environ.get("LOCALAPPDATA", "C:\\Users\\{}\\AppData\\Local".format(os.environ.get("USERNAME", "")))
        
        paths = [
            os.path.join(program_files, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files_x86, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(local_app_data, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files, "Microsoft\\Edge\\Application\\msedge.exe"),
            os.path.join(local_app_data, "Microsoft\\Edge\\Application\\msedge.exe"),
        ]
    elif system == "Darwin":
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:  # Linux / Docker
        paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
    
    for path in paths:
        if os.path.exists(path):
            print(f"[DrissionPage] 自动检测到浏览器: {path}")
            return path
    
    return None


def init_browser():
    """初始化浏览器"""
    try:
        co = DrissionPage.ChromiumOptions()
        
        co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--disable-gpu')
        co.auto_port()
        
        if DRISSIONPAGE_HEADLESS:
            co.headless(True)
        
        chrome_path = find_chrome_path()
        if chrome_path:
            co.set_browser_path(chrome_path)
        else:
            print("⚠️ 未找到浏览器，尝试使用系统默认浏览器")
        
        browser = DrissionPage.ChromiumPage(co)
        return browser
    
    except Exception as e:
        raise Exception(f"浏览器初始化失败: {e}")


def get_cookies():
    """读取环境变量 COOKIE，支持 JSON 格式和普通字符串格式"""
    cookie_str = os.environ.get("COOKIE", "").strip()
    
    if not cookie_str:
        print("❌ 未设置 COOKIE 环境变量")
        Push("SouthPlus签到", "❌ 未设置 COOKIE 环境变量")
        sys.exit(0)
    
    # 尝试解析为 JSON 格式（旧脚本格式）
    try:
        cookie_list = json.loads(cookie_str)
        if isinstance(cookie_list, list):
            print(f"✅ 检测到 JSON 格式 Cookie，共 {len(cookie_list)} 个")
            return cookie_list, "json"
    except json.JSONDecodeError:
        pass
    
    # 普通字符串格式，支持多账号
    cookie_list = [c.strip() for c in re.split(r"\n|&&", cookie_str) if c.strip()]
    print(f"✅ 检测到字符串格式 Cookie，共 {len(cookie_list)} 个账号")
    return cookie_list, "string"


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
    print(f"签到需要等待 {format_time_remaining(delay_seconds)}")
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


def wait_for_cloudflare(browser, max_wait: int = 60):
    """等待 Cloudflare 验证通过"""
    waited = 0
    while waited < max_wait:
        html = browser.html
        html_lower = html.lower()
        
        if "cloudflare" in html_lower or "just a moment" in html_lower or "cf-challenge" in html_lower:
            print(f"[DrissionPage] 等待 Cloudflare 验证... ({waited}s)")
            time.sleep(5)
            waited += 5
        else:
            print("[DrissionPage] ✅ Cloudflare 验证已通过")
            return True
    
    print("[DrissionPage] ⚠️ Cloudflare 验证超时")
    return False


def do_task(browser, site_base: str) -> str:
    """执行任务流程"""
    log_lines = []
    
    # 任务页面 URL
    task_url = f"{site_base}/plugin.php?H_name-tasks.html.html"
    
    print(f"[DrissionPage] 访问任务页面: {task_url}")
    browser.get(task_url)
    time.sleep(3)
    
    # 等待 Cloudflare
    wait_for_cloudflare(browser)
    time.sleep(2)
    
    # 检查登录状态
    if "您还没有登录" in browser.html or "您还没有登录或注册" in browser.html:
        return "❌ Cookie 无效或已过期：站点返回未登录"
    
    # ===== 步骤1: 申请任务 =====
    log_lines.append("📋 步骤1: 申请任务")
    
    # 查找可申请的任务 (p_14=周常, p_15=日常)
    apply_count = 0
    
    # 尝试点击日常任务 (p_15)
    try:
        daily_task = browser.ele('#p_15 a img', timeout=2)
        if daily_task:
            daily_task.click()
            print("[DrissionPage] ✅ 日常任务申请成功")
            log_lines.append("   ✅ 日常任务申请成功")
            apply_count += 1
            time.sleep(1)
    except Exception as e:
        print(f"[DrissionPage] 日常任务申请: {e}")
        log_lines.append("   日常任务暂不可申请或已申请")
    
    # 尝试点击周常任务 (p_14)
    try:
        weekly_task = browser.ele('#p_14 a img', timeout=2)
        if weekly_task:
            weekly_task.click()
            print("[DrissionPage] ✅ 周常任务申请成功")
            log_lines.append("   ✅ 周常任务申请成功")
            apply_count += 1
            time.sleep(1)
    except Exception as e:
        print(f"[DrissionPage] 周常任务申请: {e}")
        log_lines.append("   周常任务暂不可申请或已申请")
    
    # ===== 步骤2: 完成任务 =====
    log_lines.append("📋 步骤2: 完成任务")
    
    # 切换到进行中的任务
    try:
        in_progress_tab = browser.ele('xpath://*[@id="main"]/table/tbody/tr/td[1]/div[2]/table/tbody/tr[3]/td', timeout=3)
        if in_progress_tab:
            in_progress_tab.click()
            print("[DrissionPage] 切换到进行中任务")
            time.sleep(2)
    except Exception as e:
        print(f"[DrissionPage] 切换任务标签: {e}")
    
    # 完成日常任务 (both_15)
    try:
        daily_complete = browser.ele('#both_15 a img', timeout=2)
        if daily_complete:
            daily_complete.click()
            print("[DrissionPage] ✅ 日常任务完成")
            log_lines.append("   ✅ 日常任务完成")
            time.sleep(1)
    except Exception as e:
        print(f"[DrissionPage] 日常任务完成: {e}")
        log_lines.append("   日常任务暂不可完成")
    
    # 完成周常任务 (both_14)
    try:
        weekly_complete = browser.ele('#both_14 a img', timeout=2)
        if weekly_complete:
            weekly_complete.click()
            print("[DrissionPage] ✅ 周常任务完成")
            log_lines.append("   ✅ 周常任务完成")
            time.sleep(1)
    except Exception as e:
        print(f"[DrissionPage] 周常任务完成: {e}")
        log_lines.append("   周常任务暂不可完成")
    
    # ===== 步骤3: 领取奖励 =====
    log_lines.append("📋 步骤3: 领取奖励")
    
    # 访问已完成任务页面
    finished_url = f"{site_base}/plugin.php?H_name-tasks-actions-endtasks.html.html"
    browser.get(finished_url)
    time.sleep(2)
    
    # 领取日常奖励
    try:
        daily_reward = browser.ele('#both_15 a img', timeout=2)
        if daily_reward:
            daily_reward.click()
            print("[DrissionPage] ✅ 日常奖励领取成功")
            log_lines.append("   ✅ 日常奖励领取成功")
            time.sleep(1)
    except Exception as e:
        print(f"[DrissionPage] 日常奖励领取: {e}")
        log_lines.append("   日常奖励暂不可领取")
    
    # 领取周常奖励
    try:
        weekly_reward = browser.ele('#both_14 a img', timeout=2)
        if weekly_reward:
            weekly_reward.click()
            print("[DrissionPage] ✅ 周常奖励领取成功")
            log_lines.append("   ✅ 周常奖励领取成功")
            time.sleep(1)
    except Exception as e:
        print(f"[DrissionPage] 周常奖励领取: {e}")
        log_lines.append("   周常奖励暂不可领取")
    
    return "\n".join(log_lines)


def run_for_cookie_json(cookie_list: list, site_base: str) -> str:
    """使用 JSON 格式 cookie 执行任务（旧脚本格式）"""
    browser = None
    try:
        browser = init_browser()
        
        # 先访问首页
        print(f"[DrissionPage] 访问首页: {site_base}")
        browser.get(site_base)
        time.sleep(2)
        
        # 等待 Cloudflare
        wait_for_cloudflare(browser)
        
        # 添加 cookies（Selenium 风格）
        print(f"[DrissionPage] 设置 {len(cookie_list)} 个 Cookie...")
        for cookie in cookie_list:
            try:
                # DrissionPage 使用 set.cookies 方法
                browser.set.cookies(cookie)
            except Exception as e:
                print(f"[DrissionPage] 设置 cookie 失败: {e}")
        
        # 刷新页面使 cookie 生效
        browser.refresh()
        time.sleep(2)
        
        # 执行任务
        return do_task(browser, site_base)
    
    except Exception as e:
        return f"❌ 执行失败: {e}"
    
    finally:
        if browser:
            try:
                browser.quit()
            except:
                pass


def run_for_cookie_string(cookie_str: str, site_base: str) -> str:
    """使用字符串格式 cookie 执行任务"""
    browser = None
    try:
        browser = init_browser()
        
        # 先访问首页
        print(f"[DrissionPage] 访问首页: {site_base}")
        browser.get(site_base)
        time.sleep(2)
        
        # 等待 Cloudflare
        wait_for_cloudflare(browser)
        
        # 设置 cookies
        print("[DrissionPage] 设置 Cookie...")
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                name, value = item.split('=', 1)
                name = name.strip()
                value = value.strip()
                if name and value:
                    try:
                        # 使用字典格式设置 cookie
                        browser.set.cookies({'name': name, 'value': value})
                    except Exception as e:
                        print(f"[DrissionPage] 设置 cookie {name} 失败: {e}")
        
        # 刷新页面使 cookie 生效
        browser.refresh()
        time.sleep(2)
        
        # 执行任务
        return do_task(browser, site_base)
    
    except Exception as e:
        return f"❌ 执行失败: {e}"
    
    finally:
        if browser:
            try:
                browser.quit()
            except:
                pass


def main():
    cookie_list, cookie_type = get_cookies()
    site_base = os.getenv("SOUTHPLUS_SITE", DEFAULT_SITE).strip().rstrip("/")
    
    print(f"\n✅ 检测到 {len(cookie_list)} 个 SouthPlus 账号")
    print(f"✅ 站点: {site_base}")
    print(f"✅ 无头模式: {DRISSIONPAGE_HEADLESS}\n")
    
    summary = []
    
    for idx, ck in enumerate(cookie_list, start=1):
        print(f"🙍🏻‍♂️ 第{idx}个账号开始")
        try:
            if cookie_type == "json":
                result = run_for_cookie_json(ck, site_base)
            else:
                result = run_for_cookie_string(ck, site_base)
            
            print(result)
            summary.append(f"账号{idx}:\n{result}")
        except Exception as e:
            err_msg = f"账号{idx} 失败: {e}"
            summary.append(err_msg)
            print(f"❌ {err_msg}")
    
    result = "\n\n".join(summary)
    print("\n========== 本次执行汇总 ==========")
    print(result)
    
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
