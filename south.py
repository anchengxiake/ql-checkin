"""
cron: 0 9 * * *
new Env('SouthPlus签到')
"""

import os
import re
import sys
import time
import random
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# 尝试导入 pydoll 用于绕过 Cloudflare（优先级最高）
USE_PYDOLL = False
try:
    from pydoll.browser import Chrome
    from pydoll.browser.options import ChromiumOptions
    USE_PYDOLL = True
    print("✅ 已加载 pydoll，可自动绕过 Cloudflare 验证")
except ImportError:
    print("⚠️ 未安装 pydoll-python，尝试使用 cloudscraper")
    print("   如需自动绕过 Cloudflare，请执行: pip install pydoll-python")

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
    if not USE_PYDOLL:
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


# ============== Pydoll CF 绕过功能 ==============
import asyncio
import platform

# Pydoll 配置
PYDOLL_HEADLESS = os.getenv("PYDOLL_HEADLESS", "true").lower() == "true"
PYDOLL_CHROME_PATH = os.getenv("PYDOLL_CHROME_PATH", "").strip()  # 可选：指定 Chrome 路径


def find_chrome_path() -> str:
    """自动检测 Chrome/Chromium 浏览器路径"""
    system = platform.system()
    
    # 如果环境变量已指定，直接使用
    if PYDOLL_CHROME_PATH:
        return PYDOLL_CHROME_PATH
    
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
            print(f"[Pydoll] 自动检测到浏览器: {path}")
            return path
    
    # 未找到浏览器
    return None


def get_pydoll_options(headless: bool = True, proxy: str = None) -> "ChromiumOptions":
    """获取 pydoll 浏览器配置"""
    options = ChromiumOptions()
    options.headless = headless

    # 服务器/Docker 环境必需参数
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')

    # 自动检测或使用指定的 Chrome 路径
    chrome_path = find_chrome_path()
    if chrome_path:
        options.binary_location = chrome_path
    else:
        # 未找到浏览器，提供友好提示
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
  PYDOLL_CHROME_PATH=/usr/bin/chromium

当前系统: {system}
"""
        raise Exception(error_msg)

    # 增加启动超时
    options.start_timeout = 30

    # 反检测配置 - 模拟真实用户浏览器
    fake_engagement_time = int(time.time()) - (7 * 24 * 60 * 60)

    options.browser_preferences = {
        'profile': {
            'last_engagement_time': fake_engagement_time,
            'exit_type': 'Normal',
            'exited_cleanly': True,
            'default_content_setting_values': {
                'notifications': 2,
                'geolocation': 2,
            },
        },
        'session': {
            'restore_on_startup': 1,
        },
    }

    # WebRTC 泄露保护
    options.webrtc_leak_protection = True

    # 代理配置
    if proxy:
        options.add_argument(f'--proxy-server={proxy}')

    return options


async def pydoll_bypass_cf_and_get_cookies(url: str, existing_cookie: str = None) -> dict:
    """
    使用 pydoll 绕过 Cloudflare 并获取 cookies
    
    Args:
        url: 目标 URL
        existing_cookie: 现有的 cookie 字符串（可选，将通过 URL 参数传递）
    
    Returns:
        包含 cookies 和页面 HTML 的字典
    """
    if not USE_PYDOLL:
        raise Exception("pydoll-python 未安装，无法使用 CF 绕过功能")

    options = get_pydoll_options(headless=PYDOLL_HEADLESS, proxy=proxy_url or None)

    async with Chrome(options=options) as browser:
        tab = await browser.start()

        print(f"[Pydoll] 正在访问: {url}")

        # 自动检测并处理 Cloudflare
        try:
            async with tab.expect_and_bypass_cloudflare_captcha():
                await tab.go_to(url)
            print("[Pydoll] Cloudflare 验证已通过")
        except Exception as e:
            print(f"[Pydoll] Cloudflare 处理: {e}")
            # 即使超时也继续尝试访问
            try:
                await tab.go_to(url)
            except Exception:
                pass

        # 等待页面加载完成
        await asyncio.sleep(5)

        # 获取所有 cookies
        cookies = await tab.get_cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        cookie_str = "; ".join([f"{name}={value}" for name, value in cookie_dict.items()])

        # 获取页面 HTML
        html = await tab.page_source

        # 检查是否仍然在 Cloudflare 验证页面
        html_lower = html.lower()
        if "cloudflare" in html_lower or "just a moment" in html_lower or "cf-challenge" in html_lower:
            print("[Pydoll] ⚠️ 页面仍显示 Cloudflare 验证，可能需要更长时间等待")
            # 再等待一段时间
            await asyncio.sleep(10)
            html = await tab.page_source
            cookies = await tab.get_cookies()
            cookie_dict = {c['name']: c['value'] for c in cookies}
            cookie_str = "; ".join([f"{name}={value}" for name, value in cookie_dict.items()])

        # 如果有用户 cookie，合并到返回的 cookie 中
        if existing_cookie:
            for item in existing_cookie.split(";"):
                item = item.strip()
                if "=" in item:
                    name, value = item.split("=", 1)
                    name = name.strip()
                    value = value.strip()
                    if name and value and name not in cookie_dict:
                        cookie_str += f"; {name}={value}"

        return {
            'cookies': cookie_str,
            'cookie_dict': cookie_dict,
            'html': html,
            'url': await tab.current_url,
        }


def run_pydoll_bypass(url: str, existing_cookie: str = None) -> dict:
    """同步包装 pydoll CF 绕过函数"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # 如果在异步环境中，创建新的线程运行
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                pydoll_bypass_cf_and_get_cookies(url, existing_cookie)
            )
            return future.result()
    else:
        return loop.run_until_complete(
            pydoll_bypass_cf_and_get_cookies(url, existing_cookie)
        )


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

    # 去重（保序）
    dedup = []
    for b in bases:
        if b not in dedup:
            dedup.append(b)
    return dedup


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


