#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
cron "13 8 * * *" script-path=quark_punch.py,tag=夸克签到
new Env('夸克签到')
"""
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import unquote, urlparse

import requests

# ---------------- 统一通知模块加载 ----------------
hadsend = False
send = None
try:
    from ql_notify import send
    hadsend = True
    print("✅ 已加载notify.py通知模块")
except ImportError:
    print("⚠️  未加载通知模块，跳过通知功能")

# ---------------- 常量 ----------------
INFO_URL = "https://drive-m.quark.cn/1/clouddrive/capacity/growth/info"
SIGN_URL = "https://drive-m.quark.cn/1/clouddrive/capacity/growth/sign"
REQUIRED_PARAMS = ("kps", "sign", "vcode")
DEFAULT_TIMEOUT = 15
MAX_GET_ATTEMPTS = 3
RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
# 接口在「今天已经签过」时会返回业务错误码，这种提示按成功处理
ALREADY_SIGNED_PATTERN = re.compile(r"已经签|已签到|重复签|already\s*signed", re.I)

# 随机延迟配置
try:
    max_random_delay = int(os.getenv("MAX_RANDOM_DELAY", "3600"))
except ValueError:
    max_random_delay = 3600
random_signin = os.getenv("RANDOM_SIGNIN", "true").lower() == "true"


class ConfigError(ValueError):
    """COOKIE_QUARK 缺失或格式不正确。"""


class QuarkAPIError(RuntimeError):
    """夸克接口无法完成签到操作。"""


def format_time_remaining(seconds):
    """格式化时间显示"""
    if seconds <= 0:
        return "立即执行"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}小时{minutes}分{secs}秒"
    elif minutes > 0:
        return f"{minutes}分{secs}秒"
    else:
        return f"{secs}秒"


def wait_with_countdown(delay_seconds):
    """带倒计时的等待"""
    if delay_seconds <= 0:
        return

    print(f"夸克签到需要等待 {format_time_remaining(delay_seconds)}")

    remaining = delay_seconds
    while remaining > 0:
        if remaining <= 10 or remaining % 10 == 0:
            print(f"倒计时: {format_time_remaining(remaining)}")

        sleep_time = 1 if remaining <= 10 else min(10, remaining)
        time.sleep(sleep_time)
        remaining -= sleep_time


def Push(title, message):
    """推送结果；通知模块缺失时退化为控制台输出。"""
    if hadsend:
        try:
            send(title, message)
            print("📨 已提交通知")
        except Exception as e:
            print(f"❌ notify.py推送失败: {e}")
    else:
        print(f"📢 {title}")
        print(f"📄 {message}")


def split_account_entries(raw_value):
    """把 COOKIE_QUARK 拆成多个账号条目，忽略空行。"""
    if not raw_value or not raw_value.strip():
        raise ConfigError("未添加 COOKIE_QUARK 变量，或变量内容为空")

    entries = [entry.strip() for entry in re.split(r"\r?\n|&&", raw_value)]
    entries = [entry for entry in entries if entry]
    if not entries:
        raise ConfigError("COOKIE_QUARK 中没有可用的账号配置")
    return entries


def extract_params(url):
    """从抓包 URL 中提取 kps/sign/vcode。

    夸克凭证里可能包含字面量 ``+``，而 parse_qs 会按 x-www-form-urlencoded
    语义把 ``+`` 当成空格，导致解析出的凭证失效。这里自行切分 query，只做
    百分号解码。
    """
    query = {}
    for part in urlparse(url.strip()).query.split("&"):
        if not part:
            continue
        key, separator, value = part.partition("=")
        if not separator:
            value = ""
        key = unquote(key)
        if key not in query:  # 同名参数取第一个，与浏览器行为一致
            query[key] = unquote(value)

    return {name: query.get(name, "") for name in REQUIRED_PARAMS}


def parse_account(entry, index):
    """解析并校验单个账号条目。"""
    account = {}
    for field in entry.split(";"):
        field = field.strip()
        if not field:
            continue
        if "=" not in field:
            raise ConfigError(f"第 {index} 个账号存在无效字段：{field}")
        key, value = field.split("=", 1)
        key = key.strip()
        if not key:
            raise ConfigError(f"第 {index} 个账号存在空字段名")
        account[key] = value.strip()

    if "url" in account:
        for key, value in extract_params(account["url"]).items():
            account.setdefault(key, value)

    missing = [key for key in REQUIRED_PARAMS if not account.get(key)]
    if missing:
        raise ConfigError(f"第 {index} 个账号缺少必要参数：{', '.join(missing)}")

    account.setdefault("user", f"账号{index}")
    return account


def _api_error_message(payload, fallback):
    message = payload.get("message") or payload.get("msg")
    code = payload.get("code")
    if message:
        return str(message)
    if code is not None:
        return f"{fallback}（code={code}）"
    return fallback


class Quark:
    """夸克移动端成长接口的最小封装。"""

    def __init__(self, account, session=None, timeout=DEFAULT_TIMEOUT, dry_run=False):
        self.account = account
        self.session = session or requests.Session()
        self.timeout = timeout
        self.dry_run = dry_run

    @staticmethod
    def convert_bytes(value):
        """将字节转换为 B/KB/MB/GB/TB"""
        units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        size = float(value)
        index = 0
        while size >= 1024 and index < len(units) - 1:
            size /= 1024
            index += 1
        return f"{size:.2f} {units[index]}"

    def _params(self):
        params = {
            "pr": "ucpro",
            "fr": "android",
        }
        params.update({key: self.account[key] for key in REQUIRED_PARAMS})
        return params

    def _request(self, method, url, **kwargs):
        """带重试的请求；GET 遇到网络错误与可重试状态码会退避重试。"""
        stage = "查询签到状态" if method == "GET" else "提交签到"
        attempts = MAX_GET_ATTEMPTS if method == "GET" else 1

        for attempt in range(1, attempts + 1):
            try:
                response = self.session.request(
                    method, url, timeout=self.timeout, **kwargs
                )
                response.raise_for_status()
                payload = response.json()
            except (requests.Timeout, requests.ConnectionError) as exc:
                print(f"⚠️ {stage}第 {attempt}/{attempts} 次网络失败：{type(exc).__name__}")
                if attempt >= attempts:
                    raise QuarkAPIError(f"{stage}网络失败（{type(exc).__name__}）") from exc
                time.sleep(2 ** (attempt - 1) + random.uniform(0, 1))
                continue
            except requests.RequestException as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if attempt < attempts and status in RETRYABLE_STATUS:
                    print(f"⚠️ {stage}返回 HTTP {status}，第 {attempt} 次重试")
                    time.sleep(2 ** (attempt - 1) + random.uniform(0, 1))
                    continue
                raise QuarkAPIError(f"{stage}请求失败（HTTP {status or 'unknown'}）") from exc
            except ValueError as exc:  # response.json() 解析失败
                raise QuarkAPIError(f"{stage}返回了无法解析的数据") from exc

            if not isinstance(payload, dict):
                raise QuarkAPIError(f"{stage}返回格式异常")
            return payload

        raise QuarkAPIError(f"{stage}重试次数已用尽")

    def get_growth_info(self):
        """获取用户当前的签到信息"""
        payload = self._request("GET", INFO_URL, params=self._params())
        data = payload.get("data")
        if not isinstance(data, dict):
            raise QuarkAPIError(_api_error_message(payload, "获取成长信息失败"))
        return data

    def get_growth_sign(self):
        """提交签到；返回奖励字节数，「今天已签过」时返回 None。"""
        payload = self._request(
            "POST", SIGN_URL, params=self._params(), json={"sign_cyclic": True}
        )
        data = payload.get("data")
        if isinstance(data, dict) and "sign_daily_reward" in data:
            return data["sign_daily_reward"]

        message = _api_error_message(payload, "签到失败")
        if ALREADY_SIGNED_PATTERN.search(message):
            print(f"ℹ️ 接口提示：{message}")
            return None
        raise QuarkAPIError(message)

    def do_sign(self):
        """执行签到任务，返回一段可直接推送的文本。"""
        growth_info = self.get_growth_info()
        cap_sign = growth_info.get("cap_sign")
        if not isinstance(cap_sign, dict):
            raise QuarkAPIError("成长信息中缺少 cap_sign 字段")

        composition = growth_info.get("cap_composition") or {}
        progress = cap_sign.get("sign_progress", "?")
        target = cap_sign.get("sign_target", "?")

        lines = [
            f"🙍🏻‍♂️ {'88VIP' if growth_info.get('88VIP') else '普通用户'} {self.account['user']}",
            f"💾 网盘总容量：{self.convert_bytes(growth_info.get('total_capacity', 0))}，"
            f"签到累计容量：{self.convert_bytes(composition.get('sign_reward', 0))}",
        ]

        if cap_sign.get("sign_daily"):
            lines.append(
                f"✅ 签到日志: 今日已签到+{self.convert_bytes(cap_sign.get('sign_daily_reward', 0))}，"
                f"连签进度({progress}/{target})"
            )
            return "\n".join(lines)

        if self.dry_run:
            lines.append("🧪 DRY_RUN：凭证有效，今日尚未签到（已跳过实际签到）")
            return "\n".join(lines)

        try:
            reward = self.get_growth_sign()
        except QuarkAPIError as exc:
            if "网络失败" not in str(exc):
                raise
            # POST 已经发出但结果未知，复查一次状态，避免误报失败或重复签到
            print("⚠️ 签到结果不确定，重新查询签到状态")
            verified = self.get_growth_info().get("cap_sign") or {}
            if not verified.get("sign_daily"):
                raise QuarkAPIError("未确认签到成功，请稍后重试") from exc
            lines.append(
                f"✅ 复查确认今日已签到+{self.convert_bytes(verified.get('sign_daily_reward', 0))}"
            )
            return "\n".join(lines)

        if reward is None:
            lines.append(f"✅ 今日已签到（接口提示重复签到），连签进度({progress}/{target})")
        else:
            next_progress = progress + 1 if isinstance(progress, int) else "?"
            lines.append(
                f"✅ 执行签到: 今日签到+{self.convert_bytes(reward)}，"
                f"连签进度({next_progress}/{target})"
            )
        return "\n".join(lines)


def main():
    """主函数，返回青龙任务退出码（0 全部成功 / 1 有失败 / 2 配置错误）。"""
    print("----------夸克网盘开始签到----------")

    try:
        cookie_quark = split_account_entries(os.getenv("COOKIE_QUARK"))
    except ConfigError as exc:
        print(f"❌ {exc}")
        Push("夸克自动签到", f"❌ {exc}")
        return 2

    dry_run = os.getenv("QUARK_DRY_RUN", os.getenv("DRY_RUN", "")).lower() in (
        "1",
        "true",
        "yes",
    )

    print(f"✅ 检测到共 {len(cookie_quark)} 个夸克账号\n")

    results = []
    failures = 0

    for index, entry in enumerate(cookie_quark, start=1):
        try:
            account = parse_account(entry, index)
            results.append(Quark(account, dry_run=dry_run).do_sign())
        except (ConfigError, QuarkAPIError) as exc:
            failures += 1
            results.append(f"🙍🏻‍♂️ 第 {index} 个账号\n❌ 该账号签到失败: {exc}")
        except Exception as exc:  # 兜底：保证后续账号继续执行
            failures += 1
            results.append(
                f"🙍🏻‍♂️ 第 {index} 个账号\n❌ 未知错误: {type(exc).__name__}: {exc}"
            )

    msg = "\n\n".join(results)
    print("\n" + msg + "\n")

    try:
        Push("夸克自动签到", msg)
    except Exception as err:
        print("%s\n❌ 推送错误，请查看运行日志！" % err)

    succeeded = len(cookie_quark) - failures
    print(f"----------夸克网盘签到完毕：成功 {succeeded}，失败 {failures}----------")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    print(f"==== 夸克网盘签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")

    # 随机延迟（可选）
    if random_signin and max_random_delay > 0:
        delay_seconds = random.randint(0, max_random_delay)
        if delay_seconds > 0:
            signin_time = datetime.now() + timedelta(seconds=delay_seconds)
            print(f"随机模式: 延迟 {format_time_remaining(delay_seconds)} 后签到")
            print(f"预计签到时间: {signin_time.strftime('%H:%M:%S')}")
            wait_with_countdown(delay_seconds)

    exit_code = main()
    print(f"==== 夸克签到完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    sys.exit(exit_code)
