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
from urllib.parse import urlparse
from datetime import datetime, timedelta

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
SOUTHPLUS_USER_AGENT = os.getenv(
    "SOUTHPLUS_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
).strip()
SOUTHPLUS_CF_WAIT = int(os.getenv("SOUTHPLUS_CF_WAIT", "60"))

# 随机延迟配置
max_random_delay = int(os.getenv("MAX_RANDOM_DELAY", "3600"))
random_signin = os.getenv("RANDOM_SIGNIN", "true").lower() == "true"

# 站点配置
DEFAULT_SITE = "https://www.south-plus.net"

# 账号密码配置
SOUTHPLUS_USERNAME = os.getenv("SOUTHPLUS_USERNAME", "").strip()
SOUTHPLUS_PASSWORD = os.getenv("SOUTHPLUS_PASSWORD", "").strip()


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
        
        co.set_user_agent(SOUTHPLUS_USER_AGENT)
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--disable-gpu')
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--window-size=1920,1080')
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
    cookie_str = os.environ.get("SOUTHPLUS_COOKIE", "").strip() or os.environ.get("COOKIE", "").strip()
    
    # 如果没有 Cookie 但有账号密码，返回 None 表示使用账号密码登录
    if not cookie_str:
        if SOUTHPLUS_USERNAME and SOUTHPLUS_PASSWORD:
            print("✅ 检测到账号密码配置，将使用账号密码登录")
            return None, "login"
        print("❌ 未设置 COOKIE 环境变量，也未设置账号密码")
        Push("SouthPlus签到", "❌ 未设置 COOKIE 环境变量，也未设置账号密码")
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


def is_cloudflare_challenge(browser) -> bool:
    """只识别真正的 Cloudflare 验证页，避免把正常页脚脚本误判为验证中。"""
    try:
        result = browser.run_js('''
        var text = (document.body && document.body.innerText || '');
        var title = document.title || '';
        var html = document.documentElement.innerHTML || '';
        return /Just a moment/i.test(title)
            || /Performing security verification/i.test(text)
            || /Checking if the site connection is secure/i.test(text)
            || /cf-turnstile-response/i.test(html)
            || /cf-challenge/i.test(html);
        ''')
        return bool(result)
    except Exception:
        html = (browser.html or "").lower()
        return "just a moment" in html or "cf-turnstile-response" in html or "cf-challenge" in html


def wait_for_cloudflare(browser, max_wait: int = None):
    """等待 Cloudflare 正常放行；不内置绕过安全验证逻辑。"""
    max_wait = SOUTHPLUS_CF_WAIT if max_wait is None else max_wait
    waited = 0
    while waited < max_wait:
        if not is_cloudflare_challenge(browser):
            return True
        print(f"[DrissionPage] 等待 Cloudflare 验证... ({waited}s)")
        time.sleep(5)
        waited += 5

    print("[DrissionPage] ⚠️ Cloudflare 验证超时，未进入目标页面")
    return False


def page_text(browser) -> str:
    try:
        return browser.run_js('return document.body ? document.body.innerText : "";') or ""
    except Exception:
        return browser.html or ""


def is_not_logged_in(browser) -> bool:
    text = page_text(browser)
    html = browser.html or ""
    return any(x in text or x in html for x in [
        "您还没有登录",
        "您还没有登录或注册",
        "还不是论坛会员",
        "请先登录论坛",
    ])


def is_logged_in(browser) -> bool:
    text = page_text(browser)
    html = browser.html or ""
    if is_not_logged_in(browser):
        return False
    return any(x in text or x in html for x in [
        "退出",
        "用户中心",
        "个人首页",
        "我的主题",
        "积分",
        "社区论坛任务",
    ])


