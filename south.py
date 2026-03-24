"""
cron: 0 9 * * *
new Env('SouthPlus签到')
"""

import os
import re
import sys
import time
import random
import platform
from datetime import datetime, timedelta

# ============ DrissionPage 配置 ============
USE_DRISSIONPAGE = False
try:
    import DrissionPage
    USE_DRISSIONPAGE = True
    print("✅ 已加载 DrissionPage，可自动绕过 Cloudflare 验证")
except ImportError:
    print("⚠️ 未安装 DrissionPage，尝试使用 cloudscraper")
    print("   如需自动绕过 Cloudflare，请执行: pip install DrissionPage")

# 尝试导入 cloudscraper 用于绕过 Cloudflare，如未安装则回退到 requests
try:
    import cloudscraper
    scraper = cloudscraper.create_scraper()
    USE_CLOUDSCRAPER = True
    print("✅ 已加载 cloudscraper，可自动处理 Cloudflare 验证")
except ImportError:
    import requests
    scraper = None
    USE_CLOUDSCRAPER = False
    if not USE_DRISSIONPAGE:
        print("⚠️ 未安装 cloudscraper，使用标准 requests（可能被 Cloudflare 拦截）")
        print("   如需绕过 Cloudflare，请执行: pip install cloudscraper")

# 从环境变量读取 cf_clearance（用于手动绕过 Cloudflare）
CF_CLEARANCE = os.getenv("CF_CLEARANCE", "").strip()
if CF_CLEARANCE:
    print(f"✅ 已配置 CF_CLEARANCE，长度: {len(CF_CLEARANCE)}")

# 包装请求函数，统一使用 cloudscraper 或 requests
def make_request(method, url, **kwargs):
    """统一请求函数，优先使用 cloudscraper 绕过 Cloudflare"""
    if USE_CLOUDSCRAPER and scraper:
        req_func = getattr(scraper, method.lower())
    else:
        import requests
        req_func = getattr(requests, method.lower())
    return req_func(url, **kwargs)


# ============== DrissionPage CF 绕过功能 ==============

# DrissionPage 配置
DRISSIONPAGE_HEADLESS = os.getenv("DRISSIONPAGE_HEADLESS", "true").lower() == "true"
DRISSIONPAGE_CHROME_PATH = os.getenv("DRISSIONPAGE_CHROME_PATH", "").strip()