# 全局变量：存储 pydoll 获取的 cookies
PYDOLL_COOKIES = {}


def fetch_task_page(cookie: str, site_base: str, page_suffix: str, use_pydoll: bool = False) -> str:
    """抓取任务页面（自动按响应头编码解析）。
    
    Args:
        cookie: 用户 cookie
        site_base: 站点基础 URL
        page_suffix: 页面后缀
        use_pydoll: 是否强制使用 pydoll 绕过 CF
    """
    global PYDOLL_COOKIES, CF_CLEARANCE
    url = f"{site_base}/plugin.php{page_suffix}"
    
    # 如果启用 pydoll 且可用，直接使用 pydoll
    if use_pydoll and USE_PYDOLL:
        print(f"[Pydoll] 使用 pydoll 绕过 Cloudflare 访问: {url}")
        try:
            result = run_pydoll_bypass(url, cookie)
            html = result['html']
            # 存储获取的 cookies
            PYDOLL_COOKIES = result.get('cookie_dict', {})
            new_cookies = result['cookies']
            
            # 更新全局 cf_clearance（如果获取到了）
            cf_match = re.search(r'cf_clearance=([^;]+)', new_cookies)
            if cf_match:
                CF_CLEARANCE = cf_match.group(1)
                print(f"[Pydoll] 已获取新的 cf_clearance: {CF_CLEARANCE[:20]}...")
            
            # 检查是否成功获取任务页面
            valid_markers = [
                "社区论坛任务",
                "按这申请此任务",
                "领取此奖励",
                "startjob(",
                "H_name-tasks",
            ]
            if any(m in html for m in valid_markers):
                print("[Pydoll] ✅ 成功获取任务页面")
                return html
            
            # 如果仍然不是任务页面，检查是否需要登录
            if "您还没有登录或注册" in html:
                raise Exception("Cookie 无效或已过期：站点返回未登录")
            
            # 打印页面信息用于调试
            m_title = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
            title = m_title.group(1).strip() if m_title else "未知页面"
            print(f"[Pydoll] 页面标题: {title}")
            
            # 如果页面仍然显示 Cloudflare，说明绕过失败
            html_lower = html.lower()
            if "cloudflare" in html_lower or "just a moment" in html_lower:
                raise Exception("Pydoll 绕过 Cloudflare 失败，页面仍显示验证")
            
            # 其他情况，返回 HTML 让后续处理
            return html
            
        except Exception as e:
            print(f"[Pydoll] 绕过失败: {e}")
            raise Exception(f"Pydoll CF 绕过失败: {e}")
    
    # 常规请求方式
    # 优先使用 pydoll 获取的 cookies
    merged_cookie = cookie
    if PYDOLL_COOKIES:
        # 合并 pydoll cookies 和用户 cookie
        cookie_dict = {}
        for item in cookie.split(";"):
            item = item.strip()
            if "=" in item:
                name, value = item.split("=", 1)
                cookie_dict[name.strip()] = value.strip()
        # 添加 pydoll cookies（不覆盖用户 cookie）
        for name, value in PYDOLL_COOKIES.items():
            if name not in cookie_dict:
                cookie_dict[name] = value
        merged_cookie = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
    
    cookie_with_cf = add_cf_clearance_to_cookie(merged_cookie)
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
        # 如果还没使用 pydoll，尝试用 pydoll 绕过
        if not use_pydoll and USE_PYDOLL:
            print("⚠️ 触发 Cloudflare 验证，尝试使用 pydoll 绕过...")
            return fetch_task_page(cookie, site_base, page_suffix, use_pydoll=True)
        
        error_msg = """触发 Cloudflare 验证，无法直接请求。
解决方案：
1. 安装 pydoll-python（推荐）：
   pip install pydoll-python
   
2. 设置环境变量 CF_CLEARANCE：
   - 使用浏览器访问站点，通过 F12 -> Network 找到包含 cf_clearance 的请求
   - 复制 cf_clearance 的值
   - 设置环境变量: export CF_CLEARANCE="你的值"
   
3. 使用与浏览器同出口 IP 的代理：
   - 设置环境变量: export SOUTHPLUS_PROXY="http://代理地址:端口"
   
4. 在本地网络运行脚本（非服务器机房IP）"""
        raise Exception(error_msg)

    if "您还没有登录或注册" in html:
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
    return {
        "H_name": "tasks",
        "action": "ajax",
        "actions": action,
        "cid": cid,
        "nowtime": str(int(time.time() * 1000)),
        "verify": verify,
    }


