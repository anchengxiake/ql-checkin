#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cron: 0 9 * * *
new Env('雨云签到')

雨云签到青龙单文件版。

环境变量:
  RAINYUN_ACCOUNT=[["账号","密码","false",""],["账号2","密码2","true","API Key"]]
  RAINYUN_CONFIG={"captcha_retry_limit":10,"renew_threshold_days":3}

上游:
  https://github.com/LMTXQ/Rainyun-QingLong
"""

import ast
import json
import logging
import os
import random
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


logging.basicConfig(
    level=logging.DEBUG if os.getenv("RAINYUN_DEBUG", "").lower() == "true" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


try:
    from notify import send as notify_send
except ImportError:
    notify_send = None


DEFAULT_CONFIG = {
    "timeout": 20,
    "captcha_wait": 6,
    "max_delay": 5,
    "captcha_retry_limit": 10,
    "similarity_threshold": 0.4,
    "download_max_retries": 3,
    "download_retry_delay": 2,
    "download_timeout": 10,
    "api_base_url": "https://api.v2.rainyun.com",
    "api_request_timeout": 10,
    "api_max_retries": 3,
    "api_retry_delay": 2,
    "renew_days": 7,
    "renew_threshold_days": 3,
    "min_points_reserve": 5000,
    "points_to_cny_rate": 2000,
    "account_interval_min": 3,
    "account_interval_max": 6,
    "headless": True,
    "keep_debug_files": False,
}

STEALTH_JS = r"""
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
  window.navigator.permissions.query = (parameters) => (
    parameters && parameters.name === 'notifications'
      ? Promise.resolve({state: Notification.permission})
      : originalQuery(parameters)
  );
}
"""


class RainyunAPIError(Exception):
    """雨云 API 异常。"""


class CaptchaRetryableError(Exception):
    """可重试的验证码异常。"""


@dataclass
class Account:
    username: str
    password: str
    auto_renew: bool = False
    api_key: str = ""


@dataclass
class AccountResult:
    username: str
    login_success: bool = False
    sign_in_success: bool = False
    points_before: int = 0
    points_after: int = 0
    points_earned: int = 0
    auto_renew_enabled: bool = False
    renew_summary: str = ""
    error_msg: str = ""

    def is_success(self) -> bool:
        return self.login_success and self.sign_in_success


@dataclass
class RuntimeContext:
    driver: object
    wait: object
    ocr: object
    det: object
    temp_dir: str
    config: dict

    def temp_path(self, filename: str) -> str:
        return os.path.join(self.temp_dir, filename)


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    logger.warning("环境变量 %s=%r 不是有效布尔值，使用默认值 %s", name, value, default)
    return default


def env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("环境变量 %s=%r 不是整数，使用默认值 %s", name, value, default)
        return default


def mask_account(value: str) -> str:
    value = str(value or "")
    if "@" in value:
        local, domain = value.split("@", 1)
        if len(local) <= 2:
            return "*" * len(local) + "@" + domain
        return local[:2] + "***@" + domain
    if len(value) <= 6:
        return value[:1] + "***"
    return value[:3] + "****" + value[-4:]


def load_config() -> dict:
    raw = os.getenv("RAINYUN_CONFIG", "").strip()
    config = DEFAULT_CONFIG.copy()
    if raw:
        try:
            user_config = json.loads(raw)
            if not isinstance(user_config, dict):
                raise ValueError("RAINYUN_CONFIG 必须是 JSON 对象")
            config.update(user_config)
        except Exception as exc:
            logger.warning("RAINYUN_CONFIG 解析失败，使用默认配置: %s", exc)

    config["headless"] = env_bool("RAINYUN_HEADLESS", bool(config.get("headless", True)))
    if os.getenv("RAINYUN_TIMEOUT"):
        config["timeout"] = env_int("RAINYUN_TIMEOUT", int(config["timeout"]))
    if os.getenv("RAINYUN_CAPTCHA_RETRY_LIMIT"):
        config["captcha_retry_limit"] = env_int(
            "RAINYUN_CAPTCHA_RETRY_LIMIT",
            int(config["captcha_retry_limit"]),
        )

    logger.info("配置: 页面超时=%ss, 验证码重试=%s, 相似度阈值=%s",
                config["timeout"], config["captcha_retry_limit"], config["similarity_threshold"])
    logger.info("配置: 续费天数=%s, 触发阈值=%s天, 保留积分=%s",
                config["renew_days"], config["renew_threshold_days"], config["min_points_reserve"])
    return config


def parse_accounts() -> List[Account]:
    raw = os.getenv("RAINYUN_ACCOUNT", "").strip()
    if not raw:
        raise ValueError("未配置 RAINYUN_ACCOUNT")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            data = ast.literal_eval(raw)
        except Exception as exc:
            raise ValueError(f"RAINYUN_ACCOUNT 解析失败: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("RAINYUN_ACCOUNT 必须是账号列表")

    accounts = []
    for index, item in enumerate(data, 1):
        if isinstance(item, dict):
            username = str(item.get("username") or item.get("user") or "").strip()
            password = str(item.get("password") or item.get("passwd") or "").strip()
            auto_renew = item.get("auto_renew", False)
            api_key = str(item.get("api_key") or "").strip()
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            username = str(item[0]).strip()
            password = str(item[1]).strip()
            auto_renew = item[2] if len(item) >= 3 else False
            api_key = str(item[3]).strip() if len(item) >= 4 and item[3] is not None else ""
        else:
            raise ValueError(f"第 {index} 个账号格式错误")

        if not username or not password:
            raise ValueError(f"第 {index} 个账号缺少用户名或密码")

        if isinstance(auto_renew, str):
            auto_renew = auto_renew.strip().lower() in ("1", "true", "yes", "on")
        else:
            auto_renew = bool(auto_renew)

        accounts.append(Account(username, password, auto_renew, api_key))

    if not accounts:
        raise ValueError("RAINYUN_ACCOUNT 中没有有效账号")

    logger.info("共解析 %s 个雨云账号", len(accounts))
    for index, account in enumerate(accounts, 1):
        logger.info(
            "账号%s: %s, 自动续费=%s, API Key=%s",
            index,
            mask_account(account.username),
            "开启" if account.auto_renew else "关闭",
            "已配置" if account.api_key else "未配置",
        )
    return accounts


def send_notification(title: str, content: str):
    if notify_send:
        try:
            notify_send(title, content)
            logger.info("notify.py 推送成功")
            return
        except Exception as exc:
            logger.warning("notify.py 推送失败: %s", exc)
    logger.info("%s\n%s", title, content)


def find_executable(env_name: str, candidates: List[str]) -> Optional[str]:
    configured = os.getenv(env_name, "").strip()
    if configured:
        if os.path.exists(configured):
            return configured
        logger.warning("%s 指定的路径不存在: %s", env_name, configured)

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def init_browser(config: dict):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ImportError as exc:
        raise RuntimeError("缺少 selenium，请执行 pip3 install selenium") from exc

    options = Options()
    if config.get("headless", True):
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=zh-CN")
    options.add_argument(
        "--user-agent=" + os.getenv(
            "RAINYUN_USER_AGENT",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    local_app_data = os.getenv("LOCALAPPDATA", "")
    chrome_candidates = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/snap/bin/chromium",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(local_app_data, r"Google\Chrome\Application\chrome.exe") if local_app_data else "",
    ]
    driver_candidates = [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        r"C:\WebDriver\chromedriver.exe",
    ]

    chrome_path = find_executable("RAINYUN_CHROME_PATH", chrome_candidates)
    driver_path = find_executable("RAINYUN_DRIVER_PATH", driver_candidates)
    if chrome_path:
        options.binary_location = chrome_path
        logger.info("使用浏览器: %s", chrome_path)

    try:
        if driver_path:
            logger.info("使用 ChromeDriver: %s", driver_path)
            driver = webdriver.Chrome(service=Service(driver_path), options=options)
        else:
            logger.info("未找到固定 ChromeDriver，尝试 Selenium Manager")
            driver = webdriver.Chrome(options=options)
    except Exception as exc:
        raise RuntimeError(
            "浏览器启动失败，请安装 Chromium/Chrome 和 chromedriver，"
            "或设置 RAINYUN_CHROME_PATH、RAINYUN_DRIVER_PATH"
        ) from exc

    driver.set_page_load_timeout(int(config["timeout"]) + 10)
    driver.delete_all_cookies()
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": STEALTH_JS})
    logger.info("浏览器启动成功，已注入单文件内置 stealth 配置")
    return driver


class RainyunAPI:
    def __init__(self, api_key: str, config: dict):
        if not api_key:
            raise ValueError("API Key 不能为空")
        self.base_url = str(config.get("api_base_url", DEFAULT_CONFIG["api_base_url"])).rstrip("/")
        self.timeout = int(config.get("api_request_timeout", 10))
        self.max_retries = max(1, int(config.get("api_max_retries", 3)))
        self.retry_delay = max(0, int(config.get("api_retry_delay", 2)))
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "ql-checkin-rainyun/1.0",
        })

    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        url = f"{self.base_url}{endpoint}"
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    json=data,
                    timeout=self.timeout,
                )
                try:
                    result = response.json()
                except ValueError as exc:
                    raise RainyunAPIError(
                        f"API 响应不是 JSON: HTTP {response.status_code}, {response.text[:200]}"
                    ) from exc

                code = result.get("code")
                if str(code) != "200":
                    raise RainyunAPIError(
                        f"API 错误 [{code}]: {result.get('message', '未知错误')}"
                    )
                return result.get("data", {})
            except (requests.RequestException, RainyunAPIError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    logger.warning("API 请求失败 (%s/%s): %s", attempt, self.max_retries, exc)
                    time.sleep(self.retry_delay)
                else:
                    break
        raise RainyunAPIError(f"API 请求失败: {last_error}")

    def get_user_points(self) -> int:
        return int(self._request("GET", "/user/").get("Points", 0))

    def get_server_list(self, product_type: str = "rgs") -> list:
        data = self._request("GET", f"/product/id_list?product_type={product_type}")
        return data.get(product_type, [])

    def get_server_detail(self, server_id: int) -> dict:
        return self._request("GET", f"/product/rgs/{server_id}/")

    def renew_server(self, server_id: int, days: int = 7) -> dict:
        return self._request("POST", "/product/point_renew", {
            "duration_day": days,
            "product_id": server_id,
            "product_type": "rgs",
        })


class ServerManager:
    def __init__(self, api: RainyunAPI, config: dict):
        self.api = api
        self.renew_days = int(config.get("renew_days", 7))
        self.threshold_days = int(config.get("renew_threshold_days", 3))
        self.min_reserve = int(config.get("min_points_reserve", 5000))

    @staticmethod
    def parse_expire_date(raw) -> datetime:
        if isinstance(raw, (int, float)):
            timestamp = raw / 1000 if raw > 10000000000 else raw
            return datetime.fromtimestamp(timestamp)
        value = str(raw or "").strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ValueError(f"无法解析到期时间: {value}")

    def check_and_renew(self) -> Dict:
        result = {"total": 0, "renewed": 0, "skipped": 0, "failed": 0, "details": []}
        points = self.api.get_user_points()
        server_ids = self.api.get_server_list("rgs")
        result["total"] = len(server_ids)
        logger.info("自动续费检查: %s 台服务器，当前积分 %s", len(server_ids), points)

        for server_id in server_ids:
            detail = self.process_server(server_id, points)
            result["details"].append(detail)
            action = detail["action"]
            if action == "renewed":
                result["renewed"] += 1
                points = detail["points_after"]
            elif action == "failed":
                result["failed"] += 1
            else:
                result["skipped"] += 1
        return result

    def process_server(self, server_id: int, points: int) -> Dict:
        detail = {
            "server_id": server_id,
            "action": "skipped",
            "reason": "",
            "points_cost": 0,
            "points_after": points,
            "exp_date": "",
            "days_left": 0,
        }
        try:
            info = self.api.get_server_detail(server_id)
            server_data = info.get("Data", {})
            prices = info.get("RenewPointPrice", {})
            expire = self.parse_expire_date(server_data.get("ExpDate"))
            detail["exp_date"] = expire.strftime("%Y-%m-%d %H:%M:%S")
            detail["days_left"] = (expire - datetime.now()).days

            if detail["days_left"] > self.threshold_days:
                detail["reason"] = f"剩余 {detail['days_left']} 天，暂不续费"
                return detail

            cost = prices.get(str(self.renew_days))
            if cost is None:
                detail["action"] = "failed"
                detail["reason"] = f"没有 {self.renew_days} 天续费价格"
                return detail

            cost = int(cost)
            if points - cost < self.min_reserve:
                detail["reason"] = f"积分不足或续费后低于保留值（需 {cost}，现有 {points}）"
                return detail

            self.api.renew_server(server_id, self.renew_days)
            detail.update({
                "action": "renewed",
                "reason": f"成功续费 {self.renew_days} 天",
                "points_cost": cost,
                "points_after": points - cost,
            })
            return detail
        except Exception as exc:
            detail["action"] = "failed"
            detail["reason"] = str(exc)
            return detail

    @staticmethod
    def generate_report(result: Dict) -> str:
        lines = [
            f"续费检查: {result['total']} 台",
            f"已续费: {result['renewed']} 台",
            f"跳过: {result['skipped']} 台",
            f"失败: {result['failed']} 台",
        ]
        for item in result["details"]:
            lines.append(f"服务器 {item['server_id']}: {item['reason']}")
        return "\n".join(lines)


def clear_temp_dir(temp_dir: str):
    os.makedirs(temp_dir, exist_ok=True)
    for filename in os.listdir(temp_dir):
        path = os.path.join(temp_dir, filename)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass


def get_url_from_style(style: str) -> str:
    match = re.search(r"url\([\"']?(.*?)[\"']?\)", style or "")
    if not match:
        raise ValueError(f"无法从 style 解析图片地址: {style}")
    return match.group(1)


def download_image(ctx: RuntimeContext, url: str, output_path: str) -> bool:
    max_retries = max(1, int(ctx.config.get("download_max_retries", 3)))
    retry_delay = max(0, int(ctx.config.get("download_retry_delay", 2)))
    timeout = int(ctx.config.get("download_timeout", 10))
    cookies = {cookie["name"]: cookie["value"] for cookie in ctx.driver.get_cookies()}
    headers = {
        "User-Agent": ctx.driver.execute_script("return navigator.userAgent"),
        "Referer": ctx.driver.current_url,
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                url,
                headers=headers,
                cookies=cookies,
                timeout=timeout,
            )
            response.raise_for_status()
            with open(output_path, "wb") as file:
                file.write(response.content)
            return True
        except Exception as exc:
            logger.warning("验证码图片下载失败 (%s/%s): %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(retry_delay)
    return False


def download_captcha_images(ctx: RuntimeContext) -> bool:
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC

        clear_temp_dir(ctx.temp_dir)
        slide_bg = ctx.wait.until(EC.visibility_of_element_located((By.ID, "slideBg")))
        bg_url = urljoin(ctx.driver.current_url, get_url_from_style(slide_bg.get_attribute("style")))
        sprite = ctx.wait.until(
            EC.visibility_of_element_located((By.XPATH, "//div[@id='instruction']//img"))
        )
        sprite_url = urljoin(ctx.driver.current_url, sprite.get_attribute("src"))
        return (
            download_image(ctx, bg_url, ctx.temp_path("captcha.jpg"))
            and download_image(ctx, sprite_url, ctx.temp_path("sprite.jpg"))
        )
    except Exception as exc:
        logger.warning("验证码图片获取失败: %s", exc)
        return False


def check_captcha_fragments(ctx: RuntimeContext) -> bool:
    try:
        import cv2

        raw = cv2.imread(ctx.temp_path("sprite.jpg"))
        if raw is None or raw.shape[1] < 3:
            return False
        width = raw.shape[1]
        for index in range(3):
            fragment = raw[:, width // 3 * index: width // 3 * (index + 1)]
            path = ctx.temp_path(f"sprite_{index + 1}.jpg")
            cv2.imwrite(path, fragment)
            with open(path, "rb") as file:
                result = ctx.ocr.classification(file.read())
            if result in ("0", "1"):
                logger.warning("验证码碎片 %s 疑似无效，OCR=%s", index + 1, result)
                return False
        return True
    except Exception as exc:
        logger.warning("验证码碎片校验失败: %s", exc)
        return False


def compute_similarity(path1: str, path2: str) -> Tuple[float, int]:
    try:
        import cv2

        image1 = cv2.imread(path1, cv2.IMREAD_GRAYSCALE)
        image2 = cv2.imread(path2, cv2.IMREAD_GRAYSCALE)
        if image1 is None or image2 is None:
            return 0.0, 0
        try:
            detector = cv2.SIFT_create()
            norm = cv2.NORM_L2
        except AttributeError:
            detector = cv2.ORB_create()
            norm = cv2.NORM_HAMMING

        _, desc1 = detector.detectAndCompute(image1, None)
        _, desc2 = detector.detectAndCompute(image2, None)
        if desc1 is None or desc2 is None:
            return 0.0, 0

        matches = cv2.BFMatcher(norm, crossCheck=False).knnMatch(desc1, desc2, k=2)
        good = []
        for pair in matches:
            if len(pair) == 2 and pair[0].distance < 0.8 * pair[1].distance:
                good.append(pair[0])
        return (len(good) / len(matches), len(good)) if matches else (0.0, 0)
    except Exception:
        return 0.0, 0


def build_captcha_answer(ctx: RuntimeContext) -> dict:
    import cv2

    captcha = cv2.imread(ctx.temp_path("captcha.jpg"))
    if captcha is None:
        raise CaptchaRetryableError("验证码背景图读取失败")
    with open(ctx.temp_path("captcha.jpg"), "rb") as file:
        boxes = ctx.det.detection(file.read())
    if not boxes:
        raise CaptchaRetryableError("未检测到验证码图案")

    result = {}
    for box_index, (x1, y1, x2, y2) in enumerate(boxes, 1):
        spec_path = ctx.temp_path(f"spec_{box_index}.jpg")
        cv2.imwrite(spec_path, captcha[y1:y2, x1:x2])
        for sprite_index in range(1, 4):
            similarity, _ = compute_similarity(
                ctx.temp_path(f"sprite_{sprite_index}.jpg"),
                spec_path,
            )
            key = f"sprite_{sprite_index}"
            if similarity > float(result.get(f"{key}_similarity", 0)):
                result[f"{key}_similarity"] = similarity
                result[f"{key}_position"] = (int((x1 + x2) / 2), int((y1 + y2) / 2))

    threshold = float(ctx.config.get("similarity_threshold", 0.4))
    positions = []
    for index in range(1, 4):
        similarity = float(result.get(f"sprite_{index}_similarity", 0))
        position = result.get(f"sprite_{index}_position")
        logger.info("验证码图案%s: 坐标=%s, 相似度=%.4f", index, position, similarity)
        if not position or similarity < threshold:
            raise CaptchaRetryableError(
                f"图案 {index} 相似度 {similarity:.4f} 低于阈值 {threshold}"
            )
        positions.append(position)

    if len(set(positions)) != 3:
        raise CaptchaRetryableError(f"验证码坐标重复: {positions}")
    result["_captcha"] = captcha
    return result


def click_captcha(ctx: RuntimeContext, result: dict):
    from selenium.webdriver import ActionChains
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC

    slide_bg = ctx.wait.until(EC.visibility_of_element_located((By.ID, "slideBg")))
    displayed_width = float(slide_bg.size.get("width") or 300)
    displayed_height = float(slide_bg.size.get("height") or 150)
    captcha = result["_captcha"]
    raw_height, raw_width = captcha.shape[:2]

    for index in range(1, 4):
        x, y = result[f"sprite_{index}_position"]
        x_offset = int(-displayed_width / 2 + x / raw_width * displayed_width)
        y_offset = int(-displayed_height / 2 + y / raw_height * displayed_height)
        x_offset += random.randint(-1, 1)
        y_offset += random.randint(-1, 1)
        ActionChains(ctx.driver).move_to_element_with_offset(
            slide_bg,
            x_offset,
            y_offset,
        ).click().perform()
        time.sleep(random.uniform(0.5, 1.0))


def refresh_captcha(ctx: RuntimeContext) -> bool:
    try:
        from selenium.webdriver.common.by import By

        ctx.driver.find_element(By.ID, "reload").click()
        time.sleep(2)
        return True
    except Exception as exc:
        logger.warning("刷新验证码失败: %s", exc)
        return False


def process_captcha(ctx: RuntimeContext) -> bool:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC

    retry_limit = int(ctx.config.get("captcha_retry_limit", 10))
    unlimited = retry_limit == -1
    attempt = 0

    while unlimited or attempt < retry_limit:
        attempt += 1
        total = "∞" if unlimited else str(retry_limit)
        logger.info("验证码处理第 %s/%s 次", attempt, total)
        try:
            if not download_captcha_images(ctx):
                raise CaptchaRetryableError("验证码图片下载失败")
            if not check_captcha_fragments(ctx):
                raise CaptchaRetryableError("验证码碎片无效")
            result = build_captcha_answer(ctx)
            click_captcha(ctx, result)

            confirm = ctx.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//div[@id='tcStatus']/div[2]/div[2]/div/div")
                )
            )
            confirm.click()
            time.sleep(5)
            operation = ctx.wait.until(EC.visibility_of_element_located((By.ID, "tcOperation")))
            if "show-success" in (operation.get_attribute("class") or ""):
                logger.info("验证码验证通过")
                return True
            raise CaptchaRetryableError("验证码验证失败")
        except Exception as exc:
            logger.warning("验证码处理失败: %s", exc)
            if not refresh_captcha(ctx):
                return False
            delay = min(3 * (2 ** (attempt - 1)), 30)
            logger.info("等待 %s 秒后重试", delay)
            time.sleep(delay)

    logger.error("验证码重试 %s 次仍失败", retry_limit)
    return False


def init_ocr():
    try:
        import ddddocr
    except ImportError as exc:
        raise RuntimeError("缺少 ddddocr，请执行 pip3 install ddddocr") from exc
    return (
        ddddocr.DdddOcr(ocr=True, show_ad=False),
        ddddocr.DdddOcr(det=True, show_ad=False),
    )


def switch_to_captcha_if_present(ctx: RuntimeContext) -> bool:
    from selenium.common import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.wait import WebDriverWait

    try:
        WebDriverWait(ctx.driver, int(ctx.config.get("captcha_wait", 6))).until(
            EC.visibility_of_element_located((By.ID, "tcaptcha_iframe_dy"))
        )
        ctx.driver.switch_to.frame("tcaptcha_iframe_dy")
        return True
    except TimeoutException:
        return False


def compact_text(text: str, limit: int = 500) -> str:
    text = re.sub(r"\s+", " / ", (text or "").strip())
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def is_daily_sign_done(text: str) -> bool:
    text = re.sub(r"\s+", " ", text or "")
    if re.search(r"每日签到\s*(已完成|已领取|已签到|明日再来)", text):
        return True
    return False


def do_login(ctx: RuntimeContext, username: str, password: str) -> bool:
    from selenium.common import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC

    try:
        logger.info("访问雨云登录页")
        ctx.driver.get("https://app.rainyun.com/auth/login")
        user_input = ctx.wait.until(EC.visibility_of_element_located((By.NAME, "login-field")))
        password_input = ctx.wait.until(
            EC.visibility_of_element_located((By.NAME, "login-password"))
        )
        submit = ctx.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[@type='submit' and contains(., '登')]")
            )
        )
        user_input.clear()
        user_input.send_keys(username)
        password_input.clear()
        password_input.send_keys(password)
        submit.click()
        time.sleep(3)

        if switch_to_captcha_if_present(ctx):
            logger.info("登录触发验证码")
            if not process_captcha(ctx):
                return False
            ctx.driver.switch_to.default_content()
        else:
            logger.info("登录未触发验证码")

        try:
            ctx.wait.until(lambda driver: "auth/login" not in driver.current_url)
        except TimeoutException:
            pass
        time.sleep(2)
        current_url = ctx.driver.current_url
        if "dashboard" in current_url or "auth/login" not in current_url:
            logger.info("账号登录成功: %s", mask_account(username))
            return True
        logger.error("登录后仍停留在登录页: %s", current_url)
        return False
    except Exception as exc:
        logger.error("登录异常: %s", exc)
        return False
    finally:
        try:
            ctx.driver.switch_to.default_content()
        except Exception:
            pass


def find_daily_sign_container(ctx: RuntimeContext):
    from selenium.common import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC

    ctx.wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(normalize-space(.), '每日签到')]")
        )
    )
    labels = ctx.driver.find_elements(
        By.XPATH,
        "//*[normalize-space()='每日签到' or contains(normalize-space(.), '每日签到')]",
    )
    for label in labels:
        current = label
        for _ in range(8):
            text = (current.text or "").strip()
            if (
                "每日签到" in text
                and any(keyword in text for keyword in ("领取奖励", "已完成", "已领取", "已签到", "明日再来"))
                and len(text) < 800
            ):
                return current
            try:
                current = current.find_element(By.XPATH, "..")
            except Exception:
                break
    if labels:
        return labels[0].find_element(By.XPATH, "..")
    raise TimeoutException("未找到每日签到任务")


def do_sign_in(ctx: RuntimeContext) -> bool:
    from selenium.common import TimeoutException
    from selenium.webdriver.common.by import By

    try:
        logger.info("访问雨云积分任务页")
        ctx.driver.get("https://app.rainyun.com/account/reward/earn")
        page_text = ctx.driver.find_element(By.TAG_NAME, "body").text
        if is_daily_sign_done(page_text):
            logger.info("每日签到已完成")
            return True

        container = find_daily_sign_container(ctx)
        status_text = (container.text or "").strip()
        logger.info("每日签到区域状态: %s", compact_text(status_text))

        if is_daily_sign_done(status_text) or any(keyword in status_text for keyword in ("已完成", "已领取", "已签到", "明日再来")):
            return True

        click_target = None
        for element in container.find_elements(
            By.XPATH,
            ".//*[self::a or self::button or @role='button']",
        ):
            text = (element.text or "").strip()
            if "领取奖励" in text or text == "领取":
                click_target = element
                break

        if not click_target:
            # 兼容上游页面结构。
            try:
                label = container.find_element(By.XPATH, ".//span[contains(text(),'每日签到')]")
                status = label.find_element(By.XPATH, "./following-sibling::span[1]")
                if "领取奖励" in (status.text or ""):
                    click_target = status.find_element(By.XPATH, ".//a")
            except Exception:
                pass

        if not click_target:
            page_text = ctx.driver.find_element(By.TAG_NAME, "body").text
            if is_daily_sign_done(page_text):
                logger.info("每日签到已完成")
                return True
            logger.error("未找到每日签到领取按钮")
            return False

        ctx.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", click_target)
        time.sleep(0.5)
        click_target.click()
        time.sleep(2)

        if switch_to_captcha_if_present(ctx):
            logger.info("签到触发验证码")
            if not process_captcha(ctx):
                return False
            ctx.driver.switch_to.default_content()
        else:
            logger.info("签到未触发验证码")

        time.sleep(5)
        page_text = ctx.driver.find_element(By.TAG_NAME, "body").text
        if is_daily_sign_done(page_text) or any(keyword in page_text for keyword in ("已完成", "已领取", "签到成功", "明日再来")):
            logger.info("签到奖励领取成功")
            return True

        # 验证码成功后页面提示可能消失，但领取动作通常已经完成。
        ctx.driver.refresh()
        time.sleep(3)
        container = find_daily_sign_container(ctx)
        refreshed = (container.text or "").strip()
        if is_daily_sign_done(refreshed) or any(keyword in refreshed for keyword in ("已完成", "已领取", "已签到", "明日再来")):
            logger.info("签到状态已更新")
            return True
        logger.warning("未确认到签到成功状态: %s", compact_text(refreshed))
        return False
    except TimeoutException:
        logger.error("雨云签到页面加载超时")
        return False
    except Exception as exc:
        logger.error("签到异常: %s", exc)
        return False
    finally:
        try:
            ctx.driver.switch_to.default_content()
        except Exception:
            pass


def execute_auto_renew(account: Account, config: dict) -> str:
    if not account.api_key:
        return "未配置 API Key，跳过续费"
    try:
        manager = ServerManager(RainyunAPI(account.api_key, config), config)
        result = manager.check_and_renew()
        report = manager.generate_report(result)
        logger.info("\n%s", report)
        return (
            f"续费: {result['renewed']} 台成功, "
            f"{result['skipped']} 台跳过, {result['failed']} 台失败"
        )
    except Exception as exc:
        logger.error("自动续费失败: %s", exc)
        return f"续费失败: {exc}"


def wait_random_delay(config: dict):
    if not env_bool("RANDOM_SIGNIN", True):
        return
    default_seconds = max(0, int(config.get("max_delay", 5)) * 60)
    max_seconds = env_int("MAX_RANDOM_DELAY", default_seconds)
    if max_seconds <= 0:
        return
    delay = random.randint(0, max_seconds)
    if delay:
        logger.info("随机延迟 %s 秒", delay)
        time.sleep(delay)


def sign_in_account(account: Account, config: dict) -> AccountResult:
    result = AccountResult(
        username=account.username,
        auto_renew_enabled=account.auto_renew,
    )
    driver = None
    temp_dir = None
    try:
        wait_random_delay(config)
        ocr, det = init_ocr()
        driver = init_browser(config)
        from selenium.webdriver.support.wait import WebDriverWait

        temp_dir = tempfile.mkdtemp(prefix="rainyun-")
        ctx = RuntimeContext(
            driver=driver,
            wait=WebDriverWait(driver, int(config["timeout"])),
            ocr=ocr,
            det=det,
            temp_dir=temp_dir,
            config=config,
        )

        if account.api_key:
            try:
                result.points_before = RainyunAPI(account.api_key, config).get_user_points()
                logger.info("签到前积分: %s", result.points_before)
            except Exception as exc:
                logger.warning("签到前积分查询失败: %s", exc)

        result.login_success = do_login(ctx, account.username, account.password)
        if not result.login_success:
            result.error_msg = "登录失败"
            return result

        result.sign_in_success = do_sign_in(ctx)
        if not result.sign_in_success:
            result.error_msg = "签到失败"
            return result

        if account.api_key:
            try:
                result.points_after = RainyunAPI(account.api_key, config).get_user_points()
                result.points_earned = result.points_after - result.points_before
                logger.info("签到后积分: %s，本次变化: %+d", result.points_after, result.points_earned)
            except Exception as exc:
                logger.warning("签到后积分查询失败: %s", exc)

        if account.auto_renew:
            result.renew_summary = execute_auto_renew(account, config)
        return result
    except Exception as exc:
        result.error_msg = str(exc)
        logger.exception("账号处理异常")
        return result
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        if temp_dir:
            if config.get("keep_debug_files") or env_bool("RAINYUN_KEEP_DEBUG_FILES", False):
                logger.info("保留调试目录: %s", temp_dir)
            else:
                shutil.rmtree(temp_dir, ignore_errors=True)


def generate_summary(results: List[AccountResult], config: dict) -> str:
    success = sum(result.is_success() for result in results)
    lines = [
        "雨云签到任务执行报告",
        f"总账号数: {len(results)}",
        f"成功: {success}",
        f"失败: {len(results) - success}",
    ]

    total_before = sum(result.points_before for result in results)
    total_after = sum(result.points_after for result in results)
    total_earned = sum(result.points_earned for result in results)
    if total_after:
        lines.extend([
            "",
            f"签到前总积分: {total_before}",
            f"签到后总积分: {total_after}",
            f"本次积分变化: {total_earned:+d}",
            f"约合人民币: {total_after / float(config['points_to_cny_rate']):.2f} 元",
        ])

    for index, result in enumerate(results, 1):
        lines.extend([
            "",
            f"账号 {index}: {mask_account(result.username)}",
            f"状态: {'成功' if result.is_success() else '失败'}",
        ])
        if result.points_after:
            lines.append(
                f"积分: {result.points_before} -> {result.points_after} ({result.points_earned:+d})"
            )
        if result.auto_renew_enabled:
            lines.append(f"自动续费: {result.renew_summary or '已启用'}")
        if result.error_msg:
            lines.append(f"原因: {result.error_msg}")

    lines.extend(["", f"执行时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"])
    return "\n".join(lines)


def main() -> int:
    logger.info("=" * 60)
    logger.info("雨云自动签到单文件版")
    logger.info("上游: LMTXQ/Rainyun-QingLong")
    logger.info("=" * 60)

    try:
        config = load_config()
        accounts = parse_accounts()
    except Exception as exc:
        message = f"雨云配置错误: {exc}"
        logger.error(message)
        send_notification("雨云签到失败", message)
        return 1

    results = []
    for index, account in enumerate(accounts, 1):
        logger.info("-" * 60)
        logger.info("处理账号 %s/%s: %s", index, len(accounts), mask_account(account.username))
        results.append(sign_in_account(account, config))
        if index < len(accounts):
            minimum = float(config.get("account_interval_min", 3))
            maximum = float(config.get("account_interval_max", 6))
            if maximum < minimum:
                minimum, maximum = maximum, minimum
            interval = random.uniform(minimum, maximum)
            logger.info("等待 %.1f 秒后处理下一个账号", interval)
            time.sleep(interval)

    summary = generate_summary(results, config)
    logger.info("\n%s", summary)
    send_notification("雨云签到任务完成", summary)
    return 0 if all(result.is_success() for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
