"""SliderSolver 单元测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestValidatePosition:
    """测试位置校验逻辑"""

    def test_position_in_valid_range(self):
        """有效范围内的位置应返回 True"""
        from slider_solver import SliderSolver
        solver = SliderSolver(browser=Mock())
        assert solver.validate_position(100) == True
        assert solver.validate_position(50) == True
        assert solver.validate_position(200) == True

    def test_position_too_small(self):
        """小于等于 10px 应返回 False"""
        from slider_solver import SliderSolver
        solver = SliderSolver(browser=Mock())
        assert solver.validate_position(5) == False
        assert solver.validate_position(10) == False
        assert solver.validate_position(0) == False

    def test_position_too_large(self):
        """大于等于 230px 应返回 False"""
        from slider_solver import SliderSolver
        solver = SliderSolver(browser=Mock())
        assert solver.validate_position(230) == False
        assert solver.validate_position(240) == False
        assert solver.validate_position(300) == False


class TestExtractImages:
    """测试图片提取逻辑"""

    def test_extract_images_returns_bytes(self):
        """应返回两个 bytes 对象"""
        from slider_solver import SliderSolver

        # Mock browser.run_js 返回 base64 编码的图片
        mock_browser = Mock()
        mock_browser.run_js.return_value = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        solver = SliderSolver(browser=mock_browser)
        bg_bytes, full_bytes = solver.extract_images()

        assert isinstance(bg_bytes, bytes)
        assert isinstance(full_bytes, bytes)
        assert len(bg_bytes) > 0
        assert len(full_bytes) > 0

    def test_extract_images_returns_none_on_failure(self):
        """浏览器返回 None 时应返回 None"""
        from slider_solver import SliderSolver

        mock_browser = Mock()
        mock_browser.run_js.return_value = None

        solver = SliderSolver(browser=mock_browser)
        result = solver.extract_images()

        assert result is None


class TestSolveWithOpencv:
    """测试 OpenCV 识别"""

    @patch('slider_solver.SliderSolver._check_opencv', return_value=True)
    def test_solve_with_opencv_returns_position(self, mock_check):
        """OpenCV 识别成功应返回位置"""
        from slider_solver import SliderSolver
        import numpy as np
        import cv2

        np.random.seed(42)
        h, w = 150, 240

        # 创建有丰富纹理的背景（随机矩形提供边缘特征）
        bg_gray = np.zeros((h, w), dtype=np.uint8)
        for _ in range(50):
            x = np.random.randint(0, w - 30)
            y = np.random.randint(0, h - 30)
            color = np.random.randint(50, 255)
            rw = np.random.randint(10, 30)
            rh = np.random.randint(10, 30)
            cv2.rectangle(bg_gray, (x, y), (x + rw, y + rh), int(color), -1)

        # 缺口位置
        gap_x, gap_w = 120, 40

        # 带缺口的背景：缺口区域变暗（保留部分原始内容）
        bg_with_gap = bg_gray.copy()
        bg_with_gap[:, gap_x:gap_x + gap_w] = (
            bg_gray[:, gap_x:gap_x + gap_w].astype(float) * 0.4 + 20
        ).astype(np.uint8)

        # 拼图块：缺口位置的原始内容
        puzzle_piece = bg_gray[:, gap_x:gap_x + gap_w].copy()

        # 编码为 PNG 字节
        _, bg_bytes = cv2.imencode('.png', cv2.cvtColor(bg_with_gap, cv2.COLOR_GRAY2BGR))
        _, full_bytes = cv2.imencode('.png', cv2.cvtColor(puzzle_piece, cv2.COLOR_GRAY2BGR))

        mock_browser = Mock()
        solver = SliderSolver(browser=mock_browser)
        solver.has_opencv = True

        result = solver.solve_with_opencv(bg_bytes.tobytes(), full_bytes.tobytes())

        assert result > 0
        assert solver.validate_position(result)

    def test_solve_with_opencv_returns_minus1_without_opencv(self):
        """没有 OpenCV 时应返回 -1"""
        from slider_solver import SliderSolver

        mock_browser = Mock()
        solver = SliderSolver(browser=mock_browser)
        solver.has_opencv = False

        result = solver.solve_with_opencv(b'', b'')
        assert result == -1
