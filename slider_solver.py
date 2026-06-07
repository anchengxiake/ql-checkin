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

    def validate_position(self, x: int) -> bool:
        """
        校验识别位置是否合理

        Args:
            x: 识别的 x 坐标

        Returns:
            是否在合理范围内 (10-230px)
        """
        return 10 < x < 230
