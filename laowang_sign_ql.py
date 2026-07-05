#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
老王论坛自动签到脚本 v6.0（青龙单文件版）
青龙单文件版 - DrissionPage + ddddocr

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
new Env('老王论坛签到-单文件版')
"""

import os
import re
import sys
import time
import random
import logging
import base64
import json
from typing import Optional
from datetime import datetime

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


class SliderSolver:
    """滑块缺口识别求解器"""

    def __init__(self, browser, ocr=None):
        """
        初始化求解器

        Args:
            browser: DrissionPage 浏览器实例
            ocr: ddddocr 实例（可选）
        """
        self.browser = browser
        self.ocr = ocr
        self.has_opencv = self._check_opencv()

    def _check_opencv(self) -> bool:
        """检查 OpenCV 是否可用"""
        try:
            import cv2
            return True
        except ImportError:
            logger.debug("OpenCV 未安装，跳过 OpenCV 识别")
            return False

    def extract_images(self) -> Optional[tuple[bytes, bytes]]:
        """
        提取背景图和完整图

        Returns:
            (bg_bytes, full_bytes) 或 None（提取失败时）
        """
        try:
            # 0. 确保背景 canvas 已绘制
            self.browser.run_js('''
            var t = window.tncode;
            if (t && t._draw_bg && !t._is_draw_bg) {
                try { t._draw_bg(); } catch(e) {}
            }
            ''')

            # 1. 从 Canvas 获取背景图（带缺口），裁成 tncode 自然图尺寸。
            # 直接导出 canvas 可能包含 CSS 放大后的尺寸，导致 ddddocr slide_comparison 尺寸不一致。
            bg_b64 = self.browser.run_js('''
            var canvas = document.querySelector('.tncode_canvas_bg');
            var t = window.tncode;
            if (!canvas) return null;
            var imgW = (t && t._img_w) || 240;
            var imgH = (t && t._img_h) || 150;
            var c = document.createElement('canvas');
            c.width = imgW;
            c.height = imgH;
            var ctx = c.getContext('2d');
            ctx.drawImage(canvas, 0, 0, imgW, imgH, 0, 0, imgW, imgH);
            return c.toDataURL("image/png").split(",")[1];
            ''')

            if not bg_b64:
                logger.debug("无法获取背景图")
                return None

            bg_bytes = base64.b64decode(bg_b64)

            # 2. 智能选行：获取完整图
            full_bytes = self._select_best_row(bg_bytes)

            if not full_bytes:
                logger.debug("无法获取完整图")
                return None

            return bg_bytes, full_bytes

        except Exception as e:
            logger.debug(f"提取图片失败: {e}")
            return None

    def _select_best_row(self, bg_bytes: bytes) -> Optional[bytes]:
        """
        智能选择精灵图中的完整图行

        tncode 精灵图布局：第 2 行（index 2）是完整图（无缺口）。
        优先返回第 2 行，失败则按 [2, 1, 0, 3] 顺序尝试。

        Args:
            bg_bytes: 背景图字节数据

        Returns:
            完整图的字节数据，失败返回 None
        """
        for row in [2, 1, 0, 3]:
            row_bytes = self._get_row_bytes(row)
            if row_bytes:
                return row_bytes

        return None

    def _calculate_difference(self, img1_bytes: bytes, img2_bytes: bytes) -> float:
        """
        计算两张图片的差异度（简化版）

        Args:
            img1_bytes: 图片1字节数据
            img2_bytes: 图片2字节数据

        Returns:
            差异度（越大越不同）
        """
        # 简化实现：比较字节差异
        min_len = min(len(img1_bytes), len(img2_bytes))
        if min_len == 0:
            return 0

        diff_count = sum(
            1 for i in range(0, min_len, 100)  # 采样比较
            if img1_bytes[i] != img2_bytes[i]
        )
        return diff_count / (min_len / 100)

    def _get_row_bytes(self, row: int) -> Optional[bytes]:
        """获取精灵图指定行的字节数据"""
        try:
            row_b64 = self.browser.run_js(f'''
            var t = window.tncode;
            var img = (t && t._img) || document.querySelector('.tncode_div img');
            if (!img || !img.complete) return null;
            var w = (t && t._img_w) || 240;
            var h = (t && t._img_h) || 150;
            var c = document.createElement('canvas');
            c.width = w; c.height = h;
            var ctx = c.getContext('2d');
            ctx.drawImage(img, 0, h * {row}, w, h, 0, 0, w, h);
            return c.toDataURL("image/png").split(",")[1];
            ''')

            if row_b64:
                return base64.b64decode(row_b64)
        except Exception as e:
            logger.debug(f"获取第{row}行失败: {e}")
        return None

    def solve_with_opencv(self, bg_bytes: bytes, full_bytes: bytes) -> int:
        """
        使用 OpenCV 识别缺口

        方法: Canny 边缘检测 + 模板匹配

        Args:
            bg_bytes: 背景图（带缺口）字节数据
            full_bytes: 完整图字节数据

        Returns:
            缺口 x 坐标，失败返回 -1
        """
        if not self.has_opencv:
            return -1

        try:
            import cv2
            import numpy as np

            # 解码图片
            bg_img = cv2.imdecode(
                np.frombuffer(bg_bytes, np.uint8),
                cv2.IMREAD_GRAYSCALE
            )
            full_img = cv2.imdecode(
                np.frombuffer(full_bytes, np.uint8),
                cv2.IMREAD_GRAYSCALE
            )

            if bg_img is None or full_img is None:
                return -1

            # Canny 边缘检测
            bg_edges = cv2.Canny(bg_img, 100, 200)
            full_edges = cv2.Canny(full_img, 100, 200)

            # 模板匹配
            result = cv2.matchTemplate(bg_edges, full_edges, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            # 置信度检查
            if max_val > 0.8:
                x = max_loc[0]
                if self.validate_position(x):
                    logger.info(f"🎯 OpenCV 识别缺口: {x}px (置信度: {max_val:.2f})")
                    return x

            logger.debug(f"OpenCV 识别置信度不足: {max_val:.2f}")
            return -1

        except Exception as e:
            logger.debug(f"OpenCV 识别失败: {e}")
            return -1

    def solve_with_ddddocr(self, bg_bytes: bytes, full_bytes: bytes) -> int:
        """
        使用 ddddocr 识别缺口

        Args:
            bg_bytes: 背景图（带缺口）字节数据
            full_bytes: 完整图字节数据

        Returns:
            缺口 x 坐标，失败返回 -1
        """
        if not self.ocr:
            return -1

        try:
            # ddddocr 官方说明：
            # slide_match() 用于“滑块小图 + 背景图”；
            # slide_comparison() 用于“带缺口背景图 + 完整背景图”。
            # tncode 这里提取到的是后者，不能把完整背景图当滑块小图传给 slide_match。
            if hasattr(self.ocr, 'slide_comparison'):
                result = self.ocr.slide_comparison(bg_bytes, full_bytes)
                if result and 'target' in result:
                    x = int(result['target'][0])
                    if self.validate_position(x):
                        logger.info(f"🎯 ddddocr 对比识别缺口: {x}px")
                        return x
                logger.debug(f"ddddocr slide_comparison 结果无效: {result}")

            if os.getenv('LAOWANG_USE_SLIDE_MATCH_FALLBACK', '').lower() != 'true':
                return -1

            result = self.ocr.slide_match(full_bytes, bg_bytes, simple_target=False)

            if result and 'target' in result:
                x = int(result['target'][0])
                if self.validate_position(x):
                    logger.info(f"🎯 ddddocr slide_match 识别缺口: {x}px")
                    return x

            logger.debug("ddddocr 识别结果无效")
            return -1

        except Exception as e:
            logger.debug(f"ddddocr 识别失败: {e}")
            return -1

    def solve_with_canvas(self) -> int:
        """
        使用 Canvas 像素比对识别缺口

        Returns:
            缺口 x 坐标，失败返回 -1
        """
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

            // 提取完整图（第三行）
            var tmpCanvas = document.createElement('canvas');
            tmpCanvas.width = imgW;
            tmpCanvas.height = imgH;
            var tmpCtx = tmpCanvas.getContext('2d');
            tmpCtx.drawImage(img, 0, imgH * 2, imgW, imgH, 0, 0, imgW, imgH);

            var bgData = bgCanvas.getContext('2d').getImageData(0, 0, imgW, imgH);
            var fullData = tmpCtx.getImageData(0, 0, imgW, imgH);

            // 计算差异
            var diffCounts = new Array(imgW).fill(0);
            var rows = [25, 40, 55, 70, 85, 100, 115, 130];
            for (var r = 0; r < rows.length; r++) {
                var y = rows[r];
                for (var x = 0; x < imgW; x++) {
                    var i = (y * imgW + x) * 4;
                    var diff = Math.abs(bgData.data[i] - fullData.data[i]) +
                               Math.abs(bgData.data[i+1] - fullData.data[i+1]) +
                               Math.abs(bgData.data[i+2] - fullData.data[i+2]);
                    if (diff > 30) diffCounts[x]++;
                }
            }

            // 滑动窗口找最佳位置
            var bestX = -1, bestSum = 0;
            for (var x = 0; x <= imgW - markW; x++) {
                var sum = 0;
                for (var w = 0; w < markW; w++) sum += diffCounts[x + w];
                if (sum > bestSum) { bestSum = sum; bestX = x; }
            }

            return (bestSum < rows.length * markW * 0.2) ? -3 : bestX;
            ''')

            if gap and gap > 5:
                logger.info(f"🎯 Canvas 识别缺口: {gap}px")
                return int(gap)

            logger.debug(f"Canvas 识别失败: {gap}")
            return -1

        except Exception as e:
            logger.debug(f"Canvas 比对失败: {e}")
            return -1

    def solve_with_canvas_candidates(self, limit: int = 3) -> list[int]:
        """使用 Canvas 像素比对返回多个候选缺口。"""
        try:
            data = self.browser.run_js(f'''
            var t = window.tncode;
            var bgCanvas = document.querySelector('.tncode_canvas_bg');
            if (!bgCanvas || bgCanvas.width === 0) return "[]";

            var img = (t && t._img) || document.querySelector('.tncode_div img');
            if (!img || !img.complete || img.naturalWidth === 0) return "[]";

            var imgW = (t && t._img_w) || 240;
            var imgH = (t && t._img_h) || 150;
            var markW = (t && t._mark_w) || 50;
            var maxOffset = imgW - markW;

            var tmpCanvas = document.createElement('canvas');
            tmpCanvas.width = imgW;
            tmpCanvas.height = imgH;
            var tmpCtx = tmpCanvas.getContext('2d');
            tmpCtx.drawImage(img, 0, imgH * 2, imgW, imgH, 0, 0, imgW, imgH);

            var bgData = bgCanvas.getContext('2d').getImageData(0, 0, imgW, imgH);
            var fullData = tmpCtx.getImageData(0, 0, imgW, imgH);

            var diffCounts = new Array(imgW).fill(0);
            var rows = [25, 40, 55, 70, 85, 100, 115, 130];
            for (var r = 0; r < rows.length; r++) {{
                var y = rows[r];
                for (var x = 0; x < imgW; x++) {{
                    var i = (y * imgW + x) * 4;
                    var diff = Math.abs(bgData.data[i] - fullData.data[i]) +
                               Math.abs(bgData.data[i+1] - fullData.data[i+1]) +
                               Math.abs(bgData.data[i+2] - fullData.data[i+2]);
                    if (diff > 30) diffCounts[x]++;
                }}
            }}

            var scores = [];
            for (var x = 0; x <= maxOffset; x++) {{
                var sum = 0;
                for (var w = 0; w < markW; w++) sum += diffCounts[x + w];
                scores.push({{x: x, score: sum}});
            }}

            scores.sort(function(a, b) {{ return b.score - a.score; }});
            var minScore = rows.length * markW * 0.2;
            var selected = [];
            for (var i = 0; i < scores.length && selected.length < {limit}; i++) {{
                if (scores[i].score < minScore) break;
                var farEnough = true;
                for (var j = 0; j < selected.length; j++) {{
                    if (Math.abs(scores[i].x - selected[j].x) < Math.max(24, markW * 0.55)) {{
                        farEnough = false;
                        break;
                    }}
                }}
                if (farEnough) selected.push(scores[i]);
            }}

            return JSON.stringify(selected);
            ''')

            raw = json.loads(data) if isinstance(data, str) else data
            candidates = []
            for item in raw or []:
                x = int(item.get('x', -1))
                if self.validate_position(x):
                    candidates.append(x)

            if candidates:
                logger.info(f"🎯 Canvas 候选缺口: {candidates}")
            else:
                logger.debug(f"Canvas 候选为空: {data}")
            return candidates

        except Exception as e:
            logger.debug(f"Canvas 候选识别失败: {e}")
            return []

    def solve_candidates(self, max_candidates: int = 3) -> list[int]:
        """返回多个去重后的候选缺口位置。"""
        images = self.extract_images()
        if not images:
            logger.warning("无法提取图片，跳过候选识别")
            return []

        bg_bytes, full_bytes = images
        logger.debug(f"候选图片提取完成: bg={len(bg_bytes)}b, full={len(full_bytes)}b")

        candidates = []

        x = self.solve_with_ddddocr(bg_bytes, full_bytes)
        if self.validate_position(x):
            candidates.append(x)

        for x in self.solve_with_canvas_candidates(limit=max_candidates):
            if all(abs(x - old) > 5 for old in candidates):
                candidates.append(x)

        x = self._solve_once(bg_bytes, full_bytes)
        if self.validate_position(x) and all(abs(x - old) > 5 for old in candidates):
            candidates.append(x)

        candidates = candidates[:max_candidates]
        if candidates:
            logger.info(f"✅ 最终候选缺口: {candidates}")
        else:
            logger.warning("所有候选识别方法均失败")
        return candidates

    def solve(self, max_attempts: int = 5) -> int:
        """
        主识别入口，自动降级 + 多次识别取中位数

        Args:
            max_attempts: 最大重试次数

        Returns:
            缺口 x 坐标，失败返回 -1
        """
        # 1. 提取图片
        logger.debug("提取图片...")
        images = self.extract_images()
        if not images:
            logger.warning("无法提取图片，跳过识别")
            return -1

        bg_bytes, full_bytes = images
        logger.debug(f"图片提取完成: bg={len(bg_bytes)}b, full={len(full_bytes)}b")

        # 2. 多次识别取中位数
        results = []

        for attempt in range(3):
            logger.debug(f"识别尝试 {attempt + 1}/3...")
            x = self._solve_once(bg_bytes, full_bytes)
            if self.validate_position(x):
                results.append(x)
                logger.debug(f"第 {attempt + 1} 次识别: {x}px")

        if not results:
            logger.warning("所有识别方法均失败")
            return -1

        # 3. 取中位数
        results.sort()
        median = results[len(results) // 2]
        logger.info(f"✅ 最终识别结果: {median}px (共 {len(results)} 次有效识别)")

        return median

    def _solve_once(self, bg_bytes: bytes, full_bytes: bytes) -> int:
        """
        单次识别尝试，按优先级调用各引擎

        Args:
            bg_bytes: 背景图字节数据
            full_bytes: 完整图字节数据

        Returns:
            缺口 x 坐标，失败返回 -1
        """
        # 优先级 1: OpenCV
        if self.has_opencv:
            x = self.solve_with_opencv(bg_bytes, full_bytes)
            if self.validate_position(x):
                return x

        # 优先级 2: Canvas 像素比对。tncode 场景中完整图和缺口图同尺寸，
        # 比 ddddocr 的通用滑块匹配更稳定。
        x = self.solve_with_canvas()
        if self.validate_position(x):
            return x

        # 优先级 3: ddddocr
        if self.ocr:
            x = self.solve_with_ddddocr(bg_bytes, full_bytes)
            if self.validate_position(x):
                return x

        return -1

    def validate_position(self, x: int) -> bool:
        """
        校验识别位置是否合理

        Args:
            x: 识别的 x 坐标

        Returns:
            是否在合理范围内 (10-230px)
        """
        return 10 < x < 230

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
                # Linux / 青龙
                '/usr/bin/chromium',
                '/usr/bin/chromium-browser',
                '/usr/bin/google-chrome',
                '/opt/google/chrome/google-chrome',
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