def tasks(url: str, params: dict, headers: dict, action_desc: str) -> bool:
    # 添加 cf_clearance 到 cookie
    if "cookie" in headers:
        headers["cookie"] = add_cf_clearance_to_cookie(headers["cookie"])
    response = make_request("GET", url, params=params, headers=headers, timeout=request_timeout, proxies=proxies)
    response.encoding = "utf-8"
    data = response.text

    message = parse_message_from_response(data)
    print(action_desc + message)

    fail_keywords = ["未登录", "没有登录", "错误", "失败", "非法", "权限", "验证", "Cloudflare"]
    if any(k in message for k in fail_keywords):
        raise Exception(message)

    return "还没超过" not in message


def run_for_cookie(cookie: str, site_base: str) -> str:
    """单账号执行签到任务并返回日志"""
    url = f"{site_base}/plugin.php"

    headers_apply = {**base_headers, "cookie": cookie, "referer": url + "?H_name-tasks-actions-newtasks.html.html"}
    headers_finish = {
        **base_headers,
        "cookie": cookie,
        "authority": site_base.replace("https://", "").replace("http://", ""),
        "method": "GET",
        "path": "/plugin.php?H_name-tasks-actions-newtasks.html.html",
        "scheme": "https" if site_base.startswith("https://") else "http",
        "Referer": url + "?H_name-tasks.html.html",
    }

    log_lines = [f"站点: {site_base}"]

    # 1) 申请可做任务（job）
    new_tasks_html = fetch_task_page(cookie, site_base, "?H_name-tasks.html")
    apply_jobs = extract_jobs_from_html(new_tasks_html)
    if apply_jobs:
        log_lines.append(f"检测到可申请任务: {len(apply_jobs)}")
    else:
        log_lines.append("未检测到可申请任务")

    for cid, verify in apply_jobs:
        params = build_job_params("job", cid, verify)
        tasks(url, params, headers_apply, f"申请任务(cid={cid}): ")
        time.sleep(0.15)

    # 2) 领取已完成任务（job2）
    current_tasks_html = fetch_task_page(cookie, site_base, "?H_name-tasks-actions-newtasks.html.html")
    reward_jobs = extract_jobs_from_html(current_tasks_html)
    if reward_jobs:
        log_lines.append(f"检测到可领取任务: {len(reward_jobs)}")
    else:
        log_lines.append("未检测到可领取任务")

    for cid, verify in reward_jobs:
        params = build_job_params("job2", cid, verify)
        tasks(url, params, headers_finish, f"领取任务(cid={cid}): ")
        time.sleep(0.15)

    return "\n".join(log_lines)


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
    if USE_PYDOLL:
        print("🛡️ 已启用 Pydoll Cloudflare 自动绕过模式（推荐）\n")
        print(f"   无头模式: {PYDOLL_HEADLESS}")
        if PYDOLL_CHROME_PATH:
            print(f"   Chrome 路径: {PYDOLL_CHROME_PATH}")
        print()
    elif USE_CLOUDSCRAPER:
        print("🛡️ 已启用 Cloudflare 绕过模式 (cloudscraper)\n")
    else:
        print("❌ 未启用 Cloudflare 绕过，建议安装: pip install pydoll-python\n")
    
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
