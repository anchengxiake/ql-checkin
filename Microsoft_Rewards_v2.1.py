#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cron: 1 7-20 * * *
new Env('微软积分签到')

Microsoft Rewards 青龙单文件版

基于 chiihero/Microsoft-Rewards-Script 的配置化 workers 思路重写：
- Cookie 多账号
- 可选 refresh_token 阅读任务
- 每日活动 / 更多活动 / PC 搜索 / 移动搜索 / 阅读任务开关
- 国内热搜词源 + 本地兜底词库
- 多账号并发限制，青龙默认串行更稳

变量：
bing_ck_1、bing_ck_2...                         必需
bing_token_1、bing_token_2...                    可选，阅读任务使用

兼容变量：
MR_COOKIE_1 / BING_COOKIE_1 / ACCOUNT_1_COOKIE
MR_TOKEN_1 / BING_TOKEN_1 / ACCOUNT_1_REFRESH_TOKEN
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def env_int(name: str, default: int, minimum: Optional[int] = None) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        result = default
    else:
        try:
            result = int(value)
        except ValueError:
            print(f"⚠️  环境变量 {name}={value!r} 不是整数，使用默认值 {default}")
            result = default
    if minimum is not None:
        result = max(minimum, result)
    return result


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    return default


def env_list(name: str, default: str) -> List[str]:
    value = os.getenv(name, default)
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_key() -> str:
    return date.today().strftime("%m/%d/%Y")


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return email or "未知账号"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[:1]}***@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"


def format_seconds(seconds: int) -> str:
    if seconds <= 0:
        return "立即执行"
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if hours:
        return f"{hours}小时{minutes}分{seconds}秒"
    if minutes:
        return f"{minutes}分{seconds}秒"
    return f"{seconds}秒"


def wait_with_countdown(delay: int, task_name: str = "微软积分签到") -> None:
    if delay <= 0:
        return
    print(f"{task_name} 需要等待 {format_seconds(delay)}")
    remaining = delay
    while remaining > 0:
        if remaining <= 10 or remaining % 10 == 0:
            print(f"{task_name} 倒计时: {format_seconds(remaining)}")
        sleep_time = 1 if remaining <= 10 else min(10, remaining)
        time.sleep(sleep_time)
        remaining -= sleep_time


def sleep_range(min_seconds: int, max_seconds: int) -> None:
    if max_seconds <= 0:
        return
    if max_seconds < min_seconds:
        max_seconds = min_seconds
    time.sleep(random.uniform(min_seconds, max_seconds))


def print_log(module: str, message: str, account_index: Optional[int] = None) -> None:
    prefix = f"账号{account_index} " if account_index else ""
    print(f"{datetime.now().strftime('%H:%M:%S')} [{module}] {prefix}{message}")


hadsend = False
send_func = None
try:
    from notify import send as notify_send

    send_func = notify_send
    hadsend = True
    print("✅ 已加载notify.py通知模块")
except Exception:
    print("⚠️  未加载notify.py通知模块，跳过通知功能")


def notify_user(title: str, content: str) -> None:
    if not hadsend or send_func is None:
        print(f"📢 {title}\n{content}")
        return
    try:
        send_func(title, content)
        print_log("通知", f"推送成功: {title}")
    except Exception as exc:
        print_log("通知", f"推送失败: {exc}")


