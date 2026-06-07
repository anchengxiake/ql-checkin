# 滑块识别混合方案实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现多引擎滑块缺口识别系统，提升验证码识别成功率到 90% 以上

**Architecture:** 创建独立的 `SliderSolver` 类，支持 OpenCV、ddddocr、Canvas 三种识别引擎，自动降级并取中位数结果

**Tech Stack:** Python 3.8+, DrissionPage, ddddocr (可选), opencv-python (可选)

---

## 文件结构

```
ql-checkin/
├── slider_solver.py           # 新建：滑块识别核心模块
├── tests/
│   └── test_slider_solver.py  # 新建：单元测试
├── laowang_sign.py            # 修改：集成 SliderSolver
└── requirements.txt           # 修改：添加 opencv-python 可选依赖
```

---

## Task 1: 创建项目测试框架

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_slider_solver.py`

- [ ] **Step 1: 创建 tests 目录和 __init__.py**

```bash
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 2: 创建测试文件骨架**

```python
# tests/test_slider_solver.py
"""SliderSolver 单元测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestValidatePosition:
    """测试位置校验逻辑"""

    def test_position_in_valid_range(self):
        """有效范围内的位置应返回 True"""
        # 将在后续步骤实现
        pass

    def test_position_too_small(self):
        """小于 10px 应返回 False"""
        pass

    def test_position_too_large(self):
        """大于 230px 应返回 False"""
        pass
```

- [ ] **Step 3: 运行测试确认框架正常**

```bash
python -m pytest tests/test_slider_solver.py -v
```

Expected: 3 tests collected, 3 passed (因为 pass 语句)

- [ ] **Step 4: 提交**

```bash
git add tests/
git commit -m "test: 初始化测试框架"
```

---

## Task 2: 实现 validate_position 方法

**Files:**
- Create: `slider_solver.py`
- Modify: `tests/test_slider_solver.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_slider_solver.py
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_slider_solver.py::TestValidatePosition -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'slider_solver'"

- [ ] **Step 3: 实现 SliderSolver 基础类和 validate_position**

```python
# slider_solver.py
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_slider_solver.py::TestValidatePosition -v
```

Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add slider_solver.py tests/test_slider_solver.py
git commit -m "feat: 实现 SliderSolver 基础类和 validate_position"
```

---

## Task 3: 实现 extract_images 方法

**Files:**
- Modify: `slider_solver.py`
- Modify: `tests/test_slider_solver.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_slider_solver.py - 在文件末尾添加

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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_slider_solver.py::TestExtractImages -v
```

Expected: FAIL with "AttributeError: 'SliderSolver' object has no attribute 'extract_images'"

- [ ] **Step 3: 实现 extract_images 方法**

```python
# slider_solver.py - 在 SliderSolver 类中添加

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
        # 实际应用中可用 PIL 或 OpenCV 计算像素差异
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_slider_solver.py::TestExtractImages -v
```

Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add slider_solver.py tests/test_slider_solver.py
git commit -m "feat: 实现 extract_images 和智能选行逻辑"
```

---

## Task 4: 实现 solve_with_opencv 方法

**Files:**
- Modify: `slider_solver.py`
- Modify: `tests/test_slider_solver.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_slider_solver.py - 在文件末尾添加

class TestSolveWithOpencv:
    """测试 OpenCV 识别"""

    @patch('slider_solver.SliderSolver._check_opencv', return_value=True)
    def test_solve_with_opencv_returns_position(self, mock_check):
        """OpenCV 识别成功应返回位置"""
        from slider_solver import SliderSolver

        # 创建测试图片（模拟）
        import numpy as np
        import cv2

        # 创建背景图（带缺口）
        bg_img = np.zeros((150, 240, 3), dtype=np.uint8)
        bg_img[:, 100:150] = 255  # 缺口区域

        # 创建完整图
        full_img = np.zeros((150, 240, 3), dtype=np.uint8)

        _, bg_bytes = cv2.imencode('.png', bg_img)
        _, full_bytes = cv2.imencode('.png', full_img)

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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_slider_solver.py::TestSolveWithOpencv -v
```

Expected: FAIL with "AttributeError: 'SliderSolver' object has no attribute 'solve_with_opencv'"

- [ ] **Step 3: 实现 solve_with_opencv 方法**

```python
# slider_solver.py - 在 SliderSolver 类中添加

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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_slider_solver.py::TestSolveWithOpencv -v
```

Expected: 2 passed (如果安装了 opencv-python)

- [ ] **Step 5: 提交**

```bash
git add slider_solver.py tests/test_slider_solver.py
git commit -m "feat: 实现 solve_with_opencv 识别方法"
```

---

## Task 5: 实现 solve_with_ddddocr 方法

**Files:**
- Modify: `slider_solver.py`
- Modify: `tests/test_slider_solver.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_slider_solver.py - 在文件末尾添加