def find_chrome_path() -> str:
    """自动检测 Chrome/Chromium 浏览器路径"""
    system = platform.system()
    
    # 如果环境变量已指定，直接使用
    if DRISSIONPAGE_CHROME_PATH:
        return DRISSIONPAGE_CHROME_PATH
    
    # 常见浏览器路径
    paths = []
    
    if system == "Windows":
        # Windows 路径
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        local_app_data = os.environ.get("LOCALAPPDATA", "C:\\Users\\{}\\AppData\\Local".format(os.environ.get("USERNAME", "")))
        
        paths = [
            os.path.join(program_files, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files_x86, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(local_app_data, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files, "Microsoft\\Edge\\Application\\msedge.exe"),
            os.path.join(program_files_x86, "Microsoft\\Edge\\Application\\msedge.exe"),
            os.path.join(local_app_data, "Microsoft\\Edge\\Application\\msedge.exe"),
            # Chromium
            os.path.join(local_app_data, "Chromium\\Application\\chrome.exe"),
        ]
    elif system == "Darwin":  # macOS
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    else:  # Linux / Docker / 青龙面板
        paths = [
            # 标准 Chrome 路径
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            # Chromium 路径（常见于 Docker）
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            # Alpine Linux 路径
            "/usr/bin/chromium-browser",
            # Snap 路径
            "/snap/bin/chromium",
            # Edge
            "/usr/bin/microsoft-edge",
            "/usr/bin/microsoft-edge-stable",
            # 青龙面板常见自定义安装路径
            "/ql/data/scripts/chrome/chrome",
            "/ql/scripts/chrome/chrome",
            "/root/chrome/chrome",
        ]
    
    # 检查路径是否存在
    for path in paths:
        if os.path.exists(path):
            print(f"[DrissionPage] 自动检测到浏览器: {path}")
            return path
    
    # 未找到浏览器
    return None


def init_browser(headless: bool = True, proxy: str = None):
    """初始化 DrissionPage 浏览器"""
    if not USE_DRISSIONPAGE:
        raise Exception("DrissionPage 未安装，无法使用 CF 绕过功能")
    
    try:
        co = DrissionPage.ChromiumOptions()
        
        # 基础配置
        co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')
        co.set_pref('credentials_enable_service', False)
        co.set_argument('--hide-crash-restore-bubble')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--disable-gpu')
        co.auto_port()
        
        # 无头模式
        if headless:
            co.headless(True)
        
        # 指定浏览器路径
        chrome_path = find_chrome_path()
        if chrome_path:
            co.set_browser_path(chrome_path)
        else:
            system = platform.system()
            error_msg = f"""
未找到 Chrome/Chromium 浏览器！请安装或指定路径。

【青龙面板/Docker 环境安装 Chrome 方法】

方法1: 使用 apt 安装 Chromium（推荐）
  docker exec -it <容器名> bash
  apt update && apt install -y chromium chromium-driver

方法2: 安装完整 Chrome
  docker exec -it <容器名> bash
  wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
  echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
  apt update && apt install -y google-chrome-stable

方法3: 使用自定义 Docker 镜像
  使用已包含 Chrome 的青龙面板镜像，如:
  - whyour/qinglong:latest (部分版本已包含)
  - 或自行构建包含 Chrome 的镜像

方法4: 设置环境变量指定路径
  在青龙面板 -> 环境变量 中添加:
  DRISSIONPAGE_CHROME_PATH=/usr/bin/chromium

当前系统: {system}
"""
            raise Exception(error_msg)
        
        # 代理配置
        if proxy:
            co.set_argument(f'--proxy-server={proxy}')
        
        browser = DrissionPage.ChromiumPage(co)
        return browser
    
    except Exception as e:
        raise Exception(f"浏览器初始化失败: {e}")


def drissionpage_get_cf_clearance(site_base: str, cookie_str: str = None) -> dict:
    """
    使用 DrissionPage 访问网站，绕过 Cloudflare 并获取 cookies
    
    Args:
        site_base: 站点基础 URL（如 https://south-plus.net）
        cookie_str: 用户 cookie 字符串（可选，用于设置登录状态）
    
    Returns:
        包含 cookies 和页面 HTML 的字典
    """
    browser = None
    try:
        browser = init_browser(headless=DRISSIONPAGE_HEADLESS, proxy=proxy_url or None)
        
        # 先访问首页设置 cookies
        print(f"[DrissionPage] 正在访问首页: {site_base}")
        browser.get(site_base)
        time.sleep(2)
        
        # 如果提供了用户 cookie，设置到浏览器
        if cookie_str:
            print("[DrissionPage] 正在设置用户 Cookie...")
            # 解析并设置 cookies
            for item in cookie_str.split(';'):
                item = item.strip()
                if '=' in item:
                    name, value = item.split('=', 1)
                    name = name.strip()
                    value = value.strip()
                    if name and value:
                        try:
                            browser.set.cookies.set(name, value, domain=site_base.replace('https://', '').replace('http://', ''))
                        except Exception as e:
                            print(f"[DrissionPage] 设置 cookie {name} 失败: {e}")
            
            # 刷新页面使 cookie 生效
            browser.refresh()
            time.sleep(2)
        
        # 检查是否在 Cloudflare 验证页面
        max_wait = 30
        waited = 0
        while waited < max_wait:
            html = browser.html
            html_lower = html.lower()
            
            # 检查是否仍在 Cloudflare 验证中
            if "cloudflare" in html_lower or "just a moment" in html_lower or "cf-challenge" in html_lower:
                print(f"[DrissionPage] 等待 Cloudflare 验证... ({waited}s)")
                time.sleep(3)
                waited += 3
            else:
                print("[DrissionPage] ✅ Cloudflare 验证已通过")
                break
        
        # 获取所有 cookies
        cookies = browser.cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        cookie_str_result = "; ".join([f"{name}={value}" for name, value in cookie_dict.items()])
        
        # 获取页面 HTML
        html = browser.html
        
        # 提取 cf_clearance
        cf_clearance = cookie_dict.get('cf_clearance', '')
        if cf_clearance:
            print(f"[DrissionPage] ✅ 已获取 cf_clearance: {cf_clearance[:20]}...")
        else:
            print("[DrissionPage] ⚠️ 未获取到 cf_clearance，可能 Cloudflare 未启用或已通过")
        
        return {
            'cookies': cookie_str_result,
            'cookie_dict': cookie_dict,
            'html': html,
            'cf_clearance': cf_clearance,
            'url': browser.url,
        }
    
    finally:
        if browser:
            try:
                browser.quit()
            except:
                pass


def drissionpage_do_tasks(site_base: str, cookie_str: str) -> dict:
    """
    使用 DrissionPage 完成完整的任务流程
    
    任务流程：
    1. 新任务选择 -> 申请任务 (job)
    2. 进行中任务 -> 完成任务 (job)  
    3. 已完成任务 -> 领取奖励 (job2)
    
    Args:
        site_base: 站点基础 URL
        cookie_str: 用户 cookie 字符串
    
    Returns:
        包含执行结果的字典
    """
    browser = None
    try:
        browser = init_browser(headless=DRISSIONPAGE_HEADLESS, proxy=proxy_url or None)
        
        # 访问首页并设置 cookies
        print(f"[DrissionPage] 正在访问首页: {site_base}")
        browser.get(site_base)
        time.sleep(2)
        
        # 设置用户 cookie
        print("[DrissionPage] 正在设置用户 Cookie...")
        domain = site_base.replace('https://', '').replace('http://', '')
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                name, value = item.split('=', 1)
                name = name.strip()
                value = value.strip()
                if name and value:
                    try:
                        browser.set.cookies.set(name, value, domain=domain)
                    except Exception as e:
                        print(f"[DrissionPage] 设置 cookie {name} 失败: {e}")
        
        # 刷新页面使 cookie 生效
        browser.refresh()
        time.sleep(2)
        
        # 等待 Cloudflare 验证
        max_wait = 30
        waited = 0
        while waited < max_wait:
            html = browser.html
            html_lower = html.lower()
            if "cloudflare" in html_lower or "just a moment" in html_lower or "cf-challenge" in html_lower:
                print(f"[DrissionPage] 等待 Cloudflare 验证... ({waited}s)")
                time.sleep(3)
                waited += 3
            else:
                print("[DrissionPage] ✅ Cloudflare 验证已通过")
                break
        
        log_lines = [f"站点: {site_base}"]
        
        # ===== 步骤1: 新任务选择 -> 申请任务 =====
        log_lines.append("📋 步骤1: 新任务选择 - 申请任务")
        task_url = f"{site_base}/plugin.php?H_name-tasks.html"
        print(f"[DrissionPage] 访问任务页面: {task_url}")
        browser.get(task_url)
        time.sleep(2)
        
        # 检查登录状态
        if "您还没有登录" in browser.html or "您还没有登录或注册" in browser.html:
            raise Exception("Cookie 无效或已过期：站点返回未登录")
        
        # 查找并点击申请任务按钮
        apply_count = 0
        try:
            # 查找所有 startjob 调用
            html = browser.html
            jobs = re.findall(r"startjob\(\s*'?(\d+)'?\s*,\s*'?(\w{6,64})'?\s*\)", html, flags=re.IGNORECASE)
            
            if jobs:
                log_lines.append(f"   检测到可申请任务: {len(jobs)}")
                for cid, verify in jobs:
                    try:
                        # 执行 startjob
                        js_code = f"startjob('{cid}', '{verify}')"
                        browser.run_js(js_code)
                        time.sleep(0.5)
                        apply_count += 1
                        print(f"[DrissionPage] 申请任务 cid={cid}")
                    except Exception as e:
                        print(f"[DrissionPage] 申请任务 cid={cid} 失败: {e}")
            else:
                log_lines.append("   未检测到可申请任务")
        except Exception as e:
            log_lines.append(f"   申请任务异常: {e}")
        
        # ===== 步骤2: 进行中任务 -> 完成任务 =====
        log_lines.append("📋 步骤2: 进行中任务 - 完成任务")
        current_url = f"{site_base}/plugin.php?H_name-tasks-actions-newtasks.html.html"
        print(f"[DrissionPage] 访问进行中任务: {current_url}")
        browser.get(current_url)
        time.sleep(2)
        
        complete_count = 0
        try:
            html = browser.html
            jobs = re.findall(r"startjob\(\s*'?(\d+)'?\s*,\s*'?(\w{6,64})'?\s*\)", html, flags=re.IGNORECASE)
            
            if jobs:
                log_lines.append(f"   检测到进行中任务: {len(jobs)}")
                for cid, verify in jobs:
                    try:
                        js_code = f"startjob('{cid}', '{verify}')"
                        browser.run_js(js_code)
                        time.sleep(0.5)
                        complete_count += 1
                        print(f"[DrissionPage] 完成任务 cid={cid}")
                    except Exception as e:
                        print(f"[DrissionPage] 完成任务 cid={cid} 失败: {e}")
            else:
                log_lines.append("   未检测到进行中任务")
        except Exception as e:
            log_lines.append(f"   完成任务异常: {e}")
        
        # ===== 步骤3: 已完成任务 -> 领取奖励 =====
        log_lines.append("📋 步骤3: 已完成任务 - 领取奖励")
        finished_url = f"{site_base}/plugin.php?H_name-tasks-actions-endtasks.html.html"
        print(f"[DrissionPage] 访问已完成任务: {finished_url}")
        browser.get(finished_url)
        time.sleep(2)
        
        reward_count = 0
        try:
            html = browser.html
            jobs = re.findall(r"startjob\(\s*'?(\d+)'?\s*,\s*'?(\w{6,64})'?\s*\)", html, flags=re.IGNORECASE)
            
            if jobs:
                log_lines.append(f"   检测到可领取奖励: {len(jobs)}")
                for cid, verify in jobs:
                    try:
                        js_code = f"startjob('{cid}', '{verify}')"
                        browser.run_js(js_code)
                        time.sleep(0.5)
                        reward_count += 1
                        print(f"[DrissionPage] 领取奖励 cid={cid}")
                    except Exception as e:
                        print(f"[DrissionPage] 领取奖励 cid={cid} 失败: {e}")
            else:
                log_lines.append("   未检测到可领取奖励")
        except Exception as e:
            log_lines.append(f"   领取奖励异常: {e}")
        
        return {
            'success': True,
            'log': "\n".join(log_lines),
            'apply_count': apply_count,
            'complete_count': complete_count,
            'reward_count': reward_count,
        }
    
    except Exception as e:
        return {
            'success': False,
            'log': f"执行失败: {e}",
            'error': str(e),
        }
    
    finally:
        if browser:
            try:
                browser.quit()
            except:
                pass


def add_cf_clearance_to_cookie(cookie: str) -> str:
    """将 cf_clearance 添加到 cookie 字符串中"""
    if not CF_CLEARANCE:
        return cookie
    
    # 检查是否已存在 cf_clearance
    if "cf_clearance" in cookie:
        # 替换现有的 cf_clearance
        pattern = r"cf_clearance=[^;]*"
        cookie = re.sub(pattern, f"cf_clearance={CF_CLEARANCE}", cookie)
    else:
        # 添加 cf_clearance
        cookie = f"{cookie}; cf_clearance={CF_CLEARANCE}" if cookie else f"cf_clearance={CF_CLEARANCE}"
    
    return cookie

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
request_timeout = int(os.getenv("SOUTHPLUS_TIMEOUT", "20"))

# 代理：优先 SOUTHPLUS_PROXY，兼容 MY_PROXY
proxy_url = os.getenv("SOUTHPLUS_PROXY", "").strip() or os.getenv("MY_PROXY", "").strip()
proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

DEFAULT_SITE_BASES = [
    "https://north-plus.net",
    "https://south-plus.net",
    "https://east-plus.net",
    "https://white-plus.net",
    "https://level-plus.net",
    "https://soul-plus.net",
    "https://snow-plus.net",
    "https://spring-plus.net",
    "https://summer-plus.net",
    "https://blue-plus.net",
    "https://imoutolove.me",
]

base_headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    # requests 原生不支持 br/zstd，避免服务端返回无法正常解码的内容
    "accept-encoding": "gzip, deflate",
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


def get_site_bases():
    """读取可用站点列表，支持 SOUTHPLUS_BASES / SOUTHPLUS_BASE。"""
    fixed_site = os.getenv("SOUTHPLUS_SITE", "https://south-plus.net").strip()
    bases_raw = os.getenv("SOUTHPLUS_BASES", "").strip()
    single_base = os.getenv("SOUTHPLUS_BASE", "").strip()

    if fixed_site:
        bases = [fixed_site.rstrip("/")]
    elif bases_raw:
        bases = [b.strip().rstrip("/") for b in re.split(r"\n|&&|,", bases_raw) if b.strip()]
    elif single_base:
        bases = [single_base.rstrip("/")]
    else:
        bases = DEFAULT_SITE_BASES[:]

    return bases


def normalize_cookie(raw_cookie: str) -> str:
    """规范化 cookie 字符串"""
    # 去除多余空白
    cookie = " ".join(raw_cookie.split())
    # 确保键值对格式正确
    parts = []
    for part in cookie.split(";"):
        part = part.strip()
        if part and "=" in part:
            parts.append(part)
    return "; ".join(parts)


def parse_message_from_response(data: str) -> str:
    """尽量从返回内容中提取任务提示消息。"""
    if not data:
        return ""
    try:
        # 尝试解析 XML 格式
        if data.strip().startswith("<"):
            try:
                root = ET.fromstring(data.strip())
                # 尝试 CDATA
                if root.text:
                    return root.text.strip()
                for child in root.iter():
                    if child.text and len(child.text.strip()) > 2:
                        return child.text.strip()
            except ET.ParseError:
                pass
        # 尝试 JSON
        if data.strip().startswith("{"):
            try:
                import json
                jd = json.loads(data)
                if isinstance(jd, dict):
                    for key in ["message", "msg", "info", "data"]:
                        if key in jd and jd[key]:
                            return str(jd[key])
            except json.JSONDecodeError:
                pass
        # 纯文本
        text = re.sub(r"<[^>]+>", "", data).strip()
        if text:
            return text[:200]
    except Exception:
        pass
    return ""


def run_for_cookie_drissionpage(cookie: str, site_base: str) -> str:
    """使用 DrissionPage 执行签到任务"""
    result = drissionpage_do_tasks(site_base, cookie)
    return result.get('log', '执行完成')


def run_for_cookie_requests(cookie: str, site_base: str) -> str:
    """使用传统 requests 方式执行签到任务（备用）"""
    url = f"{site_base}/plugin.php"

    headers_apply = {**base_headers, "cookie": cookie, "referer": url + "?H_name-tasks.html"}
    headers_finish = {
        **base_headers,
        "cookie": cookie,
        "authority": site_base.replace("https://", "").replace("http://", ""),
        "method": "GET",
        "path": "/plugin.php?H_name-tasks-actions-newtasks.html.html",
        "scheme": "https" if site_base.startswith("https://") else "http",
        "Referer": url + "?H_name-tasks-actions-newtasks.html.html",
    }
    headers_reward = {
        **base_headers,
        "cookie": cookie,
        "authority": site_base.replace("https://", "").replace("http://", ""),
        "method": "GET",
        "path": "/plugin.php?H_name-tasks-actions-endtasks.html.html",
        "scheme": "https" if site_base.startswith("https://") else "http",
        "Referer": url + "?H_name-tasks-actions-endtasks.html.html",
    }

    log_lines = [f"站点: {site_base}"]

    # 1) 新任务选择 -> 申请任务（job）
    log_lines.append("📋 步骤1: 新任务选择 - 申请任务")
    new_tasks_html = fetch_task_page(cookie, site_base, "?H_name-tasks.html")
    apply_jobs = extract_jobs_from_html(new_tasks_html)
    if apply_jobs:
        log_lines.append(f"   检测到可申请任务: {len(apply_jobs)}")
    else:
        log_lines.append("   未检测到可申请任务")

    for cid, verify in apply_jobs:
        params = build_job_params("job", cid, verify)
        do_task_request(url, params, headers_apply, f"   申请任务(cid={cid}): ")
        time.sleep(0.15)

    # 2) 进行中任务 -> 完成任务（job）
    log_lines.append("📋 步骤2: 进行中任务 - 完成任务")
    current_tasks_html = fetch_task_page(cookie, site_base, "?H_name-tasks-actions-newtasks.html.html")
    complete_jobs = extract_jobs_from_html(current_tasks_html)
    if complete_jobs:
        log_lines.append(f"   检测到进行中任务: {len(complete_jobs)}")
    else:
        log_lines.append("   未检测到进行中任务")

    for cid, verify in complete_jobs:
        params = build_job_params("job", cid, verify)
        do_task_request(url, params, headers_finish, f"   完成任务(cid={cid}): ")
        time.sleep(0.15)

    # 3) 已完成任务 -> 领取奖励（job2）
    log_lines.append("📋 步骤3: 已完成任务 - 领取奖励")
    finished_tasks_html = fetch_task_page(cookie, site_base, "?H_name-tasks-actions-endtasks.html.html")
    reward_jobs = extract_jobs_from_html(finished_tasks_html)
    if reward_jobs:
        log_lines.append(f"   检测到可领取奖励: {len(reward_jobs)}")
    else:
        log_lines.append("   未检测到可领取奖励")

    for cid, verify in reward_jobs:
        params = build_job_params("job2", cid, verify)
        do_task_request(url, params, headers_reward, f"   领取奖励(cid={cid}): ")
        time.sleep(0.15)

    return "\n".join(log_lines)


def fetch_task_page(cookie: str, site_base: str, page_suffix: str, retry_with_drissionpage: bool = False) -> str:
    """抓取任务页面（自动按响应头编码解析）。
    
    Args:
        cookie: 用户 cookie
        site_base: 站点基础 URL
        page_suffix: 页面后缀
        retry_with_drissionpage: 是否已尝试用 DrissionPage
    """
    global CF_CLEARANCE
    
    url = f"{site_base}/plugin.php{page_suffix}"
    
    # 常规请求方式
    cookie_with_cf = add_cf_clearance_to_cookie(cookie)
    headers = {
        **base_headers,
        "cookie": cookie_with_cf,
        "referer": f"{site_base}/",
    }
    response = make_request("GET", url, headers=headers, timeout=request_timeout, proxies=proxies)
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    html = response.text or ""

    html_lower = html.lower()
    if "cloudflare" in html_lower or "just a moment" in html_lower or "cf-challenge" in html_lower:
        # 如果还没使用 DrissionPage，尝试用 DrissionPage
        if not retry_with_drissionpage and USE_DRISSIONPAGE:
            print("⚠️ 触发 Cloudflare 验证，尝试使用 DrissionPage...")
            try:
                result = drissionpage_get_cf_clearance(site_base, cookie)
                cf_clearance = result.get('cf_clearance', '')
                if cf_clearance:
                    CF_CLEARANCE = cf_clearance
                    print(f"[DrissionPage] ✅ 已获取 cf_clearance: {cf_clearance[:20]}...")
                    # 使用新获取的 cf_clearance 重新请求
                    return fetch_task_page(cookie, site_base, page_suffix, retry_with_drissionpage=True)
                else:
                    print("[DrissionPage] ⚠️ 未获取到 cf_clearance")
            except Exception as e:
                print(f"[DrissionPage] 获取 cf_clearance 失败: {e}")
        
        error_msg = """触发 Cloudflare 验证，无法直接请求。
解决方案：
1. 安装 DrissionPage（推荐）：
   pip install DrissionPage
    
2. 设置环境变量 CF_CLEARANCE：
   - 使用浏览器访问站点，通过 F12 -> Network 找到包含 cf_clearance 的请求
   - 复制 cf_clearance 的值
   - 设置环境变量: export CF_CLEARANCE="你的值"
    
3. 使用与浏览器同出口 IP 的代理：
   - 设置环境变量: export SOUTHPLUS_PROXY="http://代理地址:端口"
    
4. 在本地网络运行脚本（非服务器机房IP）"""
        raise Exception(error_msg)

    if "您还没有登录" in html or "您还没有登录或注册" in html:
        raise Exception("Cookie 无效或已过期：站点返回未登录")

    # 任务页有效性校验：避免误把重定向页/异常页当成功
    valid_markers = [
        "社区论坛任务",
        "按这申请此任务",
        "领取此奖励",
        "startjob(",
        "H_name-tasks",
    ]
    if not any(m in html for m in valid_markers):
        m_title = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        title = m_title.group(1).strip() if m_title else "未知页面"
        snippet = re.sub(r"\s+", " ", html).strip()[:120]
        raise Exception(f"任务页内容异常: {title} | 内容片段: {snippet or '空'}")

    return html


def extract_jobs_from_html(html: str):
    """从任务页提取 startjob(cid, verify) 列表。"""
    # 例: startjob('15','5af36471')
    matches = re.findall(
        r"startjob\(\s*'?(\d+)'?\s*,\s*'?(\w{6,64})'?\s*\)",
        html,
        flags=re.IGNORECASE,
    )
    jobs = []
    seen = set()
    for cid, verify in matches:
        key = (cid, verify)
        if key not in seen:
            seen.add(key)
            jobs.append(key)
    return jobs


def build_job_params(action: str, cid: str, verify: str):
    """构建任务请求参数"""
    return {
        "H_name": "tasks",
        "action": "ajax",
        "nowtime": str(int(time.time() * 1000)),
        "verify": verify,
        "actions": action,
        "cid": cid,
    }


def do_task_request(url: str, params: dict, headers: dict, action_desc: str) -> bool:
    """执行任务请求"""
    try:
        response = make_request("GET", url, params=params, headers=headers, timeout=request_timeout, proxies=proxies)
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        data = response.text or ""
        msg = parse_message_from_response(data)
        print(f"{action_desc}{msg or '完成'}")
        return True
    except Exception as e:
        print(f"{action_desc}失败: {e}")
        return False


def run_for_cookie(cookie: str, site_base: str) -> str:
    """单账号执行签到任务并返回日志
    
    优先使用 DrissionPage，失败则回退到 requests
    """
    # 优先使用 DrissionPage
    if USE_DRISSIONPAGE:
        print(f"[DrissionPage] 使用浏览器模式执行任务...")
        return run_for_cookie_drissionpage(cookie, site_base)
    else:
        print(f"[Requests] 使用传统请求模式执行任务...")
        return run_for_cookie_requests(cookie, site_base)


def main():
    cookies = get_cookies()
    site_bases = get_site_bases()
    print("✅ 检测到", len(cookies), "个 SouthPlus 账号\n")
    print("✅ 可尝试站点:", " | ".join(site_bases), "\n")
    if proxy_url:
        print(f"✅ 已启用代理: {proxy_url}\n")
    else:
        print("⚠️ 未启用代理：Cloudflare 站点大概率会拦截机房IP\n")
    
    # CF 绕过模式提示
    if USE_DRISSIONPAGE:
        print("🛡️ 已启用 DrissionPage Cloudflare 自动绕过模式（推荐）\n")
        print(f"   无头模式: {DRISSIONPAGE_HEADLESS}")
        if DRISSIONPAGE_CHROME_PATH:
            print(f"   Chrome 路径: {DRISSIONPAGE_CHROME_PATH}")
        print()
    elif USE_CLOUDSCRAPER:
        print("🛡️ 已启用 Cloudflare 绕过模式 (cloudscraper)\n")
    else:
        print("❌ 未启用 Cloudflare 绕过，建议安装: pip install DrissionPage\n")
    
    if CF_CLEARANCE:
        print(f"🔑 已配置 CF_CLEARANCE (长度: {len(CF_CLEARANCE)})\n")
    else:
        print("💡 提示: 如遇到 Cloudflare 验证，可设置 CF_CLEARANCE 环境变量绕过\n")

    summary = []
    for idx, ck in enumerate(cookies, start=1):
        print(f"🙍🏻‍♂️ 第{idx}个账号开始")
        try:
            clean_cookie = normalize_cookie(ck)
            if not clean_cookie:
                raise Exception("COOKIE 清洗后为空，请检查环境变量格式")

            last_error = None
            success_log = None
            for site_base in site_bases:
                try:
                    print(f"➡️ 尝试站点: {site_base}")
                    success_log = run_for_cookie(clean_cookie, site_base)
                    break
                except Exception as site_err:
                    last_error = site_err
                    print(f"⚠️ 站点失败: {site_base} -> {site_err}")

                    # HTTPS 握手异常时，自动降级 HTTP 再试一次
                    err_text = str(site_err)
                    if site_base.startswith("https://") and ("SSLError" in err_text or "EOF occurred" in err_text):
                        http_site = "http://" + site_base[len("https://"):]
                        try:
                            print(f"↪️ HTTPS异常，尝试HTTP: {http_site}")
                            success_log = run_for_cookie(clean_cookie, http_site)
                            break
                        except Exception as http_err:
                            last_error = http_err
                            print(f"⚠️ HTTP也失败: {http_site} -> {http_err}")

            if not success_log:
                raise Exception(f"所有站点均失败，最后错误: {last_error}")

            print(success_log)
            summary.append(f"账号{idx}: \n{success_log}")
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
