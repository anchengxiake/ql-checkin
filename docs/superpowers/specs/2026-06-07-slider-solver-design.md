# 滑块识别混合方案设计文档

**日期**: 2026-06-07
**状态**: 已批准
**目标**: 提升滑块验证码识别成功率

---

## 1. 问题分析

### 当前问题
- 滑块缺口识别不稳定，有时准有时不准
- ddddocr 识别受图片质量影响大
- Canvas 像素比对阈值固定，适应性差
- 精灵图行序不确定（4行），按固定顺序尝试效率低

### 根本原因
1. 单一识别引擎，无法互相验证
2. 图片提取逻辑不够智能
3. 缺少结果校验和异常处理

---

## 2. 解决方案

### 2.1 整体架构

采用**混合识别方案**，建立多引擎识别链，自动降级：

```
OpenCV (首选) → ddddocr (次选) → Canvas (兜底) → 刷新重试
```

### 2.2 核心类设计

```python
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
            return False

    def extract_images(self) -> tuple[bytes, bytes]:
        """
        提取背景图和完整图

        Returns:
            (bg_bytes, full_bytes): 背景图（带缺口）和完整图的字节数据
        """
        # 1. 从 Canvas 获取背景图
        # 2. 从精灵图提取完整图（智能选行）
        pass

    def _select_best_row(self, bg_bytes: bytes) -> bytes:
        """
        智能选择精灵图中最可能的行

        分析4行图片与背景图的差异度，选差异最大的行
        """
        pass

    def solve_with_opencv(self, bg_bytes: bytes, full_bytes: bytes) -> int:
        """
        使用 OpenCV 识别缺口

        方法: Canny 边缘检测 + 模板匹配

        Returns:
            缺口 x 坐标，失败返回 -1
        """
        pass

    def solve_with_ddddocr(self, bg_bytes: bytes, full_bytes: bytes) -> int:
        """
        使用 ddddocr 识别缺口

        Returns:
            缺口 x 坐标，失败返回 -1
        """
        pass

    def solve_with_canvas(self) -> int:
        """
        使用 Canvas 像素比对识别缺口

        Returns:
            缺口 x 坐标，失败返回 -1
        """
        pass

    def validate_position(self, x: int) -> bool:
        """
        校验识别位置是否合理

        Args:
            x: 识别的 x 坐标

        Returns:
            是否在合理范围内 (10-230px)
        """
        return 10 < x < 230

    def solve(self) -> int:
        """
        主识别入口，自动降级

        流程:
        1. 提取图片
        2. 尝试 OpenCV（有依赖时）
        3. 尝试 ddddocr（有依赖时）
        4. 尝试 Canvas
        5. 多次识别取中位数

        Returns:
            缺口 x 坐标，失败返回 -1
        """
        pass
```

### 2.3 识别流程详解

#### 第1步：提取图片
```python
def extract_images(self):
    # 1. 从 Canvas 获取背景图（带缺口）
    bg_b64 = self.browser.run_js('''
    var canvas = document.querySelector('.tncode_canvas_bg');
    return canvas ? canvas.toDataURL("image/png").split(",")[1] : null;
    ''')

    # 2. 智能选行：分析4行图片与背景图的差异度
    best_row = self._select_best_row(base64.b64decode(bg_b64))

    return bg_bytes, best_row
```

#### 第2步：智能选行
```python
def _select_best_row(self, bg_bytes):
    """分析精灵图4行，选差异最大的行"""
    differences = []

    for row in range(4):
        # 提取该行图片
        row_b64 = self.browser.run_js(f'''
        var t = window.tncode;
        var img = (t && t._img) || document.querySelector('.tncode_div img');
        var w = (t && t._img_w) || 240;
        var h = (t && t._img_h) || 150;
        var c = document.createElement('canvas');
        c.width = w; c.height = h;
        var ctx = c.getContext('2d');
        ctx.drawImage(img, 0, h * {row}, w, h, 0, 0, w, h);
        return c.toDataURL("image/png").split(",")[1];
        ''')

        # 计算与背景图的差异度
        diff = self._calculate_difference(bg_bytes, base64.b64decode(row_b64))
        differences.append((diff, row))

    # 选差异最大的行
    best_row = max(differences, key=lambda x: x[0])[1]
    return best_row
```

#### 第3步：OpenCV 识别
```python
def solve_with_opencv(self, bg_bytes, full_bytes):
    """Canny 边缘检测 + 模板匹配"""
    import cv2
    import numpy as np

    # 解码图片
    bg_img = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    full_img = cv2.imdecode(np.frombuffer(full_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)

    # Canny 边缘检测
    bg_edges = cv2.Canny(bg_img, 100, 200)
    full_edges = cv2.Canny(full_img, 100, 200)

    # 模板匹配
    result = cv2.matchTemplate(bg_edges, full_edges, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    # 置信度检查
    if max_val > 0.8:
        return max_loc[0]

    return -1
```

#### 第4步：结果校验
```python
def solve(self):
    """主入口：多次识别取中位数"""
    results = []

    for _ in range(3):
        x = self._solve_once()
        if self.validate_position(x):
            results.append(x)

    if not results:
        return -1

    # 取中位数
    results.sort()
    return results[len(results) // 2]
```

---

## 3. 依赖管理

### 必需依赖
```
DrissionPage>=1.0.0
```

### 推荐依赖
```
ddddocr>=1.4.0
```

### 可选依赖
```
opencv-python>=4.5.0
```

### 优雅降级逻辑
```python
def _check_opencv(self):
    try:
        import cv2
        return True
    except ImportError:
        logger.info("OpenCV 未安装，跳过 OpenCV 识别")
        return False
```

---

## 4. 集成方案

### 4.1 修改 laowang_sign.py

将现有的 `find_gap_with_ocr` 和 `find_gap_with_canvas` 方法替换为 `SliderSolver`：

```python
# 原来的代码
gap = self.find_gap_with_ocr()
if gap < 0:
    gap = self.find_gap_with_canvas()

# 改为
solver = SliderSolver(self.browser, self.ocr)
gap = solver.solve()
```

### 4.2 文件结构

```
ql-checkin/
├── slider_solver.py      # 新增：滑块识别模块
├── laowang_sign.py       # 修改：调用 SliderSolver
├── laowang_v8.py         # 修改：调用 SliderSolver
└── ...
```

---

## 5. 测试计划

### 5.1 单元测试
- 测试 `validate_position` 边界条件
- 测试 `_select_best_row` 逻辑
- 测试各识别方法的返回值

### 5.2 集成测试
- 本地运行脚本，观察识别成功率
- 测试缺少不同依赖时的降级行为

### 5.3 性能指标
- 目标识别成功率：> 90%
- 单次识别时间：< 3 秒
- 最大重试次数：5 次

---

## 6. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| OpenCV 安装失败 | 无法使用最精准的识别 | 自动降级到 ddddocr |
| 精灵图结构变化 | 智能选行逻辑失效 | 保留固定行序作为兜底 |
| 网站更新验证机制 | 滑块逻辑变化 | 保持代码可维护性 |

---

## 7. 后续优化方向

1. **机器学习模型训练** - 用历史成功数据训练专用模型
2. **云端识别服务** - 接入第三方验证码识别 API
3. **自适应阈值** - 根据图片特征动态调整识别参数