class TestSolveWithDdddocr:
    """测试 ddddocr 识别"""

    def test_solve_with_ddddocr_returns_position(self):
        """ddddocr 识别成功应返回位置"""
        from slider_solver import SliderSolver

        # Mock ocr 对象
        mock_ocr = Mock()
        mock_ocr.slide_match.return_value = {'target': [120, 50]}

        mock_browser = Mock()
        solver = SliderSolver(browser=mock_browser, ocr=mock_ocr)

        # 创建简单的测试图片
        bg_bytes = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        full_bytes = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100

        result = solver.solve_with_ddddocr(bg_bytes, full_bytes)

        assert result == 120
        mock_ocr.slide_match.assert_called_once()

    def test_solve_with_ddddocr_returns_minus1_without_ocr(self):
        """没有 ocr 时应返回 -1"""
        from slider_solver import SliderSolver

        mock_browser = Mock()
        solver = SliderSolver(browser=mock_browser, ocr=None)

        result = solver.solve_with_ddddocr(b'', b'')
        assert result == -1

    def test_solve_with_ddddocr_returns_minus1_on_failure(self):
        """识别失败应返回 -1"""
        from slider_solver import SliderSolver

        mock_ocr = Mock()
        mock_ocr.slide_match.return_value = None

        mock_browser = Mock()
        solver = SliderSolver(browser=mock_browser, ocr=mock_ocr)

        result = solver.solve_with_ddddocr(b'\x00' * 100, b'\x00' * 100)
        assert result == -1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_slider_solver.py::TestSolveWithDdddocr -v
```

Expected: FAIL with "AttributeError: 'SliderSolver' object has no attribute 'solve_with_ddddocr'"

- [ ] **Step 3: 实现 solve_with_ddddocr 方法**

```python
# slider_solver.py - 在 SliderSolver 类中添加

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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_slider_solver.py::TestSolveWithDdddocr -v
```

Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add slider_solver.py tests/test_slider_solver.py
git commit -m "feat: 实现 solve_with_ddddocr 识别方法"
```

---

## Task 6: 实现 solve_with_canvas 方法

**Files:**
- Modify: `slider_solver.py`
- Modify: `tests/test_slider_solver.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_slider_solver.py - 在文件末尾添加

class TestSolveWithCanvas:
    """测试 Canvas 像素比对识别"""

    def test_solve_with_canvas_returns_position(self):
        """Canvas 识别成功应返回位置"""
        from slider_solver import SliderSolver

        mock_browser = Mock()
        mock_browser.run_js.return_value = 120

        solver = SliderSolver(browser=mock_browser)
        result = solver.solve_with_canvas()

        assert result == 120

    def test_solve_with_canvas_returns_minus1_on_failure(self):
        """识别失败应返回 -1"""
        from slider_solver import SliderSolver

        mock_browser = Mock()
        mock_browser.run_js.return_value = -1

        solver = SliderSolver(browser=mock_browser)
        result = solver.solve_with_canvas()

        assert result == -1

    def test_solve_with_canvas_returns_minus1_on_exception(self):
        """异常时应返回 -1"""
        from slider_solver import SliderSolver

        mock_browser = Mock()
        mock_browser.run_js.side_effect = Exception("JS error")

        solver = SliderSolver(browser=mock_browser)
        result = solver.solve_with_canvas()

        assert result == -1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_slider_solver.py::TestSolveWithCanvas -v
```

Expected: FAIL with "AttributeError: 'SliderSolver' object has no attribute 'solve_with_canvas'"

- [ ] **Step 3: 实现 solve_with_canvas 方法**

```python
# slider_solver.py - 在 SliderSolver 类中添加

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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_slider_solver.py::TestSolveWithCanvas -v
```

Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add slider_solver.py tests/test_slider_solver.py
git commit -m "feat: 实现 solve_with_canvas 识别方法"
```

---

## Task 7: 实现 solve 主方法（自动降级 + 中位数）

**Files:**
- Modify: `slider_solver.py`
- Modify: `tests/test_slider_solver.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_slider_solver.py - 在文件末尾添加

