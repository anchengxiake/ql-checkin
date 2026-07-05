#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
老王论坛自动签到脚本 v6.0
简洁稳定版 - DrissionPage + ddddocr

功能特性:
- 自动登录 + 滑块验证
- 多账号支持
- 青龙面板兼容
- 详细日志输出
- 通知推送支持

环境变量:
  LAOWANG_ACCOUNT=用户名:密码 或 用户1:密码1&用户2:密码2
  LAOWANG_DEBUG=true          # 调试模式
  MAX_RANDOM_DELAY=300        # 最大随机延迟秒数

cron: 0 9 * * *
new Env('老王论坛签到')
"""

import os
import re
import sys
import time
import random
import logging
from datetime import datetime
from slider_solver import SliderSolver

# Windows 控制台 UTF-8
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass

# ============ 配置 ============
BASE_URL = "https://laowang.vip"
LOGIN_URL = f"{BASE_URL}/member.php?mod=logging&action=login"
SIGN_URL = f"{BASE_URL}/plugin.php?id=k_misign:sign"
SIGN_API_URL = f"{BASE_URL}/plugin.php?id=k_misign:sign&operation=qiandao&format=button_inajax"
CUSTOM_HOST = os.getenv('LAOWANG_CUSTOM_HOST', '').strip()

# 日志
logging.basicConfig(
    level=logging.DEBUG if os.getenv('LAOWANG_DEBUG', '').lower() == 'true' else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# 通知模块
notify = None
try:
    from notify import send
    notify = send
except ImportError:
    pass


def push_notify(title, message):
    """推送通知"""
    if notify:
        try:
            notify(title, message)
        except Exception as e:
            logger.debug(f"通知推送失败: {e}")


def split_account_items(env_str):
    """分割多账号，避免把密码里的 & 当成账号分隔符。"""
    items = []
    for line in env_str.strip().splitlines():
        current = ''
        for chunk in line.split('&'):
            chunk = chunk.strip()
            if not chunk:
                continue
            head = chunk.split(':', 1)[0].strip()
            looks_like_new_account = ':' in chunk and bool(re.match(r'^[^=;&\s]{1,64}$', head))
            if current and looks_like_new_account:
                items.append(current)
                current = chunk
            else:
                current = chunk if not current else f"{current}&{chunk}"
        if current:
            items.append(current)
    return items


class LaowangSigner:
    """老王论坛签到器"""

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.display_name = username
        self.browser = None
        self.ocr = None

    def init_ocr(self):
        """初始化 OCR"""
        try:
            import ddddocr
            self.ocr = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)
            logger.info("✅ ddddocr 已加载")
            return True
        except ImportError:
            logger.warning("⚠️ ddddocr 未安装，使用 Canvas 比对")
            return False

    def init_browser(self):
        """初始化浏览器"""
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions

            co = ChromiumOptions()

            # 尝试查找浏览器路径
            browser_paths = [
                # Chrome（优先）
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                # Edge
                r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                # CloakBrowser（备选）
                r'C:\Program Files\cloakbrowser\chrome.exe',
            ]

            browser_found = False
            for path in browser_paths:
                if os.path.exists(path):
                    co.set_browser_path(path)
                    logger.info(f"🌐 使用浏览器: {path}")
                    browser_found = True
                    break

            if not browser_found:
                logger.warning("⚠️ 未找到浏览器路径，尝试默认配置")

            co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')
            co.set_argument('--disable-blink-features=AutomationControlled')
            co.set_argument('--no-sandbox')
            co.set_argument('--disable-gpu')
            co.set_argument('--window-size=1920,1080')
            if CUSTOM_HOST:
                co.set_argument(f'--host-resolver-rules=MAP laowang.vip {CUSTOM_HOST}')
                logger.info(f"🌐 自定义解析: laowang.vip -> {CUSTOM_HOST}")
            co.auto_port()

            # 无头模式（服务器环境）
            if os.getenv('DISPLAY') is None and sys.platform != 'win32':
                co.headless(True)

            self.browser = ChromiumPage(co)
            logger.info("✅ 浏览器已启动")
            return True
        except ImportError:
            logger.error("❌ 未安装 DrissionPage: pip install DrissionPage")
            return False
        except Exception as e:
            logger.error(f"❌ 浏览器启动失败: {e}")
            return False

    def drag_slider(self, distance):
        """拖动滑块：直接调用 tncode 原生处理函数生成完整轨迹"""
        try:
            total_time = random.randint(1200, 2200)
            target_points = random.randint(25, 40)
            y_variance = random.randint(5, 10)

            js_code = f'''
            var IMAGE_GAP = {distance};
            var SCREEN_DIST = IMAGE_GAP;
            var TOTAL_TIME = {total_time};
            var TARGET_POINTS = {target_points};
            var Y_VARIANCE = {y_variance};

            var overlay = document.getElementById('zh-cvt-overlay');
            if (overlay) overlay.remove();

            var t = window.tncode;
            var slider = document.querySelector('.slide_block');
            if (!t || !slider) return 'no_handler';
            if (typeof t._block_start_move !== 'function' ||
                typeof t._block_on_move !== 'function' ||
                typeof t._block_on_end !== 'function') return 'missing_tncode_methods';

            try {{ t._reset(); }} catch(e) {{}}

            var rect = slider.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return 'no_rect';
            var startX = Math.round(rect.left + rect.width / 2);
            var startY = Math.round(rect.top + rect.height / 2);

            function makeME(type, x, y, isUp) {{
                return new MouseEvent(type, {{
                    bubbles: true,
                    cancelable: true,
                    clientX: x,
                    clientY: y,
                    button: 0,
                    buttons: isUp ? 0 : 1
                }});
            }}

            function rnd(min, max) {{
                return min + Math.floor(Math.random() * (max - min + 1));
            }}

            var steps = TARGET_POINTS;
            var times = new Array(steps);
            var base = TOTAL_TIME / steps;
            for (var i = 0; i < steps; i++) {{
                var t_step = base + rnd(-15, 15);
                if (Math.random() < 0.05) t_step += rnd(20, 60);
                if (Math.random() < 0.03) t_step += rnd(40, 100);
                times[i] = Math.max(2, Math.round(t_step));
            }}

            var xs = new Array(steps);
            for (var i = 0; i < steps; i++) {{
                var frac = (i + 1) / steps;
                var eased;
                if (frac < 0.3) {{
                    eased = 0.5 * Math.pow(frac / 0.3, 2);
                }} else if (frac < 0.8) {{
                    eased = 0.5 + 0.5 * ((frac - 0.3) / 0.5);
                }} else {{
                    eased = 1 - 0.5 * Math.pow((1 - frac) / 0.2, 2);
                }}
                xs[i] = Math.round(eased * SCREEN_DIST);
            }}

            t._block_start_move(makeME('mousedown', startX, startY, false));

            var startMs = Date.now();
            var cumulative = 0;
            for (var i = 0; i < steps; i++) {{
                cumulative += times[i];
                var wait = startMs + cumulative - Date.now();
                if (wait > 0) {{
                    var endWait = Date.now() + wait;
                    while (Date.now() < endWait) {{}}
                }}
                var x = startX + xs[i];
                var y = startY + Math.round((Math.random() - 0.5) * Y_VARIANCE * 2);
                if (Math.random() < 0.08) y += Math.round((Math.random() - 0.5) * Y_VARIANCE * 4);
                t._block_on_move(makeME('mousemove', x, y, false));
            }}

            var wait = rnd(30, 60);
            var endWait = Date.now() + wait;
            while (Date.now() < endWait) {{}}
            var overshoot = rnd(1, 4);
            t._block_on_move(makeME('mousemove', startX + SCREEN_DIST + overshoot, startY, false));

            wait = rnd(35, 65);
            endWait = Date.now() + wait;
            while (Date.now() < endWait) {{}}
            t._block_on_move(makeME('mousemove', startX + SCREEN_DIST, startY, false));

            wait = rnd(40, 80);
            endWait = Date.now() + wait;
            while (Date.now() < endWait) {{}}
            t._block_on_end(makeME('mouseup', startX + SCREEN_DIST, startY, true));

            var trackLen = t._track_data ? t._track_data.length : 0;
            var totalT = trackLen > 0 ? t._track_data[trackLen - 1].t : 0;
            return 'ok: img_gap=' + IMAGE_GAP + ' scr_dist=' + SCREEN_DIST + ' track=' + trackLen +
                   ' time=' + totalT + 'ms offset=' + t._mark_offset;
            '''

            result = self.browser.run_js(js_code)
            logger.debug(f"tncode 拖动结果: {result}")
            return isinstance(result, str) and result.startswith('ok')

        except Exception as e:
            logger.debug(f"tncode 拖动失败: {e}")
            return False

    def check_slider_passed(self):
        """检查滑块验证是否通过"""
        try:
            result = self.browser.run_js('''
            var t = window.tncode;
            if (t && t._result === true) return true;
            var inp = document.getElementById('clicaptcha-submit-info');
            if (inp && inp.value && inp.value.indexOf('_ok') > -1) return true;
            return false;
            ''')
            return bool(result)
        except:
            return False

    def submit_verification(self):
        """滑块通过后提交验证表单。"""
        try:
            result = self.browser.run_js('''
            function visible(el) {
                if (!el) return false;
                var r = el.getBoundingClientRect();
                var s = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
            }

            var selectors = [
                '#submit-btn',
                'button[type="submit"]',
                'input[type="submit"]',
                'input[type="button"]',
                '.pn.pnc',
                '.pnc',
                'button'
            ];

            for (var si = 0; si < selectors.length; si++) {
                var nodes = Array.from(document.querySelectorAll(selectors[si]));
                for (var i = 0; i < nodes.length; i++) {
                    var el = nodes[i];
                    var label = ((el.innerText || el.value || el.textContent || '') + '').trim();
                    if (visible(el) && (el.id === 'submit-btn' || /提交|确定|签到|验证/.test(label))) {
                        el.click();
                        return 'clicked:' + (el.id || el.className || label || selectors[si]);
                    }
                }
            }

            var form = document.querySelector('form');
            if (form) {
                form.submit();
                return 'form_submit';
            }
            return 'no_submit';
            ''')
            logger.info(f"📤 提交验证结果: {result}")
            return bool(result) and result != 'no_submit'
        except Exception as e:
            logger.debug(f"提交验证失败: {e}")
            return False

    def _wait_for_tncode_result(self, timeout=6):
        """轮询等待 tncode 验证结果"""
        check_js = '''
        var t = window.tncode;
        if (!t) return 'no_tncode';
        if (t._result === true) return 'pass';
        var infoInput = document.getElementById('clicaptcha-submit-info');
        if (infoInput && infoInput.value && infoInput.value.indexOf('_ok') > -1) return 'pass';
        if (t._doing === true) return 'dragging';
        if (t._doing === false && t._track_data && t._track_data.length > 1) return 'sent';
        return 'wait';
        '''
        start = time.time()
        sent_time = None
        while time.time() - start < timeout:
            try:
                result = self.browser.run_js(check_js)
                if result == 'pass':
                    return True
                if result == 'sent':
                    if sent_time is None:
                        sent_time = time.time()
                    elif time.time() - sent_time > 2.5:
                        return 'retry'
            except:
                pass
            time.sleep(0.3)
        try:
            return bool(self.browser.run_js('''
            var t = window.tncode;
            if (t && t._result === true) return true;
            var inp = document.getElementById('clicaptcha-submit-info');
            if (inp && inp.value && inp.value.indexOf('_ok') > -1) return true;
            return false;
            '''))
        except:
            return False

    def solve_slider(self, max_attempts=5, wait_timeout=5, fallback_distances=None):
        """破解滑块验证"""
        logger.info("🤖 开始破解滑块验证...")

        # 初始化滑块识别器
        solver = SliderSolver(self.browser, self.ocr)

        # 等待滑块出现
        time.sleep(2)
        for _ in range(10):
            exists = self.browser.run_js('''
            var s = document.querySelector('.slide_block');
            return !!(s && s.getBoundingClientRect().width > 0);
            ''')
            if exists:
                break
            # 尝试触发显示
            self.browser.run_js('''
            var tn = document.querySelector('.tncode');
            if (tn) tn.click();
            var div = document.querySelector('.tncode_div');
            if (div) div.style.display = 'block';
            ''')
            time.sleep(0.5)

        # 多次尝试
        for attempt in range(max_attempts):
            if self.check_slider_passed():
                logger.info("✅ 验证已通过")
                return True

            logger.info(f"🔄 尝试 {attempt + 1}/{max_attempts}")

            # 等待图片加载
            for _ in range(20):
                ready = self.browser.run_js('''
                var t = window.tncode;
                var img = document.querySelector('.tncode_div img');
                var bgCanvas = document.querySelector('.tncode_canvas_bg');
                return !!(t && t._img_loaded && img && img.complete && img.naturalWidth > 0
                         && bgCanvas && bgCanvas.width > 0 && bgCanvas.height > 0);
                ''')
                if ready:
                    break
                time.sleep(0.5)

            time.sleep(0.5)

            # 使用 SliderSolver 识别候选缺口（图片坐标）
            logger.debug("开始识别候选缺口...")
            gaps = solver.solve_candidates(max_candidates=3)
            logger.debug(f"候选缺口识别完成: {gaps}")

            if gaps:
                for gap in gaps:
                    logger.info(f"📐 尝试缺口位置: {gap}px")

                    if not self.drag_slider(gap):
                        continue
                    result = self._wait_for_tncode_result(timeout=wait_timeout)
                    if result is True:
                        logger.info("✅ 滑块验证通过！")
                        return True
                    # 诊断：dump tncode 状态
                    try:
                        diag = self.browser.run_js('''
                        var t = window.tncode;
                        return JSON.stringify({
                            result: t ? t._result : null,
                            err_c: t ? t._err_c : null,
                            doing: t ? t._doing : null,
                            mark_offset: t ? t._mark_offset : null,
                            track_len: (t && t._track_data) ? t._track_data.length : 0,
                            clicaptcha: (document.getElementById('clicaptcha-submit-info') || {}).value || 'N/A'
                        });
                        ''')
                        logger.debug(f"tncode 诊断: {diag}")
                    except:
                        pass
                    logger.debug(f"候选 {gap}px 验证结果: {result}，继续尝试候选/刷新重试")
            else:
                logger.debug("缺口候选识别失败")

            if fallback_distances and attempt >= max_attempts - 2:
                logger.info("⚠️ 精确识别未通过，尝试备用距离...")
                for dist in fallback_distances:
                    if self.drag_slider(dist):
                        result = self._wait_for_tncode_result(timeout=wait_timeout)
                        if result is True:
                            logger.info(f"✅ 滑块验证通过！(备用距离: {dist}px)")
                            return True

            # 刷新验证码
            self.browser.run_js('''
            var t = window.tncode;
            if (t) { if (t.refresh) t.refresh(); else if (t._reset) t._reset(); }
            ''')
            time.sleep(2)

        logger.error("❌ 滑块验证失败")
        return False

    def login(self):
        """登录"""
        logger.info(f"🔐 登录账号: {self.username}")

        self.browser.get(LOGIN_URL)
        time.sleep(2)
        if not self._wait_cloudflare_clear():
            return False

        # 输入账号密码
        filled = None
        for _ in range(15):
            try:
                if self._is_logged_in():
                    logger.info("✅ 已登录，跳过输入账号密码")
                    return True
                filled = self._fill_login_form()
                if filled.get('ok'):
                    time.sleep(0.5)
                    break
            except Exception as e:
                filled = {'ok': False, 'error': str(e)}
            time.sleep(1)

        if not filled or not filled.get('ok'):
            logger.error(f"❌ 输入账号密码失败: {self._login_debug_message(filled)}")
            return False

        # 处理滑块
        try:
            tncode = self.browser.ele('.tncode', timeout=3)
            if tncode:
                text_span = self.browser.ele('.tncode-text', timeout=1)
                if text_span and '点击' in text_span.text:
                    tncode.click()
                    time.sleep(1)

                if not self.solve_slider(
                    max_attempts=8,
                    wait_timeout=7,
                    fallback_distances=[60, 90, 120, 80, 110, 150]
                ):
                    return False
        except:
            pass  # 没有滑块验证

        # 提交登录
        self.browser.run_js('''
        var form = document.querySelector("form[name='login']");
        if (form) form.submit();
        ''')
        time.sleep(3)

        # 验证登录成功
        html = self.browser.html
        if 'member.php?mod=logging&action=logout' in html:
            match = re.search(r'title="访问我的空间">([^<]+)</a>', html)
            if match:
                self.display_name = match.group(1).strip()
            logger.info(f"✅ 登录成功: {self.display_name}")
            return True

        if '欢迎您回来' in html or 'succeedmessage' in html:
            logger.info("✅ 登录成功")
            return True

        if 'member.php?mod=logging' not in self.browser.url:
            logger.info("✅ 登录成功（已跳转）")
            return True

        logger.error("❌ 登录失败，请检查账号密码")
        return False

    def _is_logged_in(self):
        """检查是否已经登录"""
        try:
            html = self.browser.html or ''
            return 'member.php?mod=logging&action=logout' in html or 'action=logout' in html
        except Exception:
            return False

    def _cloudflare_status(self):
        """检查是否停在 Cloudflare 安全验证页"""
        try:
            result = self.browser.run_js('''
            var text = (document.body && document.body.innerText || '');
            var title = document.title || '';
            var isCf = /Just a moment/i.test(title)
                || /Performing security verification/i.test(text)
                || /cf-turnstile-response/i.test(document.documentElement.innerHTML);
            var ray = (text.match(/Ray ID:\\s*([a-z0-9]+)/i) || [])[1] || '';
            return {blocked: !!isCf, title: title, ray: ray, text: text.slice(0, 220)};
            ''')
            return result if isinstance(result, dict) else {'blocked': False}
        except Exception as e:
            return {'blocked': False, 'error': str(e)}

    def _wait_cloudflare_clear(self):
        """等待 Cloudflare 正常放行；不做安全验证绕过"""
        timeout = int(os.getenv('LAOWANG_CF_WAIT', '60'))
        start = time.time()
        warned = False
        last_status = {}
        while time.time() - start < timeout:
            last_status = self._cloudflare_status()
            if not last_status.get('blocked'):
                return True
            if not warned:
                logger.warning("⚠️ 当前停在 Cloudflare 安全验证页，等待站点自动放行...")
                warned = True
            time.sleep(3)

        logger.error(
            "❌ Cloudflare 安全验证未通过，青龙无头浏览器未进入论坛登录页。"
            f" Ray ID: {last_status.get('ray') or 'N/A'}。"
            " 这不是 LAOWANG_ACCOUNT 格式问题；可尝试更换运行网络、取消或更换 LAOWANG_CUSTOM_HOST，"
            "或使用能正常通过 Cloudflare 的浏览器环境。"
        )
        return False

    def _fill_login_form(self):
        """使用 JS 兼容 Discuz 不同登录表单结构"""
        username = json.dumps(self.username)
        password = json.dumps(self.password)
        script = f'''
        var username = {username};
        var password = {password};

        function visible(el) {{
            if (!el) return false;
            var r = el.getBoundingClientRect();
            var s = window.getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
        }}

        function pick(selectors) {{
            var found = [];
            for (var i = 0; i < selectors.length; i++) {{
                found = found.concat(Array.from(document.querySelectorAll(selectors[i])));
            }}
            if (!found.length) return null;
            return found.find(visible) || found[0];
        }}

        function setValue(el, value) {{
            el.focus();
            var setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value');
            if (setter && setter.set) setter.set.call(el, value);
            else el.value = value;
            el.dispatchEvent(new Event('input', {{bubbles: true}}));
            el.dispatchEvent(new Event('change', {{bubbles: true}}));
        }}

        var userEl = pick([
            'input[name="username"]',
            'input[id^="username"]',
            'input[id*="username"]',
            'input[name="email"]',
            'input[type="email"]',
            'input[type="text"]'
        ]);
        var passEl = pick([
            'input[name="password"]',
            'input[id^="password"]',
            'input[id*="password"]',
            'input[type="password"]'
        ]);

        var inputs = Array.from(document.querySelectorAll('input')).slice(0, 20).map(function(el) {{
            return {{
                type: el.type || '',
                name: el.name || '',
                id: el.id || '',
                placeholder: el.placeholder || '',
                visible: visible(el)
            }};
        }});

        if (!userEl || !passEl) {{
            return {{
                ok: false,
                url: location.href,
                title: document.title,
                has_tncode: !!document.querySelector('.tncode,.tncode_div,.slide_block'),
                text: (document.body && document.body.innerText || '').slice(0, 300),
                inputs: inputs
            }};
        }}

        setValue(userEl, username);
        setValue(passEl, password);
        return {{
            ok: true,
            user: {{name: userEl.name || '', id: userEl.id || '', type: userEl.type || ''}},
            pass: {{name: passEl.name || '', id: passEl.id || '', type: passEl.type || ''}},
            inputs: inputs.length
        }};
        '''
        result = self.browser.run_js(script)
        return result if isinstance(result, dict) else {'ok': False, 'raw': result}

    def _login_debug_message(self, data):
        """格式化登录页调试信息"""
        if not isinstance(data, dict):
            data = {}
        try:
            info = {
                'url': data.get('url') or getattr(self.browser, 'url', ''),
                'title': data.get('title', ''),
                'has_tncode': data.get('has_tncode'),
                'text': data.get('text', ''),
                'inputs': data.get('inputs', []),
                'error': data.get('error', '')
            }
            if os.getenv('LAOWANG_DEBUG', '').lower() == 'true':
                debug_path = os.path.join(os.getcwd(), 'laowang_login_debug.html')
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(self.browser.html or '')
                info['html_saved'] = debug_path
            return json.dumps(info, ensure_ascii=False)[:1200]
        except Exception as e:
            return str(e)

    def sign(self):
        """签到"""
        logger.info("📝 访问签到页面...")
        self.browser.get(SIGN_URL)
        time.sleep(2)

        html = self.browser.html

        # 检查是否已签到
        if any(x in html for x in ['今日已签', 'btnvisted', '已签到', '已经签到', '今日已领']):
            return True, f"✅ {self.display_name} 今日已签到"

        # 点击签到按钮
        try:
            clicked = self.browser.run_js('''
            var btn = document.querySelector('.btn.J_chkitot') || document.querySelector('[class*="chkitot"]');
            if (btn) { btn.click(); return true; }
            return false;
            ''')

            if not clicked:
                logger.info("未找到签到按钮，尝试直接调用签到接口...")
                sign_target = self.browser.run_js(f'''
                var fallback = "{SIGN_API_URL}";
                var nodes = Array.from(document.querySelectorAll('a,button,input'));
                for (var i = 0; i < nodes.length; i++) {{
                    var n = nodes[i];
                    var href = n.href || n.getAttribute('href') || '';
                    if (href && href.indexOf('operation=qiandao') > -1) return href;
                    var onclick = n.getAttribute('onclick') || '';
                    var m = onclick.match(/(plugin\\.php\\?id=k_misign:sign[^'"\\s<>]+)/);
                    if (m) return new URL(m[1].replace(/&amp;/g, '&'), location.origin).href;
                }}
                return fallback;
                ''')
                logger.info(f"签到接口: {str(sign_target)[:120]}")
                self.browser.get(sign_target or SIGN_API_URL)
                time.sleep(2)
                api_html = self.browser.html
                api_text = self.browser.run_js('return document.body ? document.body.innerText : "";') or api_html

                if any(x in api_text for x in ['签到成功', '恭喜您', '已获得奖励']):
                    return True, f"✅ {self.display_name} 签到成功"
                if any(x in api_text for x in ['已经签到', '已签到', '今日已签', '今日已领']):
                    return True, f"✅ {self.display_name} 今日已签到"
                if any(x in api_text for x in ['验证', 'captcha', '滑块', '安全验证']):
                    logger.info(f"签到接口验证响应: {api_text[:200]}")
                    logger.info("🤖 签到接口需要验证，尝试处理滑块...")
                    try:
                        tncode = self.browser.ele('.tncode', timeout=3)
                        if tncode:
                            tncode.click()
                            time.sleep(1)
                            if not self.solve_slider(
                                max_attempts=8,
                                wait_timeout=7,
                                fallback_distances=[60, 90, 120, 80, 110, 150]
                            ):
                                return False, f"❌ {self.display_name}: 签到接口滑块验证失败"
                            self.submit_verification()
                            time.sleep(2)

                            self.browser.get(sign_target or SIGN_API_URL)
                            time.sleep(2)
                            retry_text = self.browser.run_js('return document.body ? document.body.innerText : "";') or self.browser.html
                            if any(x in retry_text for x in ['签到成功', '恭喜您', '已获得奖励']):
                                return True, f"✅ {self.display_name} 签到成功"
                            if any(x in retry_text for x in ['已经签到', '已签到', '今日已签', '今日已领']):
                                return True, f"✅ {self.display_name} 今日已签到"
                            logger.debug(f"签到接口二次返回: {retry_text[:500]}")
                    except Exception as e:
                        logger.debug(f"签到接口验证处理失败: {e}")
                    return False, f"❌ {self.display_name}: 签到接口需要验证"

                logger.debug(f"签到接口返回: {api_text[:500]}")
                return False, f"❌ {self.display_name}: 未找到签到按钮"

            time.sleep(2)

            # 检查是否需要滑块验证
            try:
                tncode = self.browser.ele('.tncode', timeout=3)
                if tncode:
                    tncode.click()
                    time.sleep(1)
                    if not self.solve_slider(
                        max_attempts=8,
                        wait_timeout=7,
                        fallback_distances=[60, 90, 120, 80, 110, 150]
                    ):
                        return False, f"❌ {self.display_name}: 签到滑块验证失败"
                    self.submit_verification()
                    time.sleep(2)
            except:
                pass

            # 检查签到结果
            time.sleep(2)
            html = self.browser.html
            text = self.browser.run_js('return document.body ? document.body.innerText : "";') or ''
            result_text = html + '\n' + text
            if any(x in result_text for x in [
                '今日已签', 'btnvisted', '已签到', '已经签到', '今日已领',
                '签到成功', '恭喜您', '已获得奖励', '打卡成功'
            ]):
                return True, f"✅ {self.display_name} 签到成功"
            if '验证成功' in text and '提交' in text:
                logger.info("检测到验证成功但仍在提交页，重新提交...")
                if self.submit_verification():
                    time.sleep(3)
                    html = self.browser.html
                    text = self.browser.run_js('return document.body ? document.body.innerText : "";') or ''
                    result_text = html + '\n' + text
                    if any(x in result_text for x in [
                        '今日已签', 'btnvisted', '已签到', '已经签到', '今日已领',
                        '签到成功', '恭喜您', '已获得奖励', '打卡成功'
                    ]):
                        return True, f"✅ {self.display_name} 签到成功"
            logger.info(f"签到结果页面 URL: {self.browser.url[:120]}")
            logger.info(f"签到结果页面内容: {text[:300]}")

            return False, f"❌ {self.display_name}: 签到结果不明确"

        except Exception as e:
            return False, f"❌ {self.display_name}: 签到异常 {e}"

    def run(self):
        """执行签到流程"""
        if not self.init_browser():
            return False, "浏览器初始化失败"

        try:
            # 初始化 OCR
            self.init_ocr()

            # 登录
            if not self.login():
                return False, f"❌ {self.username}: 登录失败"

            # 签到
            success, msg = self.sign()
            return success, msg

        except Exception as e:
            return False, f"❌ {self.username}: 运行异常 {e}"
        finally:
            if self.browser:
                try:
                    self.browser.quit()
                except:
                    pass


def main():
    """主函数"""
    print("""