@dataclass
class Config:
    random_signin: bool = env_bool("RANDOM_SIGNIN", True)
    max_random_delay: int = env_int("MAX_RANDOM_DELAY", 1800, 0)
    max_workers: int = env_int("MR_MAX_WORKERS", 1, 1)
    account_max_index: int = env_int("MR_ACCOUNT_MAX_INDEX", 50, 1)
    consecutive_empty_limit: int = env_int("MR_EMPTY_LIMIT", 10, 1)
    request_timeout: int = env_int("MR_REQUEST_TIMEOUT", 20, 5)
    max_retries: int = env_int("MR_MAX_RETRIES", 3, 1)
    retry_delay: int = env_int("MR_RETRY_DELAY", 2, 0)
    task_delay_min: int = env_int("MR_TASK_DELAY_MIN", 2, 0)
    task_delay_max: int = env_int("MR_TASK_DELAY_MAX", 4, 0)
    search_delay_min: int = env_int("MR_SEARCH_DELAY_MIN", 60, 0)
    search_delay_max: int = env_int("MR_SEARCH_DELAY_MAX", 80, 0)
    search_batch_size: int = env_int("MR_SEARCH_CHECK_INTERVAL", 5, 1)
    hot_words_max_count: int = env_int("MR_HOT_WORDS_MAX_COUNT", 30, 1)
    geo_locale: str = os.getenv("MR_GEO_LOCALE", os.getenv("ACCOUNT_1_GEO_LOCALE", "cn")).strip().lower() or "cn"
    lang_code: str = os.getenv("MR_LANG_CODE", os.getenv("ACCOUNT_1_LANG_CODE", "zh")).strip().lower() or "zh"
    bing_host: str = os.getenv("MR_BING_HOST", "").strip().rstrip("/")
    query_engines: List[str] = None
    do_read_tasks: bool = env_bool("MR_DO_READ_TASKS", True)
    do_daily_set: bool = env_bool("MR_DO_DAILY_SET", True)
    do_more_promotions: bool = env_bool("MR_DO_MORE_PROMOTIONS", True)
    do_pc_search: bool = env_bool("MR_DO_PC_SEARCH", True)
    do_mobile_search: bool = env_bool("MR_DO_MOBILE_SEARCH", True)
    run_on_zero_searches: bool = env_bool("MR_RUN_ON_ZERO_SEARCHES", False)
    cache_file: str = os.getenv("MR_TOKEN_CACHE_FILE", "microsoft_rewards_token_cache.json")
    cache_enabled: bool = env_bool("MR_CACHE_ENABLED", True)

    def __post_init__(self) -> None:
        if not self.bing_host:
            self.bing_host = "https://cn.bing.com" if self.geo_locale in ("cn", "zh-cn") else "https://www.bing.com"
        if self.query_engines is None:
            self.query_engines = env_list("MR_QUERY_ENGINES", "china,local")

    def accept_language(self) -> str:
        if self.lang_code.startswith("zh"):
            return "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"
        return "en-US,en;q=0.9,zh-CN;q=0.7,zh;q=0.6"

    def bing_search_url(self) -> str:
        return f"{self.bing_host}/search"

    def bing_origin(self, url: str) -> str:
        if "/search" in url:
            return url.split("/search", 1)[0]
        return self.bing_host

    def pc_ua(self) -> str:
        fixed = os.getenv("MR_PC_USER_AGENT", "").strip()
        if fixed:
            return fixed
        return random.choice(PC_USER_AGENTS)

    def mobile_ua(self) -> str:
        fixed = os.getenv("MR_MOBILE_USER_AGENT", "").strip()
        if fixed:
            return fixed
        return random.choice(MOBILE_USER_AGENTS)


config = Config()


PC_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; 2210132C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.52 Mobile Safari/537.36 EdgA/125.0.2535.51",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/123.0.2420.108 Version/18.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.44 Mobile Safari/537.36 EdgA/124.0.2478.49",
]


DEFAULT_HOT_WORDS = [
    "人工智能最新进展",
    "今日天气",
    "微软Copilot",
    "国内新闻",
    "科技新闻",
    "电影推荐",
    "健康饮食",
    "Python 教程",
    "旅行攻略",
    "新能源汽车",
    "世界杯",
    "股票行情",
    "云计算",
    "机器学习",
    "今日热点",
]


HOT_WORD_APIS: List[Tuple[str, List[str]]] = [
    ("https://dailyapi.eray.cc/", ["weibo", "douyin", "baidu", "toutiao", "thepaper", "qq-news", "netease-news", "zhihu"]),
    ("https://hot.baiwumm.com/api/", ["weibo", "douyin", "baidu", "toutiao", "thepaper", "qq", "netease", "zhihu"]),
    ("https://cnxiaobai.com/DailyHotApi/", ["weibo", "douyin", "baidu", "toutiao", "thepaper", "qq-news", "netease-news", "zhihu"]),
    ("https://hotapi.nntool.cc/", ["weibo", "douyin", "baidu", "toutiao", "thepaper", "qq-news", "netease-news", "zhihu"]),
]


