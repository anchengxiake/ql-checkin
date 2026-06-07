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

    def validate_position(self, x: int) -> bool:
        """
        校验识别位置是否合理

        Args:
            x: 识别的 x 坐标

        Returns:
            是否在合理范围内 (10-230px)
        """
        return 10 < x < 230
