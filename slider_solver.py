"""滑块缺口识别求解器 - 混合方案"""

import os
import sys
import base64
import logging
from typing import Optional

# Windows 控制台 UTF-8
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

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
            # 1. 从 Canvas 获取背景图（带缺口）
            bg_b64 = self.browser.run_js('''
            var canvas = document.querySelector('.tncode_canvas_bg');
            return canvas ? canvas.toDataURL("image/png").split(",")[1] : null;
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
        智能选择精灵图中最可能的行

        分析4行图片与背景图的差异度，选差异最大的行

        Args:
            bg_bytes: 背景图字节数据

        Returns:
            最佳行的图片字节数据，失败返回 None
        """
        try:
            best_diff = -1
            best_bytes = None

            for row in range(4):
                # 提取该行图片
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

                if not row_b64:
                    continue

                row_bytes = base64.b64decode(row_b64)

                # 计算与背景图的差异度
                diff = self._calculate_difference(bg_bytes, row_bytes)

                if diff > best_diff:
                    best_diff = diff
                    best_bytes = row_bytes

            return best_bytes

        except Exception as e:
            logger.debug(f"智能选行失败: {e}")
            # 降级：返回第一行
            return self._get_row_bytes(0)

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
            result = self.ocr.slide_match(
                full_bytes,
                bg_bytes,
                simple_target=False
            )

            if result and 'target' in result:
                x = int(result['target'][0])
                if self.validate_position(x):
                    logger.info(f"🎯 ddddocr 识别缺口: {x}px")
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

    def solve(self, max_attempts: int = 5) -> int:
        """
        主识别入口，自动降级 + 多次识别取中位数

        Args:
            max_attempts: 最大重试次数

        Returns:
            缺口 x 坐标，失败返回 -1
        """
        # 1. 提取图片
        images = self.extract_images()
        if not images:
            logger.warning("无法提取图片，跳过识别")
            return -1

        bg_bytes, full_bytes = images

        # 2. 多次识别取中位数
        results = []

        for attempt in range(3):
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

        # 优先级 2: ddddocr
        if self.ocr:
            x = self.solve_with_ddddocr(bg_bytes, full_bytes)
            if self.validate_position(x):
                return x

        # 优先级 3: Canvas
        x = self.solve_with_canvas()
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
