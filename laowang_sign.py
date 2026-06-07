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
                # Chrome
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                # Edge
                r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
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
        """模拟拖动滑块"""
        try:
            # 生成自然轨迹参数
            total_time = random.randint(1200, 2000)
            overshoot = random.randint(1, 4)

            result = self.browser.run_js(f'''
            var DIST = {distance};
            var TIME = {total_time};
            var OVERSHOOT = {overshoot};

            var t = window.tncode;
            var slider = document.querySelector('.slide_block');
            if (!t || !slider) return 'no_handler';

            try {{ t._reset(); }} catch(e) {{}}

            var rect = slider.getBoundingClientRect();
            if (rect.width === 0) return 'no_rect';

            var startX = Math.round(rect.left + rect.width / 2);
            var startY = Math.round(rect.top + rect.height / 2);

            function me(type, x, y, up) {{
                return new MouseEvent(type, {{
                    bubbles: true, cancelable: true,
                    clientX: x, clientY: y,
                    button: 0, buttons: up ? 0 : 1
                }});
            }}

            // 物理轨迹生成
            var points = [];
            var mid = DIST * 0.65;
            var sum = 0, v = 0, dt = 0.03;
            while (sum < DIST) {{
                var a = sum < mid ? 3.0 : -2.5;
                var s = v * dt + 0.5 * a * dt * dt;
                v += a * dt;
                sum = Math.min(sum + s, DIST);
                points.push(Math.round(sum));
            }}
            if (points.length > 0) points[points.length - 1] = DIST;

            // 时间分配
            var steps = points.length;
            var base = TIME / steps;
            var times = [];
            for (var i = 0; i < steps; i++) {{
                times.push(Math.max(2, Math.round(base + (Math.random() - 0.5) * 30)));
            }}

            // 执行拖动
            t._block_start_move(me('mousedown', startX, startY, false));

            var elapsed = 0;
            for (var i = 0; i < steps; i++) {{
                elapsed += times[i];
                var target = Date.now() + elapsed;
                while (Date.now() < target) {{}}
                var y = startY + Math.round((Math.random() - 0.5) * 20);
                t._block_on_move(me('mousemove', startX + points[i], y, false));
            }}

            // 超调回退
            setTimeout(function() {{
                t._block_on_move(me('mousemove', startX + DIST + OVERSHOOT, startY, false));
                setTimeout(function() {{
                    t._block_on_move(me('mousemove', startX + DIST, startY, false));
                    setTimeout(function() {{
                        t._block_on_end(me('mouseup', startX + DIST, startY, true));
                    }}, 50);
                }}, 50);
            }}, 30);

            return 'ok';
            ''')

            return result == 'ok'

        except Exception as e:
            logger.debug(f"拖动失败: {e}")
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

    def wait_slider_result(self, timeout=6):
        """等待滑块验证结果"""
        start = time.time()
        while time.time() - start < timeout:
            if self.check_slider_passed():
                return True
            time.sleep(0.3)
        return self.check_slider_passed()

    def solve_slider(self, max_attempts=5):
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
                return !!(t && t._img_loaded && img && img.complete && img.naturalWidth > 0);
                ''')
                if ready:
                    break
                time.sleep(0.5)

            time.sleep(0.5)

            # 使用 SliderSolver 识别缺口
            gap = solver.solve()

            if gap > 5:
                logger.info(f"📐 缺口位置: {gap}px")
                if self.drag_slider(gap):
                    if self.wait_slider_result(timeout=6):
                        logger.info("✅ 滑块验证通过！")
                        return True
                    logger.debug("验证未通过，重试...")
            else:
                logger.debug(f"缺口识别失败: {gap}")

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

        # 输入账号密码
        try:
            self.browser.ele('@name=username').input(self.username)
            self.browser.ele('@name=password').input(self.password)
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"❌ 输入账号密码失败: {e}")
            return False

        # 处理滑块
        try:
            tncode = self.browser.ele('.tncode', timeout=3)
            if tncode:
                text_span = self.browser.ele('.tncode-text', timeout=1)
                if text_span and '点击' in text_span.text:
                    tncode.click()
                    time.sleep(1)

                if not self.solve_slider():
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

    def sign(self):
        """签到"""
        logger.info("📝 访问签到页面...")
        self.browser.get(SIGN_URL)
        time.sleep(2)

        html = self.browser.html

        # 检查是否已签到
        if any(x in html for x in ['今日已签', 'btnvisted', '已签到']):
            return True, f"✅ {self.display_name} 今日已签到"

        # 点击签到按钮
        try:
            clicked = self.browser.run_js('''
            var btn = document.querySelector('.btn.J_chkitot') || document.querySelector('[class*="chkitot"]');
            if (btn) { btn.click(); return true; }
            return false;
            ''')

            if not clicked:
                return False, f"❌ {self.display_name}: 未找到签到按钮"

            time.sleep(2)

            # 检查是否需要滑块验证
            try:
                tncode = self.browser.ele('.tncode', timeout=3)
                if tncode:
                    tncode.click()
                    time.sleep(1)
                    if not self.solve_slider():
                        return False, f"❌ {self.display_name}: 签到滑块验证失败"
            except:
                pass

            # 检查签到结果
            time.sleep(2)
            html = self.browser.html
            if any(x in html for x in ['今日已签', 'btnvisted', '已签到', '签到成功']):
                return True, f"✅ {self.display_name} 签到成功"

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
    for item in re.split(r'[&\n]', account):
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
    if max_delay > 0:
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
