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
