#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
老王论坛自动签到脚本 v5.0（简化版）
使用 DrissionPage + ddddocr 自动处理滑块验证

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

# ============ 配置 ============
BASE_URL = "https://laowang.vip"
LOGIN_URL = f"{BASE_URL}/member.php?mod=logging&action=login"
SIGN_PAGE_URL = f"{BASE_URL}/plugin.php?id=k_misign:sign"

# 日志配置
logging.basicConfig(
    level=logging.DEBUG if os.getenv('LAOWANG_DEBUG', '').lower() == 'true' else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============ 通知模块 ============
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
        except:
            pass


class LaowangSigner:
    """老王论坛签到器"""

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.display_name = username
        self.browser = None
        self.ddddocr = None

    def _init_ddddocr(self):
        """初始化 ddddocr"""
        try:
            import ddddocr
            self.ddddocr = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)
            logger.info("✅ ddddocr 已加载")
        except ImportError:
            logger.warning("⚠️ ddddocr 未安装，将使用 Canvas 比对")

    def _init_browser(self):
        """初始化浏览器"""
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions

            co = ChromiumOptions()
            co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            co.set_argument('--disable-blink-features=AutomationControlled')
            co.set_argument('--no-sandbox')
            co.set_argument('--disable-gpu')
            co.set_argument('--window-size=1920,1080')
            co.auto_port()
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

    def _find_tncode_gap(self):
        """
        识别滑块缺口位置
        优先使用 ddddocr，失败则用 Canvas 比对
        """
        # 方法1: ddddocr
        if self.ddddocr:
            try:
                import base64
                import json

                img_data = self.browser.run_js('''
                var t = window.tncode;
                var result = {bg: null, fg: null};

                try {
                    var bgCanvas = document.querySelector('.tncode_canvas_bg');
                    if (bgCanvas) {
                        result.bg = bgCanvas.toDataURL('image/png').split(',')[1];
                    }

                    var img = (t && t._img) || document.querySelector('.tncode_div img');
                    if (img && img.complete && img.naturalWidth > 0) {
                        var tmpCanvas = document.createElement('canvas');
                        var imgW = (t && t._img_w) || 240;
                        var imgH = (t && t._img_h) || 150;
                        tmpCanvas.width = imgW;
                        tmpCanvas.height = imgH;
                        var ctx = tmpCanvas.getContext('2d');
                        ctx.drawImage(img, 0, imgH * 2, imgW, imgH, 0, 0, imgW, imgH);
                        result.fg = tmpCanvas.toDataURL('image/png').split(',')[1];
                    }
                } catch(e) {}

                return JSON.stringify(result);
                ''')

                if isinstance(img_data, str):
                    img_data = json.loads(img_data)

                bg_b64 = img_data.get('bg')
                fg_b64 = img_data.get('fg')

                if bg_b64 and fg_b64:
                    result = self.ddddocr.slide_match(
                        base64.b64decode(fg_b64),
                        base64.b64decode(bg_b64)
                    )
                    if result and 'target' in result:
                        x = result['target'][0]
                        logger.info(f"🎯 ddddocr 识别: {x}px")
                        return int(x)
            except Exception as e:
                logger.debug(f"ddddocr 失败: {e}")

        # 方法2: Canvas 比对
        try:
            gap = self.browser.run_js('''
            var t = window.tncode;
            var bgCanvas = document.querySelector('.tncode_canvas_bg');
            if (!bgCanvas || bgCanvas.width === 0) return -1;

            var img = (t && t._img) || document.querySelector('.tncode_div img');
            if (!img || !img.complete || img.naturalWidth === 0) return -2;

            var imgW = (t && t._img_w) || 240;
            var imgH = (t && t._img_h) || 150;
            var markW = (t && t._mark_w) || 50;
            var maxOffset = imgW - markW;

            var tmpCanvas = document.createElement('canvas');
            tmpCanvas.width = imgW;
            tmpCanvas.height = imgH;
            var tmpCtx = tmpCanvas.getContext('2d');
            try {
                tmpCtx.drawImage(img, 0, imgH * 2, imgW, imgH, 0, 0, imgW, imgH);
            } catch(e) { return -3; }

            var bgData = bgCanvas.getContext('2d').getImageData(0, 0, imgW, imgH);
            var fullData = tmpCtx.getImageData(0, 0, imgW, imgH);

            var diffCounts = new Array(imgW).fill(0);
            var checkRows = [25, 40, 55, 70, 85, 100, 115, 130];
            for (var ri = 0; ri < checkRows.length; ri++) {
                var y = checkRows[ri];
                for (var x = 0; x < imgW; x++) {
                    var idx = (y * imgW + x) * 4;
                    var dr = Math.abs(bgData.data[idx] - fullData.data[idx]);
                    var dg = Math.abs(bgData.data[idx+1] - fullData.data[idx+1]);
                    var db = Math.abs(bgData.data[idx+2] - fullData.data[idx+2]);
                    if (dr + dg + db > 30) diffCounts[x]++;
                }
            }

            var bestX = -1, bestSum = 0;
            for (var x = 0; x <= maxOffset; x++) {
                var sum = 0;
                for (var w = 0; w < markW; w++) sum += diffCounts[x + w];
                if (sum > bestSum) { bestSum = sum; bestX = x; }
            }

            if (bestSum < checkRows.length * markW * 0.2) return -4;
            return bestX;
            ''')

            if gap and gap > 5:
                logger.info(f"🎯 Canvas 识别: {gap}px")
                return int(gap)
        except Exception as e:
            logger.debug(f"Canvas 比对失败: {e}")

        return -1

    def _drag_slider(self, distance):
        """模拟滑块拖动（物理运动轨迹）"""
        import random as _rnd

        mid_ratio = _rnd.uniform(0.55, 0.75)
        y_variance = _rnd.randint(5, 10)

        js_code = f'''
        var DIST = {distance};
        var t = window.tncode;
        var slider = document.querySelector('.slide_block');
        if (!t || !slider) return 'no_handler';

        try {{ t._reset(); }} catch(e) {{}}

        var rect = slider.getBoundingClientRect();
        var startX = Math.round(rect.left + rect.width / 2);
        var startY = Math.round(rect.top + rect.height / 2);

        function makeME(type, x, y, isUp) {{
            return new MouseEvent(type, {{
                bubbles: true, cancelable: true,
                clientX: x, clientY: y,
                button: 0, buttons: isUp ? 0 : 1
            }});
        }}

        // 物理运动轨迹
        var points = [];
        var mid = DIST * {mid_ratio};
        var sum = 0, v = 0, dt = 0.03;
        while (sum < DIST) {{
            var a = sum < mid ? (2.5 + Math.random()) : -(2.0 + Math.random());
            var s = v * dt + 0.5 * a * dt * dt;
            v = v + a * dt;
            sum += s;
            if (sum > DIST) sum = DIST;
            points.push(Math.round(sum));
        }}
        if (points.length > 0) points[points.length - 1] = DIST;

        // 开始拖动
        t._block_start_move(makeME('mousedown', startX, startY, false));

        // 执行轨迹
        for (var i = 0; i < points.length; i++) {{
            var wait = 2 + Math.floor(Math.random() * 8);
            var endWait = Date.now() + wait;
            while (Date.now() < endWait) {{}}

            var x = startX + points[i];
            var y = startY + Math.round((Math.random() - 0.5) * {y_variance} * 2);
            t._block_on_move(makeME('mousemove', x, y, false));
        }}

        // 超调回退
        var wait = 30 + Math.floor(Math.random() * 30);
        var endWait = Date.now() + wait;
        while (Date.now() < endWait) {{}}
        t._block_on_move(makeME('mousemove', startX + DIST + 2, startY, false));
        wait = 30 + Math.floor(Math.random() * 30);
        endWait = Date.now() + wait;
        while (Date.now() < endWait) {{}}
        t._block_on_move(makeME('mousemove', startX + DIST, startY, false));

        // 释放前停顿
        wait = 40 + Math.floor(Math.random() * 40);
        endWait = Date.now() + wait;
        while (Date.now() < endWait) {{}}

        // 释放
        t._block_on_end(makeME('mouseup', startX + DIST, startY, true));

        return 'ok:' + t._mark_offset;
        '''

        try:
            result = self.browser.run_js(js_code)
            return result and str(result).startswith('ok')
        except Exception as e:
            logger.debug(f"拖动失败: {e}")
            return False

    def _check_passed(self):
        """检查验证是否通过"""
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

    def _solve_slider(self):
        """破解滑块验证"""
        logger.info("🤖 开始破解滑块...")

        # 等待滑块出现
        time.sleep(2)
        for _ in range(5):
            try:
                self.browser.ele('.slide_block', timeout=1)
                break
            except:
                time.sleep(0.5)

        # 尝试 5 次
        for attempt in range(5):
            if self._check_passed():
                logger.info("✅ 验证已通过")
                return True

            logger.info(f"🔄 尝试 {attempt + 1}/5")

            # 等待图片加载
            for _ in range(10):
                ready = self.browser.run_js('''
                var t = window.tncode;
                var img = document.querySelector('.tncode_div img');
                return !!(t && t._img_loaded && img && img.complete && img.naturalWidth > 0);
                ''')
                if ready:
                    break
                time.sleep(0.5)

            # 识别缺口
            gap = self._find_tncode_gap()
            if gap > 5:
                # 拖动
                if self._drag_slider(gap):
                    time.sleep(1.5)
                    if self._check_passed():
                        logger.info("✅ 滑块验证通过！")
                        return True

            # 刷新验证码
            try:
                self.browser.run_js('''
                var t = window.tncode;
                if (t && typeof t.refresh === 'function') t.refresh();
                ''')
                time.sleep(1.5)
            except:
                pass

        logger.error("❌ 滑块验证失败")
        return False

    def _login(self):
        """登录"""
        logger.info(f"🔐 登录: {self.username}")

        self.browser.get(LOGIN_URL)
        time.sleep(2)

        # 输入账号密码
        self.browser.ele('@name=username').input(self.username)
        self.browser.ele('@name=password').input(self.password)
        time.sleep(0.5)

        # 处理滑块
        try:
            tncode = self.browser.ele('.tncode', timeout=3)
            if tncode:
                text_span = self.browser.ele('.tncode-text', timeout=1)
                if text_span and '点击' in text_span.text:
                    tncode.click()
                    time.sleep(1)

                if not self._solve_slider():
                    return False
        except:
            pass

        # 提交登录
        self.browser.run_js('''
        var f = document.querySelector("form[name='login']");
        if (f) f.submit();
        ''')
        time.sleep(3)

        # 验证登录
        html = self.browser.html
        if 'member.php?mod=logging&action=logout' in html:
            # 提取用户名
            match = re.search(r'title="访问我的空间">([^<]+)</a>', html)
            if match:
                self.display_name = match.group(1).strip()
            logger.info(f"✅ 登录成功: {self.display_name}")
            return True

        if '欢迎您回来' in html or 'succeedmessage' in html:
            logger.info("✅ 登录成功")
            return True

        # 检查是否跳转离开登录页
        if 'member.php?mod=logging' not in self.browser.url:
            logger.info("✅ 登录成功（已跳转）")
            return True

        logger.error("❌ 登录失败")
        return False

    def _sign(self):
        """签到"""
        logger.info("📝 访问签到页面...")
        self.browser.get(SIGN_PAGE_URL)
        time.sleep(2)

        html = self.browser.html

        # 检查已签到
        if any(x in html for x in ['今日已签', 'btnvisted', '已签到']):
            return True, f"✅ {self.display_name} 今日已签到"

        # 点击签到按钮
        try:
            clicked = self.browser.run_js('''
            var btn = document.querySelector('.btn.J_chkitot') || document.querySelector('[class*="chkitot"]');
            if (btn) { btn.click(); return true; }
            return false;
            ''')

            if clicked:
                time.sleep(2)

                # 检查是否需要滑块验证
                try:
                    tncode = self.browser.ele('.tncode', timeout=3)
                    if tncode:
                        tncode.click()
                        time.sleep(1)
                        if not self._solve_slider():
                            return False, f"❌ {self.display_name}: 签到滑块验证失败"
                except:
                    pass

                # 检查结果
                time.sleep(2)
                html = self.browser.html
                if any(x in html for x in ['今日已签', 'btnvisted', '已签到', '签到成功']):
                    return True, f"✅ {self.display_name} 签到成功"

                return False, f"❌ {self.display_name}: 签到结果不明确"
        except Exception as e:
            return False, f"❌ {self.display_name}: 签到失败 {e}"

        return False, f"❌ {self.display_name}: 未找到签到按钮"

    def run(self):
        """执行签到流程"""
        self._init_ddddocr()

        if not self._init_browser():
            return False, "浏览器初始化失败"

        try:
            # 登录
            if not self._login():
                return False, f"❌ {self.username}: 登录失败"

            # 签到
            success, msg = self._sign()
            return success, msg

        except Exception as e:
            return False, f"❌ {self.username}: {e}"
        finally:
            if self.browser:
                try:
                    self.browser.quit()
                except:
                    pass


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════╗
║     老王论坛签到 v5.0（简化版）          ║
║     DrissionPage + ddddocr               ║
╚══════════════════════════════════════════╝
""")

    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 获取配置
    account = os.getenv('LAOWANG_ACCOUNT', '').strip()
    if not account:
        print("❌ 未配置 LAOWANG_ACCOUNT")
        print("\n配置方法:")
        print("  export LAOWANG_ACCOUNT=用户名:密码")
        print("\n可选配置:")
        print("  export LAOWANG_DEBUG=true    # 调试模式")
        push_notify("老王论坛签到失败", "未配置 LAOWANG_ACCOUNT")
        sys.exit(1)

    # 解析账号（支持多账号，用 & 分隔）
    accounts = []
    for item in re.split(r'[&\n]', account):
        item = item.strip()
        if ':' in item:
            parts = item.split(':', 1)
            accounts.append((parts[0].strip(), parts[1].strip()))

    if not accounts:
        print("❌ 账号格式错误")
        print("正确格式: 用户名:密码 或 用户1:密码1&用户2:密码2")
        sys.exit(1)

    # 随机延迟
    max_delay = int(os.getenv('MAX_RANDOM_DELAY', '300'))
    if max_delay > 0 and os.getenv('RANDOM_SIGNIN', 'true').lower() == 'true':
        delay = random.randint(0, max_delay)
        print(f"⏳ 随机延迟 {delay} 秒...")
        time.sleep(delay)

    # 执行签到
    results = []
    for i, (username, password) in enumerate(accounts, 1):
        print(f"\n{'─' * 40}")
        print(f"🙍 账号 {i}/{len(accounts)}: {username}")

        signer = LaowangSigner(username, password)
        success, msg = signer.run()

        results.append((username, success, msg))
        print(msg)

        # 账号间延迟
        if i < len(accounts):
            time.sleep(random.uniform(3, 8))

    # 汇总
    print(f"\n{'─' * 40}")
    success_count = sum(1 for _, s, _ in results if s)
    summary = f"成功: {success_count}/{len(accounts)}\n"
    for username, success, msg in results:
        status = "✅" if success else "❌"
        summary += f"{status} {username}: {msg.split(chr(10))[0]}\n"

    print(summary)
    push_notify("老王论坛签到结果", summary)


if __name__ == "__main__":
    main()
