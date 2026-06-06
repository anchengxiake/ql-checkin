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

    def _get_sprite_info(self):
        """获取精灵图尺寸信息"""
        try:
            info = self.browser.run_js('''
            var t = window.tncode;
            var img = (t && t._img) || document.querySelector('.tncode_div img');
            if (!img || !img.complete) return null;
            return JSON.stringify({
                naturalW: img.naturalWidth,
                naturalH: img.naturalHeight,
                imgW: (t && t._img_w) || 240,
                imgH: (t && t._img_h) || 150
            });
            ''')
            if isinstance(info, str):
                import json
                return json.loads(info)
            return info
        except:
            return None

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
                import tempfile
                import os

                # 获取背景图（带缺口）- 直接从 canvas 截图
                bg_b64 = self.browser.run_js('''
                var bgCanvas = document.querySelector('.tncode_canvas_bg');
                if (!bgCanvas) return null;
                return bgCanvas.toDataURL('image/png').split(',')[1];
                ''')

                # 获取完整图（无缺口）- 从精灵图正确区域提取
                # 先探测精灵图布局，逐行尝试提取
                sprite_info = self._get_sprite_info()
                imgW = 240
                imgH = 150
                if sprite_info:
                    imgW = sprite_info.get('imgW', 240)
                    imgH = sprite_info.get('imgH', 150)

                fg_b64 = self.browser.run_js(f'''
                var t = window.tncode;
                var img = (t && t._img) || document.querySelector('.tncode_div img');
                if (!img || !img.complete || img.naturalWidth === 0) return null;
                var imgW = {imgW};
                var imgH = {imgH};
                var natW = img.naturalWidth;
                var natH = img.naturalHeight;
                // 精灵图可能按行排列：row0=背景, row1=拼图块, row2=阴影
                // 或者：row0=背景, row1=拼图块+阴影
                // 取第二行（row1）作为拼图块
                var tmpCanvas = document.createElement('canvas');
                tmpCanvas.width = imgW;
                tmpCanvas.height = imgH;
                var ctx = tmpCanvas.getContext('2d');
                ctx.drawImage(img, 0, imgH, imgW, imgH, 0, 0, imgW, imgH);
                return tmpCanvas.toDataURL('image/png').split(',')[1];
                ''')

                if bg_b64 and fg_b64:
                    # 尝试 slide_match
                    result = self.ddddocr.slide_match(
                        base64.b64decode(fg_b64),
                        base64.b64decode(bg_b64)
                    )
                    if result and 'target' in result:
                        x = result['target'][0]
                        logger.info(f"🎯 ddddocr 识别: {x}px")
                        if 10 < x < imgW - 10:
                            return int(x)

                    # slide_match 结果不合理，尝试截图方式
                    logger.debug("slide_match 结果可疑，尝试截图方式...")

                # 备用：截图方式 - 直接截图验证码区域
                bg_el = self.browser.ele('.tncode_canvas_bg', timeout=1)
                if bg_el:
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                        bg_path = f.name
                    bg_el.get_screenshot(bg_path)

                    slider_img = self.browser.ele('.tncode_div img', timeout=1)
                    if slider_img:
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                            fg_path = f.name
                        slider_img.get_screenshot(fg_path)

                        with open(fg_path, 'rb') as f:
                            fg_bytes = f.read()
                        with open(bg_path, 'rb') as f:
                            bg_bytes = f.read()

                        result = self.ddddocr.slide_match(fg_bytes, bg_bytes)
                        try:
                            os.unlink(fg_path)
                            os.unlink(bg_path)
                        except:
                            pass

                        if result and 'target' in result:
                            x = result['target'][0]
                            logger.info(f"🎯 ddddocr 截图识别: {x}px")
                            if 10 < x < imgW - 10:
                                return int(x)

            except Exception as e:
                logger.debug(f"ddddocr 失败: {e}")

        # 方法2: Canvas 像素比对
        try:
            # 先获取精灵图信息用于正确提取
            sprite_info = self._get_sprite_info()
            imgW = 240
            imgH = 150
            if sprite_info:
                imgW = sprite_info.get('imgW', 240)
                imgH = sprite_info.get('imgH', 150)

            gap = self.browser.run_js(f'''
            var t = window.tncode;
            var bgCanvas = document.querySelector('.tncode_canvas_bg');
            if (!bgCanvas || bgCanvas.width === 0) return -1;

            var img = (t && t._img) || document.querySelector('.tncode_div img');
            if (!img || !img.complete || img.naturalWidth === 0) return -2;

            var imgW = {imgW};
            var imgH = {imgH};
            var markW = (t && t._mark_w) || 50;
            var maxOffset = imgW - markW;

            // 从精灵图第二行提取完整图（含拼图块）
            var tmpCanvas = document.createElement('canvas');
            tmpCanvas.width = imgW;
            tmpCanvas.height = imgH;
            var tmpCtx = tmpCanvas.getContext('2d');
            try {{
                tmpCtx.drawImage(img, 0, imgH, imgW, imgH, 0, 0, imgW, imgH);
            }} catch(e) {{ return -3; }}

            var bgData = bgCanvas.getContext('2d').getImageData(0, 0, imgW, imgH);
            var fullData = tmpCtx.getImageData(0, 0, imgW, imgH);

            var diffCounts = new Array(imgW).fill(0);
            var checkRows = [25, 40, 55, 70, 85, 100, 115, 130];
            for (var ri = 0; ri < checkRows.length; ri++) {{
                var y = checkRows[ri];
                for (var x = 0; x < imgW; x++) {{
                    var idx = (y * imgW + x) * 4;
                    var dr = Math.abs(bgData.data[idx] - fullData.data[idx]);
                    var dg = Math.abs(bgData.data[idx+1] - fullData.data[idx+1]);
                    var db = Math.abs(bgData.data[idx+2] - fullData.data[idx+2]);
                    if (dr + dg + db > 30) diffCounts[x]++;
                }}
            }}

            var bestX = -1, bestSum = 0;
            for (var x = 0; x <= maxOffset; x++) {{
                var sum = 0;
                for (var w = 0; w < markW; w++) sum += diffCounts[x + w];
                if (sum > bestSum) {{ bestSum = sum; bestX = x; }}
            }}

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
        """模拟滑块拖动 - 使用 DrissionPage Actions（CDP 可信事件）"""
        import random as _rnd

        # 添加随机偏移
        offset = _rnd.randint(-3, 3)
        adjusted_dist = max(10, distance + offset)

        try:
            # 重置 tncode 状态
            self.browser.run_js('try { window.tncode._reset(); } catch(e) {}')
            time.sleep(0.3)

            # 获取滑块元素
            slider = self.browser.ele('.slide_block', timeout=3)
            if not slider:
                logger.debug("找不到滑块元素")
                return False

            # 使用 DrissionPage Actions（内部调用 CDP Input.dispatchMouseEvent，isTrusted=true）
            from DrissionPage.common import Actions
            actions = Actions(self.browser)

            # 物理拖动：hold → 分段 move → release
            # 先移到滑块上
            actions.move_to(slider, duration=0.3)
            time.sleep(0.1)

            # 按下
            actions.hold()
            time.sleep(0.15)

            # 分段拖动（模拟真人加速-减速）
            moved = 0
            mid = adjusted_dist * _rnd.uniform(0.55, 0.75)
            step_size = max(3, adjusted_dist // 20)

            while moved < adjusted_dist:
                remaining = adjusted_dist - moved
                if moved < mid:
                    # 加速阶段
                    step = min(step_size + _rnd.randint(0, 5), remaining)
                else:
                    # 减速阶段
                    step = max(2, step_size - _rnd.randint(0, 3))
                    step = min(step, remaining)

                if step <= 0:
                    break

                # 添加 Y 轴微小偏移
                y_offset = _rnd.randint(-3, 3)
                actions.move(step, y_offset, duration=_rnd.uniform(0.02, 0.06))
                moved += step

            # 超调回退
            time.sleep(_rnd.uniform(0.05, 0.1))
            actions.move(3, 0, duration=0.05)
            time.sleep(_rnd.uniform(0.05, 0.08))
            actions.move(-3, 0, duration=0.05)

            # 释放前停顿
            time.sleep(_rnd.uniform(0.08, 0.15))

            # 释放
            actions.release()
            time.sleep(0.5)

            # 调试信息
            debug_info = self.browser.run_js('''
            var t = window.tncode;
            if (!t) return 'no_tncode';
            return JSON.stringify({
                mark_offset: t._mark_offset,
                block_x: t._block_x,
                result: t._result,
                img_w: t._img_w,
                mark_w: t._mark_w
            });
            ''')
            logger.debug(f"拖动调试: {debug_info}")
            return True

        except Exception as e:
            logger.debug(f"Actions 拖动失败: {e}")
            # 回退：直接 CDP 调用
            return self._drag_with_cdp_fallback(distance)

    def _drag_with_cdp_fallback(self, distance):
        """回退方案：直接调用 CDP Input.dispatchMouseEvent"""
        import random as _rnd

        try:
            self.browser.run_js('try { window.tncode._reset(); } catch(e) {}')
            time.sleep(0.3)

            slider = self.browser.ele('.slide_block', timeout=3)
            if not slider:
                return False

            rect = slider.rect
            startX = round(rect.midpoint[0])
            startY = round(rect.midpoint[1])

            # mousedown
            self.browser.run_cdp('Input.dispatchMouseEvent',
                                 type='mousePressed', x=startX, y=startY,
                                 button='left', clickCount=1)
            time.sleep(0.1)

            # 分段 mousemove
            moved = 0
            mid = distance * _rnd.uniform(0.55, 0.75)
            step = max(3, distance // 20)

            while moved < distance:
                remaining = distance - moved
                if moved < mid:
                    s = min(step + _rnd.randint(0, 5), remaining)
                else:
                    s = max(2, step - _rnd.randint(0, 3))
                    s = min(s, remaining)
                if s <= 0:
                    break
                moved += s
                x = startX + moved
                y = startY + _rnd.randint(-3, 3)
                self.browser.run_cdp('Input.dispatchMouseEvent',
                                     type='mouseMoved', x=x, y=y, button='left')
                time.sleep(_rnd.uniform(0.02, 0.06))

            # 超调回退
            time.sleep(0.05)
            self.browser.run_cdp('Input.dispatchMouseEvent',
                                 type='mouseMoved', x=startX + distance + 3, y=startY, button='left')
            time.sleep(0.05)
            self.browser.run_cdp('Input.dispatchMouseEvent',
                                 type='mouseMoved', x=startX + distance, y=startY, button='left')
            time.sleep(0.1)

            # mouseup
            self.browser.run_cdp('Input.dispatchMouseEvent',
                                 type='mouseReleased', x=startX + distance, y=startY,
                                 button='left', clickCount=1)
            time.sleep(0.5)

            debug_info = self.browser.run_js('''
            var t = window.tncode;
            if (!t) return 'no_tncode';
            return JSON.stringify({mark_offset: t._mark_offset, block_x: t._block_x, result: t._result});
            ''')
            logger.debug(f"CDP 回退拖动调试: {debug_info}")
            return True

        except Exception as e:
            logger.debug(f"CDP 回退拖动失败: {e}")
            return False

    def _check_passed(self):
        """检查验证是否通过"""
        try:
            result = self.browser.run_js('''
            var t = window.tncode;
            if (!t) return false;
            // 多种成功判断
            if (t._result === true) return true;
            if (t._result === 'success') return true;
            if (typeof t.isVerified === 'function' && t.isVerified()) return true;
            // 检查隐藏输入
            var inp = document.getElementById('clicaptcha-submit-info');
            if (inp && inp.value && inp.value.indexOf('_ok') > -1) return true;
            // 检查滑块是否到达终点
            if (t._mark_offset > 0 && t._block_x > 0) {{
                var imgW = t._img_w || 240;
                var markW = t._mark_w || 50;
                if (t._mark_offset >= imgW - markW - 5) return true;
            }}
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
        for _ in range(10):
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

            # 等待图片加载（更长超时）
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

            # 额外等待确保渲染完成
            time.sleep(0.5)

            # 识别缺口
            gap = self._find_tncode_gap()
            if gap > 5:
                logger.info(f"📐 缺口位置: {gap}px, 开始拖动...")
                # 拖动
                if self._drag_slider(gap):
                    # 轮询等待验证结果（tncode 验证是异步的）
                    for _ in range(10):
                        time.sleep(0.5)
                        if self._check_passed():
                            logger.info("✅ 滑块验证通过！")
                            return True
                    logger.debug("拖动后验证未通过，准备重试")
            else:
                logger.debug(f"缺口识别失败: {gap}")

            # 刷新验证码
            try:
                self.browser.run_js('''
                var t = window.tncode;
                if (t && typeof t.refresh === 'function') t.refresh();
                else if (t && typeof t._reset === 'function') t._reset();
                ''')
                time.sleep(2)
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