def save_debug_html(browser, name: str):
    if os.getenv("SOUTHPLUS_DEBUG", "false").lower() != "true":
        return
    try:
        path = os.path.join(os.getcwd(), name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(browser.html or "")
        print(f"[DrissionPage] 调试页面已保存: {path}")
    except Exception as e:
        print(f"[DrissionPage] 保存调试页面失败: {e}")


def add_cookie(browser, cookie, site_base: str):
    """兼容字符串 Cookie、Selenium dict 和 DrissionPage dict。"""
    domain = urlparse(site_base).hostname or "south-plus.net"
    root_domain = domain[4:] if domain.startswith("www.") else domain
    base_url = site_base.rstrip("/") + "/"

    def set_one(item, mirror_root=False):
        item = dict(item)
        item.setdefault("path", "/")
        item.setdefault("url", base_url)
        browser.set.cookies(item)
        if mirror_root and root_domain != domain:
            alt = dict(item)
            alt["domain"] = root_domain
            alt["url"] = f"https://{root_domain}/"
            try:
                browser.set.cookies(alt)
            except Exception:
                pass

    if isinstance(cookie, str):
        names = []
        for item in cookie.split(";"):
            item = item.strip()
            if "=" not in item:
                continue
            name, value = item.split("=", 1)
            name = name.strip()
            value = value.strip()
            if name and value:
                names.append(name)
                mirror_root = name == "cf_clearance"
                set_one({"name": name, "value": value, "domain": domain, "path": "/"}, mirror_root=mirror_root)
        print(f"[DrissionPage] 已注入 Cookie: {', '.join(names) if names else '空'}")
        return

    if not isinstance(cookie, dict):
        return

    item = dict(cookie)
    if "domain" not in item:
        item["domain"] = domain
    if "path" not in item:
        item["path"] = "/"
    set_one(item, mirror_root=item.get("name") == "cf_clearance")


def click_first(browser, selectors, label: str, timeout=2) -> bool:
    for selector in selectors:
        try:
            ele = browser.ele(selector, timeout=timeout)
            if ele:
                ele.click()
                print(f"[DrissionPage] ✅ {label}: {selector}")
                time.sleep(1)
                return True
        except Exception:
            continue
    print(f"[DrissionPage] {label}: 未找到可点击入口")
    return False


def task_ajax(browser, action: str, cid: str, label: str) -> tuple[bool, str]:
    """通过 SouthPlus 任务插件 Ajax 接口执行任务操作。"""
    try:
        result = browser.run_js(f'''
        var action = {json.dumps(action)};
        var cid = {json.dumps(str(cid))};
        var verify = (typeof verifyhash !== 'undefined' && verifyhash) ? verifyhash : '';
        var url = 'plugin.php?H_name=tasks&action=ajax&actions=' + encodeURIComponent(action)
            + '&cid=' + encodeURIComponent(cid)
            + '&nowtime=' + Date.now();
        if (verify) url += '&verify=' + encodeURIComponent(verify);

        var xhr = new XMLHttpRequest();
        xhr.open('GET', url, false);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.send(null);
        return {{
            status: xhr.status,
            text: xhr.responseText || '',
            url: url
        }};
        ''')
    except Exception as e:
        msg = f"Ajax 调用异常: {e}"
        print(f"[DrissionPage] ❌ {label}: {msg}")
        return False, msg

    if not isinstance(result, dict):
        msg = f"Ajax 返回异常: {result}"
        print(f"[DrissionPage] ❌ {label}: {msg}")
        return False, msg

    status = result.get("status")
    text = (result.get("text") or "").strip()
    text_short = re.sub(r"\s+", " ", text)[:160]
    ok_markers = [
        "success",
        "任务领取完成",
        "领取完成",
        "完成了",
        "已经申请",
        "已经领取",
        "已完成",
    ]
    neutral_markers = [
        "您已经申请过",
        "没有可领取",
        "任务不存在",
    ]
    not_login_markers = [
        "您还没有登录",
        "您还没有登录或注册",
        "请先登录",
    ]

    if any(x in text for x in not_login_markers):
        print(f"[DrissionPage] ❌ {label}: 未登录或 Cookie 失效")
        return False, text_short

    if status == 200 and any(x in text for x in ok_markers):
        print(f"[DrissionPage] ✅ {label}: {text_short or 'success'}")
        return True, text_short or "success"

    if status == 200 and any(x in text for x in neutral_markers):
        print(f"[DrissionPage] ℹ️ {label}: {text_short}")
        return True, text_short

    print(f"[DrissionPage] ⚠️ {label}: HTTP {status}, {text_short or '空响应'}")
    return False, text_short or f"HTTP {status}"


def task_click_fallback(browser, selectors, label: str) -> bool:
    """Ajax 失败时使用页面按钮兜底。"""
    ok = click_first(browser, selectors, label, timeout=2)
    if ok:
        time.sleep(1.5)
        wait_for_cloudflare(browser, max_wait=15)
    return ok


def solve_login_captcha(browser) -> bool:
    """识别并填写 SouthPlus 登录页 gdcode 验证码。"""
    try:
        has_input = browser.run_js('return !!document.querySelector("input[name=gdcode]");')
        if not has_input:
            return True

        try:
            import ddddocr
        except ImportError:
            print("[DrissionPage] ❌ 登录页需要验证码，请安装 ddddocr")
            return False

        ocr_engines = [ddddocr.DdddOcr(show_ad=False)]
        try:
            ocr_engines.append(ddddocr.DdddOcr(beta=True, show_ad=False))
        except Exception:
            pass

        for attempt in range(3):
            img_b64 = browser.run_js(f'''
            var input = document.querySelector('input[name="gdcode"]');
            var img = document.querySelector('#ckcode') || document.querySelector('img[src*="ck.php"]');
            if (!input || !img) return null;
            try {{
                img.style.display = 'inline';
                img.style.visibility = 'visible';
                img.src = 'ck.php?' + Date.now() + '{attempt}';
            }} catch(e) {{}}
            return 'loading';
            ''')
            if not img_b64:
                return True

            time.sleep(1.2)
            img_b64 = browser.run_js('''
            var img = document.querySelector('#ckcode') || document.querySelector('img[src*="ck.php"]');
            if (!img || !img.complete || !img.naturalWidth) return null;
            var c = document.createElement('canvas');
            c.width = img.naturalWidth;
            c.height = img.naturalHeight;
            var ctx = c.getContext('2d');
            ctx.drawImage(img, 0, 0);
            return c.toDataURL('image/png').split(',')[1];
            ''')
            if not img_b64:
                continue

            import base64
            img_bytes = base64.b64decode(img_b64)
            variants = build_captcha_variants(img_bytes)
            candidates = []
            for variant_name, variant_bytes in variants:
                if os.getenv("SOUTHPLUS_DEBUG", "false").lower() == "true":
                    try:
                        with open(f"south_captcha_{attempt}_{variant_name}.png", "wb") as f:
                            f.write(variant_bytes)
                    except Exception:
                        pass
                for engine in ocr_engines:
                    try:
                        text = engine.classification(variant_bytes)
                    except Exception:
                        continue
                    code = re.sub(r'[^0-9A-Za-z]', '', text or '').strip()
                    if 4 <= len(code) <= 6:
                        candidates.append(code)

            candidates = sorted(set(candidates), key=lambda x: (abs(len(x) - 5), -len(x), x))
            print(f"[DrissionPage] 验证码候选: {', '.join(candidates) if candidates else '空'}")
            if not candidates:
                continue
            code = candidates[0]

            filled = browser.run_js(f'''
            var input = document.querySelector('input[name="gdcode"]');
            if (!input) return false;
            input.focus();
            input.value = {json.dumps(code)};
            input.dispatchEvent(new Event('input', {{bubbles: true}}));
            input.dispatchEvent(new Event('change', {{bubbles: true}}));
            return true;
            ''')
            if filled:
                return True
        return False
    except Exception as e:
        print(f"[DrissionPage] ❌ 验证码处理失败: {e}")
        return False


def build_captcha_variants(img_bytes: bytes):
    """生成适合 SouthPlus 浅色文字验证码的 OCR 预处理图。"""
    variants = [("raw", img_bytes)]
    try:
        from PIL import Image, ImageEnhance, ImageOps
        import io

        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        for scale in (2, 3):
            gray = ImageOps.grayscale(img).resize(
                (img.width * scale, img.height * scale),
                Image.Resampling.LANCZOS,
            )
            gray = ImageEnhance.Contrast(gray).enhance(2.8)
            gray = ImageEnhance.Sharpness(gray).enhance(2.0)
            buf = io.BytesIO()
            gray.save(buf, format="PNG")
            variants.append((f"gray{scale}", buf.getvalue()))

        for delta in (10, 16, 22):
            out = Image.new("L", img.size, 255)
            src = img.load()
            dst = out.load()
            for y in range(img.height):
                for x in range(img.width):
                    r, g, b = src[x, y]
                    mx = max(r, g, b)
                    mn = min(r, g, b)
                    if mx > 125 and (mx - mn) < delta:
                        dst[x, y] = 0
            out = out.resize((img.width * 3, img.height * 3), Image.Resampling.NEAREST)
            buf = io.BytesIO()
            out.save(buf, format="PNG")
            variants.append((f"mask{delta}", buf.getvalue()))
    except Exception as e:
        print(f"[DrissionPage] 验证码预处理失败: {e}")
    return variants


def login_with_password(browser, site_base: str, username: str, password: str) -> bool:
    """使用账号密码登录"""
    try:
        login_url = f"{site_base}/login.php"
        for attempt in range(1, 4):
            print(f"[DrissionPage] 访问登录页面: {login_url} (尝试 {attempt}/3)")
            browser.get(login_url)
            time.sleep(2)

            if not wait_for_cloudflare(browser):
                return False
            time.sleep(1)

            form_result = browser.run_js(f'''
            var username = {json.dumps(username)};
            var password = {json.dumps(password)};
            function visible(el) {{
                if (!el) return false;
                var r = el.getBoundingClientRect();
                var s = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
            }}
            function pick(list) {{
                for (var i = 0; i < list.length; i++) {{
                    var nodes = Array.from(document.querySelectorAll(list[i]));
                    var found = nodes.find(visible) || nodes[0];
                    if (found) return found;
                }}
                return null;
            }}
            function setValue(el, value) {{
                el.focus();
                var setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value');
                if (setter && setter.set) setter.set.call(el, value);
                else el.value = value;
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
            var userEl = pick(['input[name="pwuser"]', '#pwuser', 'input[type="text"]']);
            var passEl = pick(['input[name="pwpwd"]', 'input[type="password"]']);
            var form = (passEl && passEl.form) || (userEl && userEl.form) || document.querySelector('form[name="login"], form[name="login_FORM"], form[action*="login.php"]');
            if (!userEl || !passEl || !form) {{
                return {{
                    ok: false,
                    title: document.title,
                    text: (document.body && document.body.innerText || '').slice(0, 300),
                    inputs: Array.from(document.querySelectorAll('input')).slice(0, 20).map(function(el) {{
                        return {{type: el.type || '', name: el.name || '', id: el.id || '', value: el.value || '', visible: visible(el)}};
                    }})
                }};
            }}
            setValue(userEl, username);
            setValue(passEl, password);
            return {{ok: true}};
            ''')

            if not isinstance(form_result, dict) or not form_result.get("ok"):
                print(f"[DrissionPage] ❌ 未找到登录表单: {json.dumps(form_result, ensure_ascii=False)[:800]}")
                save_debug_html(browser, "south_login_debug.html")
                return False

            if not solve_login_captcha(browser):
                print("[DrissionPage] ❌ 验证码识别失败")
                continue

            print("[DrissionPage] 点击登录按钮")
            submitted = browser.run_js('''
            var btn = Array.from(document.querySelectorAll('input[type="submit"], button[type="submit"], .btn'))
                .find(function(el) {
                    var r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                });
            if (btn) { btn.click(); return 'clicked'; }
            var form = document.querySelector('form[name="login"], form[name="login_FORM"], form[action*="login.php"]');
            if (form) { form.submit(); return 'submitted'; }
            return 'no_submit';
            ''')
            print(f"[DrissionPage] 登录提交结果: {submitted}")
            time.sleep(3)

            wait_for_cloudflare(browser)
            html = browser.html
            text = page_text(browser)
            if "认证码不正确" in text or "认证码不正确" in html or "验证码" in text and "不正确" in text:
                print("[DrissionPage] 验证码不正确，重试...")
                save_debug_html(browser, f"south_login_captcha_retry_{attempt}.html")
                continue
            if is_not_logged_in(browser):
                print("[DrissionPage] ❌ 登录失败：仍显示未登录状态")
                save_debug_html(browser, "south_login_failed.html")
                return False

            if "密码错误" in html or "用户名不存在" in html or "登录失败" in html or "非法请求" in html:
                print("[DrissionPage] ❌ 登录失败：用户名或密码错误")
                return False

            print("[DrissionPage] ✅ 登录成功")
            return True

        print("[DrissionPage] ❌ 登录失败：验证码多次识别失败。建议改用 SOUTHPLUS_COOKIE / COOKIE 模式运行。")
        return False
    
    except Exception as e:
        print(f"[DrissionPage] ❌ 登录过程出错: {e}")
        return False


def run_with_login(site_base: str) -> str:
    """使用账号密码登录并执行任务"""
    browser = None
    try:
        browser = init_browser()
        
        # 先访问首页
        print(f"[DrissionPage] 访问首页: {site_base}")
        browser.get(site_base)
        time.sleep(2)
        
        # 等待 Cloudflare
        if not wait_for_cloudflare(browser):
            return "❌ Cloudflare 验证超时，未进入首页"
        
        # 登录
        if not login_with_password(browser, site_base, SOUTHPLUS_USERNAME, SOUTHPLUS_PASSWORD):
            return "❌ 账号密码登录失败"
        
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


def do_task(browser, site_base: str) -> str:
    """执行任务流程"""
    log_lines = []
    
    # 任务页面 URL
    task_url = f"{site_base}/plugin.php?H_name-tasks.html"
    
    print(f"[DrissionPage] 访问任务页面: {task_url}")
    browser.get(task_url)
    time.sleep(3)
    
    # 等待 Cloudflare
    if not wait_for_cloudflare(browser):
        return "❌ Cloudflare 验证超时，未进入任务页面"
    time.sleep(2)
    
    # 检查登录状态
    if is_not_logged_in(browser):
        save_debug_html(browser, "south_not_login.html")
        return "❌ Cookie 无效或已过期：站点返回未登录"
    
    # ===== 步骤1: 申请任务 =====
    log_lines.append("📋 步骤1: 申请任务")
    
    # 查找可申请的任务 (p_14=周常, p_15=日常)
    apply_count = 0
    
    ok, _ = task_ajax(browser, "job", "15", "日常任务申请")
    if ok or task_click_fallback(browser, ['#p_15 a img', '#p_15 a', 'xpath://*[@id="p_15"]//a'], "日常任务申请"):
        log_lines.append("   ✅ 日常任务已申请/已点击")
        apply_count += 1
    else:
        log_lines.append("   日常任务暂不可申请或已申请")
    
    ok, _ = task_ajax(browser, "job", "14", "周常任务申请")
    if ok or task_click_fallback(browser, ['#p_14 a img', '#p_14 a', 'xpath://*[@id="p_14"]//a'], "周常任务申请"):
        log_lines.append("   ✅ 周常任务已申请/已点击")
        apply_count += 1
    else:
        log_lines.append("   周常任务暂不可申请或已申请")
    
    # ===== 步骤2: 完成任务 =====
    log_lines.append("📋 步骤2: 完成任务")
    
    # 切换到进行中的任务
    in_progress_url = f"{site_base}/plugin.php?H_name-tasks-actions-newtasks.html"
    browser.get(in_progress_url)
    time.sleep(2)
    wait_for_cloudflare(browser)
    
    ok, _ = task_ajax(browser, "job2", "15", "日常任务完成")
    if ok or task_click_fallback(browser, ['#both_15 a img', '#both_15 a', 'xpath://*[@id="both_15"]//a'], "日常任务完成"):
        log_lines.append("   ✅ 日常任务已完成/已点击")
    else:
        log_lines.append("   日常任务暂不可完成")
    
    ok, _ = task_ajax(browser, "job2", "14", "周常任务完成")
    if ok or task_click_fallback(browser, ['#both_14 a img', '#both_14 a', 'xpath://*[@id="both_14"]//a'], "周常任务完成"):
        log_lines.append("   ✅ 周常任务已完成/已点击")
    else:
        log_lines.append("   周常任务暂不可完成")
    
    # ===== 步骤3: 领取奖励 =====
    log_lines.append("📋 步骤3: 领取奖励")
    
    # 访问已完成任务页面
    finished_url = f"{site_base}/plugin.php?H_name-tasks-actions-endtasks.html"
    browser.get(finished_url)
    time.sleep(2)
    wait_for_cloudflare(browser)
    
    if is_not_logged_in(browser):
        return "❌ Cookie 无效或已过期：领取页面返回未登录"

    if task_click_fallback(browser, ['#both_15 a img', '#both_15 a', 'xpath://*[@id="both_15"]//a'], "日常奖励领取"):
        log_lines.append("   ✅ 日常奖励已领取/已点击")
    else:
        log_lines.append("   日常奖励无单独领取按钮，通常已在完成任务时结算")
    
    if task_click_fallback(browser, ['#both_14 a img', '#both_14 a', 'xpath://*[@id="both_14"]//a'], "周常奖励领取"):
        log_lines.append("   ✅ 周常奖励已领取/已点击")
    else:
        log_lines.append("   周常奖励无单独领取按钮，通常已在完成任务时结算")
    
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
        if not wait_for_cloudflare(browser):
            return "❌ Cloudflare 验证超时，未进入首页"
        
        # 添加 cookies（Selenium 风格）
        print(f"[DrissionPage] 设置 {len(cookie_list)} 个 Cookie...")
        for cookie in cookie_list:
            try:
                add_cookie(browser, cookie, site_base)
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
        if not wait_for_cloudflare(browser):
            return "❌ Cloudflare 验证超时，未进入首页"
        
        # 设置 cookies
        print("[DrissionPage] 设置 Cookie...")
        try:
            add_cookie(browser, cookie_str, site_base)
        except Exception as e:
            print(f"[DrissionPage] 设置 Cookie 失败: {e}")
        
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
    
    print(f"\n✅ 站点: {site_base}")
    print(f"✅ 无头模式: {DRISSIONPAGE_HEADLESS}")
    
    summary = []
    
    # 使用账号密码登录模式
    if cookie_type == "login":
        print(f"✅ 使用账号密码登录模式")
        print(f"🙍🏻‍♂️ 开始登录账号: {SOUTHPLUS_USERNAME}")
        try:
            result = run_with_login(site_base)
            print(result)
            summary.append(f"账号 {SOUTHPLUS_USERNAME}:\n{result}")
        except Exception as e:
            err_msg = f"账号 {SOUTHPLUS_USERNAME} 失败: {e}"
            summary.append(err_msg)
            print(f"❌ {err_msg}")
    else:
        # 使用 Cookie 模式
        print(f"✅ 检测到 {len(cookie_list)} 个 SouthPlus 账号\n")
        
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
    
    if random_signin and max_random_delay > 0:
        delay_seconds = random.randint(0, max_random_delay)
        if delay_seconds > 0:
            signin_time = datetime.now() + timedelta(seconds=delay_seconds)
            print(f"随机模式: 延迟 {format_time_remaining(delay_seconds)} 后签到")
            print(f"预计签到时间: {signin_time.strftime('%H:%M:%S')}")
            wait_with_countdown(delay_seconds)
    
    print("----------SouthPlus 开始签到----------")
    result = main()
    print("----------SouthPlus 签到完毕----------")
    print(f"==== SouthPlus 签到完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    sys.exit(1 if result and "❌" in result else 0)