class HotWordsManager:
    def __init__(self) -> None:
        self.words = self._load_words()
        print_log("热搜词", f"已加载 {len(self.words)} 个搜索词")

    def _load_words(self) -> List[str]:
        words: List[str] = []
        if "china" in config.query_engines:
            words.extend(self._fetch_from_china_apis())
        if "local" in config.query_engines or not words:
            words.extend(DEFAULT_HOT_WORDS)
        deduped: List[str] = []
        seen = set()
        for word in words:
            word = str(word).strip()
            if not word or word in seen:
                continue
            seen.add(word)
            deduped.append(word)
            if len(deduped) >= config.hot_words_max_count:
                break
        return deduped or DEFAULT_HOT_WORDS

    def _fetch_from_china_apis(self) -> List[str]:
        words: List[str] = []
        session = requests.Session()
        for base_url, channels in HOT_WORD_APIS:
            random.shuffle(channels)
            for channel in channels[:3]:
                url = base_url.rstrip("/") + f"/{channel}"
                try:
                    response = session.get(url, timeout=8)
                    if response.status_code != 200:
                        continue
                    data = response.json()
                    words.extend(self._extract_words(data))
                    if len(words) >= config.hot_words_max_count:
                        return words
                except Exception:
                    continue
        return words

    def _extract_words(self, data: Any) -> List[str]:
        results: List[str] = []
        if isinstance(data, dict):
            for key in ("data", "list", "result", "items"):
                if key in data:
                    results.extend(self._extract_words(data[key]))
            for key in ("title", "name", "word", "keyword", "desc"):
                value = data.get(key)
                if isinstance(value, str):
                    results.append(value)
        elif isinstance(data, list):
            for item in data:
                results.extend(self._extract_words(item))
        elif isinstance(data, str):
            results.append(data)
        return results

    def random_word(self) -> str:
        return random.choice(self.words)


hot_words = HotWordsManager()


@dataclass
class AccountInfo:
    index: int
    alias: str
    cookie: str
    refresh_token: str = ""


class AccountManager:
    @staticmethod
    def first_env(*names: str) -> str:
        for name in names:
            value = os.getenv(name, "").strip()
            if value:
                return value
        return ""

    @classmethod
    def get_accounts(cls) -> List[AccountInfo]:
        accounts: List[AccountInfo] = []
        empty_count = 0
        for index in range(1, config.account_max_index + 1):
            cookie = cls.first_env(
                f"bing_ck_{index}",
                f"BING_COOKIE_{index}",
                f"MR_COOKIE_{index}",
                f"ACCOUNT_{index}_COOKIE",
            )
            refresh_token = cls.first_env(
                f"bing_token_{index}",
                f"BING_TOKEN_{index}",
                f"MR_TOKEN_{index}",
                f"ACCOUNT_{index}_REFRESH_TOKEN",
            )
            alias = cls.first_env(f"MR_ALIAS_{index}", f"ACCOUNT_{index}_ALIAS") or f"account_{index}"

            if not cookie and not refresh_token:
                empty_count += 1
                if empty_count >= config.consecutive_empty_limit:
                    break
                continue
            empty_count = 0

            if not cookie:
                print_log("账号配置", "缺少 Cookie，跳过", index)
                continue
            missing_fields = []
            if "tifacfaatcs=" not in cookie:
                missing_fields.append("tifacfaatcs")
            if ".MSA.Auth=" not in cookie:
                missing_fields.append(".MSA.Auth")
            if missing_fields:
                print_log("账号配置", f"Cookie 缺少字段 {', '.join(missing_fields)}，仍尝试执行", index)

            accounts.append(AccountInfo(index=index, alias=alias, cookie=cookie, refresh_token=refresh_token))
        return accounts