╔═══════════════════════════════════════════════╗
║       老王论坛自动签到 v6.0                   ║
║       DrissionPage + ddddocr                  ║
╚═══════════════════════════════════════════════╝
""")

    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 获取账号配置
    account = os.getenv('LAOWANG_ACCOUNT', '').strip()
    if not account:
        print("❌ 未配置 LAOWANG_ACCOUNT 环境变量")
        print()
        print("配置方法:")
        print("  方式1: export LAOWANG_ACCOUNT=用户名:密码")
        print("  方式2: export LAOWANG_ACCOUNT=用户1:密码1&用户2:密码2")
        print("  方式3: 在 .env 文件中添加 LAOWANG_ACCOUNT=用户名:密码")
        print()
        print("可选配置:")
        print("  LAOWANG_DEBUG=true     # 开启调试模式")
        print("  MAX_RANDOM_DELAY=300   # 最大随机延迟秒数")
        push_notify("老王论坛签到失败", "未配置 LAOWANG_ACCOUNT")
        sys.exit(1)

    # 解析多账号
    accounts = []
    for item in split_account_items(account):
        item = item.strip()
        if ':' in item:
            parts = item.split(':', 1)
            accounts.append((parts[0].strip(), parts[1].strip()))

    if not accounts:
        print("❌ 账号格式错误，正确格式: 用户名:密码")
        sys.exit(1)

    print(f"👥 共 {len(accounts)} 个账号")

    # 随机延迟
    max_delay = int(os.getenv('MAX_RANDOM_DELAY', '300'))
    use_random = os.getenv('RANDOM_SIGNIN', 'true').lower() == 'true'
    if use_random and max_delay > 0:
        delay = random.randint(0, max_delay)
        print(f"⏳ 随机延迟 {delay} 秒...")
        time.sleep(delay)

    # 执行签到
    results = []
    for i, (username, password) in enumerate(accounts, 1):
        print(f"\n{'─' * 50}")
        print(f"🙍 账号 {i}/{len(accounts)}: {username}")

        signer = LaowangSigner(username, password)
        success, msg = signer.run()

        results.append((username, success, msg))
        print(msg)

        # 账号间延迟
        if i < len(accounts):
            delay = random.uniform(3, 8)
            print(f"⏳ 等待 {delay:.1f} 秒...")
            time.sleep(delay)

    # 汇总结果
    print(f"\n{'═' * 50}")
    success_count = sum(1 for _, s, _ in results if s)
    print(f"📊 签到结果: {success_count}/{len(accounts)} 成功")

    summary_lines = []
    for username, success, msg in results:
        status = "✅" if success else "❌"
        summary_lines.append(f"{status} {username}")

    print("\n".join(summary_lines))

    # 推送通知
    summary = f"成功 {success_count}/{len(accounts)}\n" + "\n".join(summary_lines)
    push_notify("老王论坛签到结果", summary)

    # 返回状态码
    sys.exit(0 if success_count == len(accounts) else 1)


if __name__ == "__main__":
    main()