class TestSolve:
    """测试主识别方法"""

    def test_solve_returns_median(self):
        """应返回多次识别的中位数"""
        from slider_solver import SliderSolver

        mock_browser = Mock()
        mock_browser.run_js.return_value = "fake_base64"

        solver = SliderSolver(browser=mock_browser)

        # Mock 各识别方法返回不同值
        with patch.object(solver, 'extract_images', return_value=(b'bg', b'full')):
            with patch.object(solver, 'solve_with_opencv', side_effect=[100, 110, 105]):
                with patch.object(solver, 'solve_with_ddddocr', return_value=-1):
                    with patch.object(solver, 'solve_with_canvas', return_value=-1):
                        result = solver.solve()

        # 中位数应该是 105
        assert result == 105

    def test_solve_returns_minus1_when_all_fail(self):
        """所有方法都失败时应返回 -1"""
        from slider_solver import SliderSolver

        mock_browser = Mock()
        solver = SliderSolver(browser=mock_browser)

        with patch.object(solver, 'extract_images', return_value=(b'bg', b'full')):
            with patch.object(solver, 'solve_with_opencv', return_value=-1):
                with patch.object(solver, 'solve_with_ddddocr', return_value=-1):
                    with patch.object(solver, 'solve_with_canvas', return_value=-1):
                        result = solver.solve()

        assert result == -1

    def test_solve_skips_opencv_when_unavailable(self):
        """没有 OpenCV 时应跳过"""
        from slider_solver import SliderSolver

        mock_browser = Mock()
        solver = SliderSolver(browser=mock_browser)
        solver.has_opencv = False

        with patch.object(solver, 'extract_images', return_value=(b'bg', b'full')):
            with patch.object(solver, 'solve_with_ddddocr', side_effect=[-1, -1, -1]):
                with patch.object(solver, 'solve_with_canvas', side_effect=[120, 115, 118]):
                    result = solver.solve()

        assert result == 118
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_slider_solver.py::TestSolve -v
```

Expected: FAIL with "AttributeError: 'SliderSolver' object has no attribute 'solve'"

- [ ] **Step 3: 实现 solve 主方法**

```python
# slider_solver.py - 在 SliderSolver 类中添加

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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_slider_solver.py::TestSolve -v
```

Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add slider_solver.py tests/test_slider_solver.py
git commit -m "feat: 实现 solve 主方法（自动降级 + 中位数）"
```

---

## Task 8: 集成到 laowang_sign.py

**Files:**
- Modify: `laowang_sign.py`

- [ ] **Step 1: 添加 import**

在 `laowang_sign.py` 文件顶部添加：

```python
from slider_solver import SliderSolver
```

- [ ] **Step 2: 修改 solve_slider 方法**

找到 `solve_slider` 方法，将：

```python
    def solve_slider(self, max_attempts=5):
        """破解滑块验证"""
        logger.info("🤖 开始破解滑块验证...")

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

            # 识别缺口
            gap = self.find_gap_with_ocr()
            if gap < 0:
                gap = self.find_gap_with_canvas()

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
```

改为：

```python
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
```

- [ ] **Step 3: 删除旧的识别方法**

删除 `find_gap_with_ocr` 和 `find_gap_with_canvas` 方法（约 110 行代码）

- [ ] **Step 4: 运行测试确认集成正常**

```bash
python -c "from laowang_sign import LaowangSigner; print('Import OK')"
```

Expected: "Import OK"

- [ ] **Step 5: 提交**

```bash
git add laowang_sign.py
git commit -m "refactor: 集成 SliderSolver 到 laowang_sign.py"
```

---

## Task 9: 更新 requirements.txt

**Files:**
- Create/Modify: `requirements.txt`

- [ ] **Step 1: 创建 requirements.txt**

```txt
# requirements.txt

# 必需依赖
DrissionPage>=1.0.0

# 推荐依赖（滑块识别）
ddddocr>=1.4.0

# 可选依赖（更精准的滑块识别）
# opencv-python>=4.5.0

# 环境变量管理
python-dotenv>=1.0.0
```

- [ ] **Step 2: 提交**

```bash
git add requirements.txt
git commit -m "docs: 添加 requirements.txt"
```

---

## Task 10: 运行完整测试套件

**Files:**
- None (验证步骤)

- [ ] **Step 1: 运行所有测试**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: All tests passed

- [ ] **Step 2: 检查代码覆盖率（可选）**

```bash
pip install pytest-cov
python -m pytest tests/ --cov=slider_solver --cov-report=term-missing
```

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat: 完成滑块识别混合方案实现"
```

---

## 自检清单

- [x] 所有任务都有完整的代码示例
- [x] 所有测试都有明确的预期结果
- [x] 文件路径都是精确的
- [x] 没有 TBD/TODO 占位符
- [x] 类型和方法签名一致
- [x] 测试覆盖所有边界条件
