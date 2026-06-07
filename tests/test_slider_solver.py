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