class TokenCache:
    def __init__(self, filename: str) -> None:
        self.path = os.path.join(os.path.abspath(os.path.dirname(__file__)), filename)

    def load(self) -> Dict[str, str]:
        if not config.cache_enabled or not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_token(self, alias: str, token: str) -> None:
        if not config.cache_enabled or not alias or not token:
            return
        data = self.load()
        data[alias] = token
        try:
            with open(self.path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            print_log("Token缓存", f"已更新 {alias}")
        except Exception as exc:
            print_log("Token缓存", f"写入失败: {exc}")


token_cache = TokenCache(config.cache_file)


class RewardsClient:
    def __init__(self, account: AccountInfo) -> None:
        self.account = account
        self.session = requests.Session()

    def close(self) -> None:
        self.session.close()

    def request(self, method: str, url: str, *, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None,
                data: Any = None, json_data: Any = None, timeout: Optional[int] = None,
                allow_redirects: bool = True) -> requests.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(1, config.max_retries + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json_data,
                    timeout=timeout or config.request_timeout,
                    allow_redirects=allow_redirects,
                )
                if response.status_code in (429, 500, 502, 503, 504) and attempt < config.max_retries:
                    time.sleep(config.retry_delay + attempt)
                    continue
                return response
            except Exception as exc:
                last_exc = exc
                if attempt < config.max_retries:
                    time.sleep(config.retry_delay + attempt)
                    continue
        if last_exc:
            raise last_exc
        raise RuntimeError("request failed")

    def browser_headers(self, mobile: bool = False, ajax: bool = False) -> Dict[str, str]:
        ua = config.mobile_ua() if mobile else config.pc_ua()
        headers = {
            "User-Agent": ua,
            "Accept": "application/json, text/javascript, */*; q=0.01" if ajax else "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": config.accept_language(),
            "Cookie": self.account.cookie,
            "Referer": "https://rewards.bing.com/",
        }
        if ajax:
            headers["X-Requested-With"] = "XMLHttpRequest"
        return headers

    def get_home_info(self) -> Optional[Dict[str, Any]]:
        response = self.request("GET", "https://rewards.bing.com", headers=self.browser_headers())
        if response.status_code != 200:
            print_log("账号信息", f"首页状态码 {response.status_code}", self.account.index)
            return None
        html = response.text
        points = self._extract_int(html, r'"availablePoints"\s*:\s*(\d+)')
        email = self._extract_str(html, r'email:\s*"([^"]+)"') or self._extract_str(html, r'"email"\s*:\s*"([^"]+)"')
        token = self._extract_str(html, r'name="__RequestVerificationToken".*?value="([^"]+)"')
        if points is None or not email:
            print_log("账号信息", "Cookie 可能失效，无法解析积分或邮箱", self.account.index)
            return None
        return {"points": points, "email": email, "token": token}

    def get_dashboard(self, silent: bool = False) -> Optional[Dict[str, Any]]:
        try:
            response = self.request(
                "GET",
                "https://rewards.bing.com/api/getuserinfo",
                headers=self.browser_headers(ajax=True),
                timeout=30,
            )
            if response.status_code != 200:
                if not silent:
                    print_log("Dashboard", f"状态码 {response.status_code}", self.account.index)
                return None
            data = response.json()
            if not isinstance(data, dict) or "dashboard" not in data:
                if not silent:
                    print_log("Dashboard", "返回格式不正确", self.account.index)
                return None
            return data
        except Exception as exc:
            if not silent:
                print_log("Dashboard", f"获取失败: {exc}", self.account.index)
            return None

    @staticmethod
    def _extract_int(text: str, pattern: str) -> Optional[int]:
        match = re.search(pattern, text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_str(text: str, pattern: str) -> str:
        match = re.search(pattern, text, re.S)
        return match.group(1) if match else ""

    def account_level(self, dashboard: Optional[Dict[str, Any]]) -> str:
        if not dashboard:
            return "Level1"
        level = dashboard.get("dashboard", {}).get("userStatus", {}).get("levelInfo", {}) or {}
        return level.get("activeLevel", "Level1")

    def search_status(self, dashboard: Optional[Dict[str, Any]], search_type: str) -> Tuple[int, int, bool]:
        if not dashboard:
            return 0, 0, False
        counters = dashboard.get("dashboard", {}).get("userStatus", {}).get("counters", {}) or {}
        tasks = counters.get(search_type, []) or []
        current = sum(int(task.get("pointProgress", 0) or 0) for task in tasks)
        maximum = sum(int(task.get("pointProgressMax", 0) or 0) for task in tasks)
        complete = bool(tasks) and all(bool(task.get("complete")) for task in tasks)
        return current, maximum, complete or (maximum > 0 and current >= maximum)

    def today_earned(self, dashboard: Optional[Dict[str, Any]]) -> int:
        if not dashboard:
            return 0
        status = dashboard.get("status", {}) or {}
        for key in ("pointProgress", "dailyPointProgress", "earnedPoints"):
            value = status.get(key)
            if isinstance(value, int):
                return value
        return 0

    def complete_daily_set(self, token: str) -> Tuple[int, int]:
        dashboard = self.get_dashboard()
        if not dashboard:
            return 0, 0
        daily = dashboard.get("dashboard", {}).get("dailySetPromotions", {}) or {}
        tasks = daily.get(today_key(), []) or []
        total = len(tasks)
        done_before = sum(1 for task in tasks if task.get("complete"))
        completed_now = 0
        for task in tasks:
            if task.get("complete"):
                continue
            title = task.get("title") or task.get("name") or "每日活动"
            print_log("每日活动", f"执行: {title}", self.account.index)
            if self.execute_promotion(task, token):
                completed_now += 1
            sleep_range(config.task_delay_min, config.task_delay_max)
        return min(total, done_before + completed_now), total

    def complete_more_promotions(self, token: str) -> Tuple[int, int]:
        dashboard = self.get_dashboard()
        if not dashboard:
            return 0, 0
        raw_tasks = (dashboard.get("dashboard", {}).get("morePromotions", []) or []) + (
            dashboard.get("dashboard", {}).get("promotionalItems", []) or []
        )
        valuable = [task for task in raw_tasks if self.is_valuable_promotion(task)]
        total = len(valuable)
        done_before = sum(1 for task in valuable if task.get("complete"))
        completed_now = 0
        for task in valuable:
            if task.get("complete"):
                continue
            title = task.get("title") or task.get("name") or "更多活动"
            print_log("更多活动", f"执行: {title}", self.account.index)
            if self.execute_promotion(task, token):
                completed_now += 1
            sleep_range(config.task_delay_min, config.task_delay_max)
        return min(total, done_before + completed_now), total

    def is_valuable_promotion(self, task: Dict[str, Any]) -> bool:
        attrs = task.get("attributes", {}) or {}
        if attrs.get("is_unlocked") == "False":
            return False
        points = int(task.get("pointProgressMax", 0) or 0)
        if points <= 0:
            return False
        priority = task.get("priority")
        return priority is None or -30 <= int(priority) <= 10

    def execute_promotion(self, task: Dict[str, Any], token: str) -> bool:
        destination = task.get("destinationUrl") or (task.get("attributes", {}) or {}).get("destination")
        if destination:
            try:
                self.request("GET", destination, headers=self.browser_headers(), timeout=config.request_timeout)
            except Exception:
                pass
        offer_id = task.get("offerId") or task.get("name") or task.get("id")
        if not offer_id or not token:
            return False
        payload = (
            f"id={quote(str(offer_id))}"
            f"&hash={quote(str(task.get('hash', '')))}"
            "&timeZone=480&activityAmount=1&dbs=0&form=&type="
            f"&__RequestVerificationToken={quote(token)}"
        )
        headers = self.browser_headers(ajax=True)
        headers.update({"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        response = self.request(
            "POST",
            "https://rewards.bing.com/api/reportactivity?X-Requested-With=XMLHttpRequest",
            headers=headers,
            data=payload,
        )
        return 200 <= response.status_code < 400

    def enhance_mobile_cookie(self) -> str:
        cookie = self.account.cookie
        remove_patterns = [
            r"MicrosoftApplicationsTelemetryDeviceId=[^;]+",
            r"MicrosoftApplicationsTelemetryFirstLaunchTime=[^;]+",
            r"MSPTC=[^;]+",
            r"vdp=[^;]+",
        ]
        for pattern in remove_patterns:
            cookie = re.sub(pattern, "", cookie)
        cookie = re.sub(r";;+", ";", cookie).strip("; ")
        today = datetime.now().strftime("%Y%m%d")
        if "SRCHD=" not in cookie:
            cookie += "; SRCHD=AF=NOFORM"
        if "SRCHUSR=" in cookie:
            cookie = re.sub(r"SRCHUSR=[^;]+", f"SRCHUSR=DOB={today}&DS=1", cookie)
        else:
            cookie += f"; SRCHUSR=DOB={today}&DS=1"
        return cookie

    def perform_search(self, mobile: bool = False) -> bool:
        query = hot_words.random_word()
        headers = {
            "User-Agent": config.mobile_ua() if mobile else config.pc_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": config.accept_language(),
            "Referer": "https://rewards.bing.com/",
            "Cookie": self.enhance_mobile_cookie() if mobile else self.account.cookie,
        }
        if mobile:
            headers.update({"x-requested-with": "com.microsoft.bing", "x-search-market": "zh-CN"})
            params = {
                "q": query,
                "form": "NPII01",
                "ssp": "1",
                "safesearch": "moderate",
                "setlang": "zh-hans" if config.lang_code.startswith("zh") else "en-us",
                "cc": "CN" if config.geo_locale in ("cn", "zh-cn") else "US",
                "ensearch": "0",
                "PC": "SANSAAND",
            }
        else:
            params = {"q": query, "qs": "HS", "form": "TSASDS"}

        search_url = config.bing_search_url()
        response = self.request("GET", search_url, headers=headers, params=params, allow_redirects=False)
        if response.status_code in (301, 302, 303, 307, 308) or response.status_code != 200:
            search_url = "https://www.bing.com/search"
            response = self.request("GET", search_url, headers=headers, params=params)
        if response.status_code != 200:
            print_log("移动搜索" if mobile else "电脑搜索", f"搜索状态码 {response.status_code}", self.account.index)
            return False

        full_url = requests.Request("GET", search_url, headers=headers, params=params).prepare().url or search_url
        sleep_range(config.task_delay_min, config.task_delay_max)

        if mobile:
            report_url = "https://www.bing.com/rewardsapp/reportActivity" if "www.bing.com" in search_url else "https://cn.bing.com/rewardsapp/reportActivity"
            post_headers = {
                "User-Agent": headers["User-Agent"],
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "Cookie": headers["Cookie"],
                "Referer": config.bing_origin(search_url) + "/",
            }
        else:
            ig = self._extract_str(response.text, r'IG:"([^"]+)"')
            iid = self._extract_str(response.text, r'data_iid\s*=\s*"([^"]+)"')
            if ig and iid:
                report_url = f"{config.bing_origin(search_url)}/rewardsapp/reportActivity?IG={ig}&IID={iid}&q={quote(query)}&qs=HS&form=TSASDS&ajaxreq=1"
            else:
                report_url = f"{config.bing_origin(search_url)}/rewardsapp/reportActivity"
            post_headers = {
                "User-Agent": headers["User-Agent"],
                "Accept": "*/*",
                "Origin": config.bing_origin(search_url),
                "Referer": full_url,
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": self.account.cookie,
            }

        post_data = f"url={quote(full_url, safe='')}&V=web"
        report = self.request("POST", report_url, headers=post_headers, data=post_data)
        if report.status_code >= 400:
            print_log("移动搜索" if mobile else "电脑搜索", f"上报状态码 {report.status_code}", self.account.index)
        return True

    def get_access_token(self, refresh_token: str, silent: bool = False) -> Optional[str]:
        data = {
            "client_id": "0000000040170455",
            "refresh_token": refresh_token,
            "scope": "service::prod.rewardsplatform.microsoft.com::MBI_SSL",
            "grant_type": "refresh_token",
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": config.pc_ua(),
            "Accept": "*/*",
            "Origin": "https://login.live.com",
            "Referer": "https://login.live.com/oauth20_desktop.srf",
        }
        response = self.request("POST", "https://login.live.com/oauth20_token.srf", headers=headers, data=data)
        if response.status_code == 200:
            token_data = response.json()
            if token_data.get("refresh_token") and token_data["refresh_token"] != refresh_token:
                token_cache.save_token(self.account.alias, token_data["refresh_token"])
            return token_data.get("access_token")
        if not silent:
            print_log("阅读Token", f"获取失败，状态码 {response.status_code}", self.account.index)
        return None

    def get_read_progress(self, access_token: str) -> Tuple[int, int]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": config.mobile_ua(),
            "Accept-Encoding": "gzip",
            "x-rewards-partnerid": "startapp",
            "x-rewards-appid": "SAAndroid/32.2.430730002",
            "x-rewards-country": "cn",
            "x-rewards-language": "zh-hans",
            "x-rewards-flights": "rwgobig",
        }
        response = self.request(
            "GET",
            "https://prod.rewardsplatform.microsoft.com/dapi/me?channel=SAAndroid&options=613",
            headers=headers,
        )
        if response.status_code != 200:
            return 0, 30
        data = response.json()
        promotions = data.get("response", {}).get("promotions", []) or data.get("promotions", []) or []
        for item in promotions:
            offer_id = str(item.get("offerid") or item.get("offerId") or "")
            if "readarticle" in offer_id.lower():
                progress = int(item.get("progress", item.get("pointProgress", 0)) or 0)
                maximum = int(item.get("max", item.get("pointProgressMax", 30)) or 30)
                return progress, maximum
        return 0, 30

    def submit_read_activity(self, access_token: str) -> bool:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": config.mobile_ua(),
            "Content-Type": "application/json",
            "x-rewards-partnerid": "startapp",
            "x-rewards-appid": "SAAndroid/32.2.430730002",
            "x-rewards-country": "cn",
            "x-rewards-language": "zh-hans",
        }
        payload = {"amount": 1, "country": "cn", "id": "", "type": 101, "offerid": "ENUS_readarticle3_30points"}
        response = self.request(
            "POST",
            "https://prod.rewardsplatform.microsoft.com/dapi/me/activities",
            headers=headers,
            json_data=payload,
        )
        if response.status_code in (200, 201, 204):
            return True
        try:
            data = response.json()
            description = json.dumps(data, ensure_ascii=False).lower()
            return "already" in description
        except Exception:
            return False

    def complete_read_tasks(self, refresh_token: str) -> Tuple[int, int]:
        access_token = self.get_access_token(refresh_token)
        if not access_token:
            return 0, 30
        current, maximum = self.get_read_progress(access_token)
        if current >= maximum:
            return current, maximum
        attempts = max(0, maximum - current)
        for _ in range(attempts):
            if self.submit_read_activity(access_token):
                current += 1
            sleep_range(config.task_delay_min, config.task_delay_max)
            latest_current, latest_max = self.get_read_progress(access_token)
            current, maximum = max(current, latest_current), latest_max or maximum
            if current >= maximum:
                break
        return current, maximum


@dataclass
class AccountResult:
    index: int
    email: str
    success: bool
    start_points: int = 0
    final_points: int = 0
    today_points: int = 0
    daily: Tuple[int, int] = (0, 0)
    more: Tuple[int, int] = (0, 0)
    read: Tuple[int, int] = (0, 0)
    pc_search: Tuple[int, int] = (0, 0)
    mobile_search: Tuple[int, int] = (0, 0)
    message: str = ""

    def summary(self) -> str:
        status = "✅" if self.success else "❌"
        lines = [
            f"{status} 账号{self.index}: {mask_email(self.email)}",
            f"积分: {self.start_points} -> {self.final_points} (+{max(0, self.final_points - self.start_points)})",
            f"今日积分: {self.today_points}",
            f"每日活动: {self.daily[0]}/{self.daily[1]}",
            f"更多活动: {self.more[0]}/{self.more[1]}",
            f"阅读任务: {self.read[0]}/{self.read[1]}",
            f"PC搜索: {self.pc_search[0]}/{self.pc_search[1]}",
            f"移动搜索: {self.mobile_search[0]}/{self.mobile_search[1]}",
        ]
        if self.message:
            lines.append(f"说明: {self.message}")
        return "\n".join(lines)


class RewardsBot:
    def __init__(self) -> None:
        self.accounts = AccountManager.get_accounts()

    def run(self) -> List[AccountResult]:
        if not self.accounts:
            msg = "未找到有效账号，请配置 bing_ck_1 / MR_COOKIE_1 等 Cookie 变量。"
            print_log("账号配置", msg)
            notify_user("Microsoft Rewards 配置缺失", msg)
            return []

        print_log("账号配置", f"共发现 {len(self.accounts)} 个账号")
        max_workers = max(1, min(config.max_workers, len(self.accounts)))
        print_log("并发配置", f"账号并发数: {max_workers}/{len(self.accounts)}")

        results: List[AccountResult] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.process_account, account) for account in self.accounts]
            for future in as_completed(futures):
                results.append(future.result())

        results.sort(key=lambda item: item.index)
        content = "\n\n".join(result.summary() for result in results)
        title = f"Microsoft Rewards 任务总结 ({date.today().strftime('%Y-%m-%d')})"
        notify_user(title, content)
        print("\n" + "=" * 17 + " [全部任务完成] " + "=" * 17)
        print(content)
        return results

    def process_account(self, account: AccountInfo) -> AccountResult:
        client = RewardsClient(account)
        try:
            print_log("账号开始", "开始处理", account.index)
            home = client.get_home_info()
            if not home:
                return AccountResult(index=account.index, email=account.alias, success=False, message="Cookie 失效或无法获取账号信息")

            email = home["email"]
            start_points = int(home["points"])
            token = home.get("token") or ""
            print_log("账号信息", f"{mask_email(email)} 当前积分 {start_points}", account.index)

            read = (0, 0)
            if config.do_read_tasks:
                refresh_token = self.resolve_refresh_token(account)
                if refresh_token:
                    read = client.complete_read_tasks(refresh_token)
                    print_log("阅读任务", f"{read[0]}/{read[1]}", account.index)
                else:
                    print_log("阅读任务", "未配置 refresh_token，跳过", account.index)
            else:
                print_log("阅读任务", "已关闭", account.index)

            daily = (0, 0)
            if config.do_daily_set and token:
                daily = client.complete_daily_set(token)
                print_log("每日活动", f"{daily[0]}/{daily[1]}", account.index)
            elif not config.do_daily_set:
                print_log("每日活动", "已关闭", account.index)
            else:
                print_log("每日活动", "缺少 RequestVerificationToken，跳过", account.index)

            more = (0, 0)
            if config.do_more_promotions and token:
                more = client.complete_more_promotions(token)
                print_log("更多活动", f"{more[0]}/{more[1]}", account.index)
            elif not config.do_more_promotions:
                print_log("更多活动", "已关闭", account.index)
            else:
                print_log("更多活动", "缺少 RequestVerificationToken，跳过", account.index)

            self.perform_search_tasks(client)

            final_home = client.get_home_info() or home
            final_dashboard = client.get_dashboard(silent=True)
            pc = client.search_status(final_dashboard, "pcSearch")[:2]
            mobile = client.search_status(final_dashboard, "mobileSearch")[:2]
            return AccountResult(
                index=account.index,
                email=email,
                success=True,
                start_points=start_points,
                final_points=int(final_home.get("points", start_points)),
                today_points=client.today_earned(final_dashboard),
                daily=daily,
                more=more,
                read=read,
                pc_search=pc,
                mobile_search=mobile,
            )
        except Exception as exc:
            print_log("账号错误", f"{exc}\n{traceback.format_exc()}", account.index)
            return AccountResult(index=account.index, email=account.alias, success=False, message=str(exc))
        finally:
            client.close()

    def resolve_refresh_token(self, account: AccountInfo) -> str:
        cache = token_cache.load()
        return cache.get(account.alias) or account.refresh_token

    def perform_search_tasks(self, client: RewardsClient) -> None:
        dashboard = client.get_dashboard()
        level = client.account_level(dashboard)

        if config.do_pc_search:
            self.perform_one_search_type(client, "pcSearch", mobile=False)
        else:
            print_log("电脑搜索", "已关闭", client.account.index)

        if config.do_mobile_search:
            if level == "Level1":
                print_log("移动搜索", "1级账号无此任务，跳过", client.account.index)
            else:
                self.perform_one_search_type(client, "mobileSearch", mobile=True)
        else:
            print_log("移动搜索", "已关闭", client.account.index)

    def perform_one_search_type(self, client: RewardsClient, search_type: str, mobile: bool) -> None:
        label = "移动搜索" if mobile else "电脑搜索"
        dashboard = client.get_dashboard()
        current, maximum, complete = client.search_status(dashboard, search_type)
        if complete and not config.run_on_zero_searches:
            print_log(label, f"已完成 ({current}/{maximum})", client.account.index)
            return
        needed_points = max(0, maximum - current)
        needed = max(1 if config.run_on_zero_searches else 0, (needed_points + 2) // 3)
        attempts = max(config.search_batch_size, needed)
        print_log(label, f"开始执行，当前 {current}/{maximum}，计划最多 {attempts} 次", client.account.index)
        for attempt in range(1, attempts + 1):
            if client.perform_search(mobile=mobile):
                delay = random.randint(config.search_delay_min, config.search_delay_max)
                print_log(label, f"第 {attempt}/{attempts} 次完成，等待 {delay}s", client.account.index)
                time.sleep(delay)
            else:
                print_log(label, f"第 {attempt}/{attempts} 次失败", client.account.index)

            dashboard = client.get_dashboard(silent=True)
            current, maximum, complete = client.search_status(dashboard, search_type)
            if complete:
                print_log(label, f"已完成 ({current}/{maximum})", client.account.index)
                break


def print_config() -> None:
    print(
        "配置: "
        f"并发={config.max_workers}, "
        f"阅读={'开' if config.do_read_tasks else '关'}, "
        f"每日活动={'开' if config.do_daily_set else '关'}, "
        f"更多活动={'开' if config.do_more_promotions else '关'}, "
        f"PC搜索={'开' if config.do_pc_search else '关'}, "
        f"移动搜索={'开' if config.do_mobile_search else '关'}, "
        f"Bing={config.bing_host}, "
        f"热搜源={','.join(config.query_engines)}"
    )


def main() -> int:
    print(f"==== 微软积分签到开始 - {now_text()} ====")
    print_config()

    if config.random_signin and config.max_random_delay > 0:
        delay = random.randint(0, config.max_random_delay)
        if delay > 0:
            wait_with_countdown(delay)

    RewardsBot().run()
    print(f"==== 微软积分签到完成 - {now_text()} ====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
