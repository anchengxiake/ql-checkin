#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
老王论坛自动签到脚本 v4.1
支持三种模式：
1. 账号密码登录模式（推荐）：自动登录获取 Cookie 并签到
2. Cookie 模式：使用已有 Cookie 签到
3. 浏览器模式（备选）：处理滑块验证

cron: 0 9 * * *
new Env('老王论坛签到')
"""

import os
import re
import sys
import time
import random
import json
import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, parse_qs

# 日志配置
logging.basicConfig(
    level=logging.DEBUG if os.getenv('LAOWANG_DEBUG', 'false').lower() == 'true' else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============ 配置常量 ============
# 自定义域名解析（当 DNS 被污染时使用）
CUSTOM_HOST = os.getenv('LAOWANG_CUSTOM_HOST', '')  # 例如: 104.21.47.182

if CUSTOM_HOST:
    # 使用自定义 IP + Host 头
    BASE_URL = f"https://{CUSTOM_HOST}"
    logger.info(f"🌐 使用自定义域名解析: {CUSTOM_HOST}")
else:
    BASE_URL = "https://laowang.vip"

LOGIN_URL = f"{BASE_URL}/member.php?mod=logging&action=login"
SIGN_PAGE_URL = f"{BASE_URL}/plugin.php?id=k_misign:sign"
SIGN_API_URL = f"{BASE_URL}/plugin.php?id=k_misign:sign&operation=qiandao&format=button_inajax"

# 请求重试配置
MAX_RETRIES = 3
RETRY_DELAY = 5

# SSL 验证配置（遇到证书问题时设为 false）
VERIFY_SSL = os.getenv('LAOWANG_VERIFY_SSL', 'true').lower() != 'false'

# 调试模式（开启后显示详细日志）
DEBUG_MODE = os.getenv('LAOWANG_DEBUG', 'false').lower() == 'true'

# 浏览器模式（账号密码登录时自动处理滑块）
# auto = 自动检测（优先用浏览器模式），true = 强制使用，false = 禁用
BROWSER_MODE = os.getenv('LAOWANG_BROWSER_MODE', 'auto').lower()

# ============ 通知模块 ============
notify = None
try:
    from notify import send
    notify = send
    logger.info("✅ 已加载 notify 通知模块")
except ImportError:
    logger.warning("⚠️ 未加载通知模块")

def push_notify(title, message):
    """推送通知"""
    if notify:
        try:
            notify(title, message)
        except Exception as e:
            logger.error(f"推送失败: {e}")

# ============ 代理配置 ============
def get_proxies():
    """获取代理配置"""
    proxy = os.getenv('LAOWANG_PROXY') or os.getenv('MY_PROXY', '')
    if proxy:
        return {'http': proxy, 'https': proxy}
    return None

# ============ 时间工具 ============
def format_time_remaining(seconds):
    """格式化剩余时间"""
    if seconds <= 0:
        return "立即执行"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}小时{minutes}分{secs}秒"
    elif minutes > 0:
        return f"{minutes}分{secs}秒"
    return f"{secs}秒"

def wait_countdown(seconds, task_name="签到"):
    """带倒计时的等待"""
    if seconds <= 0:
        return
    print(f"⏳ {task_name}将在 {format_time_remaining(seconds)} 后开始")
    remaining = seconds
    while remaining > 0:
        if remaining <= 10 or remaining % 30 == 0:
            print(f"⏳ 倒计时: {format_time_remaining(remaining)}")
        sleep_time = 1 if remaining <= 10 else min(30, remaining)
        time.sleep(sleep_time)
        remaining -= sleep_time

# ============ 响应解析工具 ============
def parse_ajax_response(resp_text):
    """
    解析 Discuz! AJAX 响应，提取 CDATA 中的真实文本
    返回: (is_success, message, raw_text)
    """
    raw = resp_text.strip()

    # 调试模式打印原始响应
    if DEBUG_MODE:
        logger.debug(f"[AJAX原始响应] {raw[:500]}")

    # 尝试提取 CDATA 内容
    cdata_match = re.search(r'<!\[CDATA\[(.*?)\]\]>', raw, re.DOTALL)
    if cdata_match:
        msg = cdata_match.group(1).strip()
        # 移除 HTML 标签
        msg_clean = re.sub(r'<[^>]+>', '', msg).strip()

        # 判断真正的成功标志（基于 CDATA 内部内容）
        # 注意：这些是子串匹配，关键词要足够精确避免误判
        success_keywords = ['签到成功', '恭喜您', '已获得奖励', '签到奖励']
        already_keywords = ['已经签到', '今日已签', '已签到', '请勿重复']
        # 必须是明确的失败标识，不要包含太宽泛的词（如单独的"登录"会误匹配"登录成功"）
        fail_keywords = ['请先登录', '登录后', '需要登录', '登录失败', '密码错误',
                        '表单错误', '验证失败', '无权', '已过期', '已失效', 'Cookie']

        # 优先检查明确的已签到标志
        if any(k in msg_clean for k in already_keywords):
            return True, f"已签到 ({msg_clean})", raw

        # 再检查明确的失败标志
        if any(k in msg_clean for k in fail_keywords):
            return False, f"签到失败: {msg_clean}", raw

        # 检查成功标志
        if any(k in msg_clean for k in success_keywords):
            return True, f"签到成功 ({msg_clean})", raw

        # CDATA 内容不命中任何已知关键词，输出供调试
        logger.warning(f"未知的CDATA响应: {msg_clean[:200]}")
        return False, f"未知响应: {msg_clean[:100]}", raw

    # 非 CDATA 响应
    if not raw:
        return False, "空响应", raw

    # 太短的响应不可能是成功（Discuz! 的成功响应通常 > 50 字符）
    if len(raw) < 10:
        return False, f"响应过短（{len(raw)} 字节）", raw

    # 检查 HTTP 页面（说明服务器返回了错误页）
    if raw.startswith('<!DOCTYPE') or raw.startswith('<html'):
        return False, "返回 HTML 页面而非 AJAX 数据", raw

    # 检查 HTTP 错误状态码常见标记
    if any(k in raw.lower() for k in ['error', '503', '502', '404', '403']):
        if len(raw) < 200:  # 简短错误响应
            return False, f"服务器错误: {raw[:100]}", raw

    return False, f"非标准响应: {raw[:100]}", raw


# ============ 请求工具（带重试） ============
def request_with_retry(session, method, url, **kwargs):
    """带重试的请求"""
    import requests
    import urllib3

    # 禁用 SSL 警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # 默认超时
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 30

    # 如果使用自定义域名解析，完全禁用 SSL 验证（由 session 的 adapter 处理）
    # 否则根据 VERIFY_SSL 设置
    if CUSTOM_HOST:
        kwargs['verify'] = False
    elif 'verify' not in kwargs:
        kwargs['verify'] = VERIFY_SSL

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            if method == 'get':
                response = session.get(url, **kwargs)
            else:
                response = session.post(url, **kwargs)
            return response
        except requests.exceptions.ProxyError as e:
            last_error = f"代理错误: {str(e)[:100]}"
            logger.warning(f"请求失败 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")
        except requests.exceptions.Timeout:
            last_error = "请求超时"
            logger.warning(f"请求超时 (尝试 {attempt+1}/{MAX_RETRIES})")
        except requests.exceptions.ConnectionError as e:
            error_str = str(e)
            # 更详细的错误分析
            if 'SSL' in error_str or 'TLS' in error_str or 'CERTIFICATE' in error_str:
                last_error = f"SSL/TLS证书错误: {error_str[:100]}"
                logger.warning(f"SSL错误 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")
                if attempt == 0:
                    logger.info("💡 提示: 可尝试设置 LAOWANG_VERIFY_SSL=false 跳过证书验证")
            elif 'Name or service not known' in error_str or 'getaddrinfo' in error_str:
                last_error = f"DNS解析失败: {error_str[:100]}"
                logger.warning(f"DNS错误 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")
            else:
                last_error = f"连接错误: {error_str[:100]}"
                logger.warning(f"连接失败 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")
        except requests.exceptions.SSLError as e:
            last_error = f"SSL错误: {str(e)[:100]}"
            logger.warning(f"SSL错误 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")
            if attempt == 0:
                logger.info("💡 提示: 可尝试设置 LAOWANG_VERIFY_SSL=false 跳过证书验证")
        except Exception as e:
            last_error = f"请求异常: {str(e)[:100]}"
            logger.warning(f"请求异常 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")

        if attempt < MAX_RETRIES - 1:
            sleep_time = RETRY_DELAY * (attempt + 1)
            logger.info(f"⏳ {sleep_time}秒后重试...")
            time.sleep(sleep_time)

    raise Exception(f"请求失败 ({MAX_RETRIES}次重试): {last_error}")


def test_connection():
    """测试网络连接"""
    import socket
    import ssl

    logger.info("🔍 测试网络连接...")

    # 1. DNS 解析测试
    try:
        ip = socket.gethostbyname('laowang.vip')
        logger.info(f"✅ DNS解析: laowang.vip -> {ip}")
        if ip == '0.0.0.0' or ip.startswith('127.'):
            logger.warning(f"⚠️ DNS解析到无效IP: {ip}，建议设置 LAOWANG_CUSTOM_HOST")
    except Exception as e:
        logger.error(f"❌ DNS解析失败: {e}")

    # 2. TCP 连接测试（使用自定义IP或域名）
    test_host = CUSTOM_HOST if CUSTOM_HOST else 'laowang.vip'
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((test_host, 443))
        if result == 0:
            logger.info(f"✅ TCP连接: {test_host}:443 连接成功")
        else:
            logger.error(f"❌ TCP连接: {test_host}:443 连接失败 (错误码: {result})")
        sock.close()
    except Exception as e:
        logger.error(f"❌ TCP连接测试失败: {e}")

    # 3. HTTPS 测试
    try:
        import requests
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})

        proxies = get_proxies()
        if proxies:
            session.proxies.update(proxies)

        # 使用当前配置测试
        logger.info(f"🔒 测试HTTPS连接: {BASE_URL}...")
        response = session.get(
            BASE_URL,
            timeout=10,
            verify=False,
            proxies=proxies
        )
        logger.info(f"✅ HTTPS连接成功: HTTP {response.status_code}")
        return True

    except Exception as e:
        logger.error(f"❌ HTTPS测试失败: {e}")
        return False


def find_working_ip():
    """尝试多个候选IP找到可用的"""
    import requests

    # 候选IP列表（已验证可用的 IP 优先）
    candidate_ips = [
        '172.67.158.164',   # 用户验证可用
        '104.21.14.105',    # 用户验证可用
        '172.64.35.25',     # 用户验证可用
        '104.21.15.106',
        '172.67.175.25',
        '172.67.176.26',
        '104.21.16.107',
        '104.21.17.108',
    ]

    # 如果用户指定了 IP，优先测试
    if CUSTOM_HOST and CUSTOM_HOST not in candidate_ips:
        candidate_ips.insert(0, CUSTOM_HOST)

    logger.info("🔍 正在寻找可用的 IP...")

    for ip in candidate_ips:
        try:
            logger.debug(f"  测试 IP: {ip}")
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0',
                'Host': 'laowang.vip'
            })

            proxies = get_proxies()
            if proxies:
                session.proxies.update(proxies)

            response = session.get(
                f"https://{ip}",
                timeout=5,
                verify=False,
                proxies=proxies
            )

            if response.status_code == 200 or response.status_code == 403:
                logger.info(f"✅ 找到可用 IP: {ip}")
                return ip

        except Exception as e:
            logger.debug(f"  IP {ip} 不可用: {e}")
            continue

    return None

# ============ 账号密码登录模式 ============
class LaowangLoginSign:
    """账号密码登录签到模式"""

    def __init__(self, username, password, index=1):
        self.username = username
        self.password = password
        self.index = index
        self.session = self._create_session()
        self.display_name = username

    def _create_session(self):
        """创建请求会话"""
        import requests
        import urllib3
        from requests.adapters import HTTPAdapter

        # 完全禁用 SSL 的 Adapter - 终极方案
        class NoVerifyHTTPAdapter(HTTPAdapter):
            def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
                from urllib3.poolmanager import PoolManager
                pool_kwargs['cert_reqs'] = 'CERT_NONE'
                pool_kwargs['assert_hostname'] = False
                pool_kwargs['assert_fingerprint'] = None
                return PoolManager(connections, maxsize, block, **pool_kwargs)

        session = requests.Session()

        # 如果使用自定义域名解析，使用完全禁用 SSL 的 Adapter
        if CUSTOM_HOST:
            session.mount('https://', NoVerifyHTTPAdapter())
            logger.info("🔒 使用 NoVerifyHTTPAdapter（完全禁用 SSL）")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'identity',  # 禁用压缩，避免乱码
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        # 如果使用自定义域名解析，需要设置 Host 头
        if CUSTOM_HOST:
            headers['Host'] = 'laowang.vip'
            logger.info(f"🌐 设置 Host 头: laowang.vip -> {CUSTOM_HOST}")

        session.headers.update(headers)

        # 设置代理
        proxies = get_proxies()
        if proxies:
            session.proxies.update(proxies)
            logger.info(f"🌐 使用代理: {proxies['http']}")

        # 完全禁用 SSL 验证和警告
        session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        return session

    def login(self):
        """登录获取 Cookie"""
        import requests

        try:
            logger.info(f"🔐 正在登录: {self.username}")

            # 1. 获取登录页面提取 formhash
            logger.info("📄 获取登录页面...")
            response = request_with_retry(self.session, 'get', LOGIN_URL)
            response.encoding = 'utf-8'

            # 调试：输出页面内容前 1000 字符
            if DEBUG_MODE:
                logger.debug(f"登录页面内容: {response.text[:1000]}")

            # 提取 formhash（多种模式尝试）
            formhash_match = None
            formhash_patterns = [
                r'name="formhash" value="([a-f0-9]{8})"',
                r'formhash=([a-f0-9]{8})',
                r'<input[^>]*name=["\']formhash["\'][^>]*value=["\']([a-f0-9]{8})["\']',
                r'value="([a-f0-9]{8})"[^>]*name="formhash"',
            ]

            for pattern in formhash_patterns:
                formhash_match = re.search(pattern, response.text)
                if formhash_match:
                    logger.debug(f"使用模式提取 formhash: {pattern}")
                    break

            if not formhash_match:
                # 检查是否已经是登录状态
                if 'member.php?mod=logging&action=logout' in response.text:
                    logger.info("✅ 已经是登录状态")
                    # 提取用户名
                    username_match = re.search(r'title="访问我的空间">([^<]+)</a>', response.text)
                    if username_match:
                        self.display_name = username_match.group(1).strip()
                    return True, "已经是登录状态"

                if DEBUG_MODE:
                    logger.error(f"页面内容（前2000字符）: {response.text[:2000]}")
                return False, "未找到 formhash，登录失败"

            formhash = formhash_match.group(1)
            logger.info(f"✅ 获取 formhash: {formhash}")

            # 2. 提交登录
            login_data = {
                'formhash': formhash,
                'referer': BASE_URL,
                'username': self.username,
                'password': self.password,
                'questionid': '0',
                'answer': '',
                'cookietime': '2592000',  # 30天
            }

            logger.info("🔑 提交登录...")
            response = request_with_retry(
                self.session, 'post', LOGIN_URL,
                data=login_data,
                headers={'Referer': LOGIN_URL}
            )
            response.encoding = 'utf-8'

            # 检查登录结果
            if '登录失败' in response.text:
                # 提取错误信息
                error_match = re.search(r'<div[^>]*class="[^"]*alert_error[^"]*"[^>]*>(.*?)</div>', response.text, re.DOTALL)
                if error_match:
                    error_msg = re.sub(r'<[^>]+>', '', error_match.group(1)).strip()
                    return False, f"登录失败: {error_msg}"
                return False, "登录失败: 用户名或密码错误"

            if '登录' in response.text and '密码' in response.text:
                return False, "登录失败，请检查账号密码"

            # 3. 验证登录成功
            logger.info("✅ 验证登录状态...")
            time.sleep(2)

            response = request_with_retry(self.session, 'get', BASE_URL)
            response.encoding = 'utf-8'

            # 检查是否已登录：看是否有退出链接或用户空间链接
            has_logout = 'member.php?mod=logging&action=logout' in response.text
            has_userlink = re.search(r'title="访问我的空间">([^<]+)</a>', response.text) is not None

            if not has_logout and not has_userlink:
                # 页面仍然显示登录/注册入口，说明没登录成功
                if '登录' in response.text and '立即注册' in response.text:
                    return False, "登录失败，页面仍显示未登录状态"

            # 提取显示用户名
            username_match = re.search(r'title="访问我的空间">([^<]+)</a>', response.text)
            if username_match:
                self.display_name = username_match.group(1).strip()

            logger.info(f"✅ 登录成功: {self.display_name}")
            return True, "登录成功"

        except Exception as e:
            return False, f"登录异常: {str(e)[:150]}"

    def get_sign_status(self):
        """获取签到状态"""
        try:
            response = request_with_retry(self.session, 'get', SIGN_PAGE_URL)
            response.encoding = 'utf-8'
            html = response.text

            # 提取统计信息
            stats = self._extract_stats(html)

            # 检查已签到
            if any(x in html for x in ['btnvisted', '已签到', '今日已签', '今日已领']):
                return 'already_signed', stats

            # 检查可签到
            if any(x in html for x in ['qiandao', '签到', 'J_chkitot']):
                sign_url = self._extract_sign_url(html)
                return 'can_sign', sign_url

            # 检查登录状态
            if '登录' in html and '注册' in html and '立即注册' in html:
                if 'member.php?mod=logging&action=logout' not in html:
                    return 'not_logged_in', None

            return 'unknown', None

        except Exception as e:
            return 'error', str(e)

    def _extract_stats(self, html):
        """提取签到统计信息"""
        stats = {}

        # 从 input 隐藏字段提取
        patterns = {
            'lxdays': r'<input[^>]*id=["\']lxdays["\'][^>]*value=["\'](\d+)["\']',
            'lxlevel': r'<input[^>]*id=["\']lxlevel["\'][^>]*value=["\'](\d+)["\']',
            'lxreward': r'<input[^>]*id=["\']lxreward["\'][^>]*value=["\']([^"\']+)["\']',
            'lxtdays': r'<input[^>]*id=["\']lxtdays["\'][^>]*value=["\'](\d+)["\']',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, html)
            if match:
                stats[key] = match.group(1)

        return stats

    def _extract_sign_url(self, html):
        """提取签到链接"""
        # 从按钮 onclick 中提取
        onclick_pattern = r'<a[^>]*onclick=["\'][^"\']*?(plugin\.php\?id=k_misign:sign[^"\']+)["\']'
        match = re.search(onclick_pattern, html)
        if match:
            url = match.group(1)
            if not url.startswith('http'):
                url = urljoin(BASE_URL, url)
            return url

        # 从 href 中提取
        href_pattern = r'href=["\']([^"\']*operation=qiandao[^"\']*)["\']'
        match = re.search(href_pattern, html)
        if match:
            url = match.group(1)
            if not url.startswith('http'):
                url = urljoin(BASE_URL, url)
            return url

        return SIGN_API_URL

    def do_sign(self):
        """执行签到"""
        # 1. 登录
        success, msg = self.login()
        if not success:
            return False, f"❌ {self.username}: {msg}"

        # 2. 获取签到状态
        logger.info("📋 检查签到状态...")
        time.sleep(2)

        status, data = self.get_sign_status()

        if status == 'not_logged_in':
            return False, f"❌ {self.display_name}: Cookie 获取失败"

        if status == 'already_signed':
            stats = data if data else {}
            msg = f"✅ {self.display_name} 今日已签到"
            if stats:
                msg += f"\n   连续: {stats.get('lxdays', '-')}天 | 总计: {stats.get('lxtdays', '-')}天 | 等级: Lv.{stats.get('lxlevel', '-')}"
            return True, msg

        if status == 'can_sign':
            sign_url = data if data else SIGN_API_URL

            try:
                logger.info(f"📝 正在签到...")
                response = request_with_retry(self.session, 'get', sign_url, headers={'Referer': SIGN_PAGE_URL})
                response.encoding = 'utf-8'
                resp_text = response.text

                if DEBUG_MODE:
                    logger.info(f"[签到响应] {resp_text[:500]}")

                # 使用解析工具判断真实结果
                is_success, msg_detail, raw = parse_ajax_response(resp_text)

                if is_success:
                    return True, f"✅ {self.display_name} {msg_detail}"

                # 兜底：非 HTML 响应中精确匹配已知成功标志
                if not resp_text.startswith('<!') and not resp_text.startswith('<html'):
                    if any(x in resp_text for x in ['签到成功', '恭喜您获得']):
                        return True, f"✅ {self.display_name} 签到成功"

                    if any(x in resp_text for x in ['已经签到', '已签到', '今日已签']):
                        return True, f"✅ {self.display_name} 今日已签到"

                # 需要验证
                if any(x in resp_text for x in ['验证', 'captcha', '滑块', '安全验证']):
                    return False, f"⚠️ {self.display_name} 需要滑块验证，建议手动签到一次"

                return False, f"❌ {self.display_name} 签到失败: {msg_detail}"

            except Exception as e:
                return False, f"❌ {self.display_name} 签到请求失败: {str(e)[:100]}"

        if status == 'error':
            return False, f"❌ {self.display_name}: {data}"

        return False, f"❌ {self.display_name} 未知状态: {status}"


# ============ Cookie 模式 ============
class LaowangCookieSign:
    """Cookie 模式签到"""

    def __init__(self, cookie, index=1):
        self.cookie = cookie
        self.index = index
        self.session = self._create_session()
        self.display_name = f"账号{index}"

    def _create_session(self):
        """创建请求会话"""
        import requests
        import urllib3
        from requests.adapters import HTTPAdapter
        from urllib3.util.ssl_ import create_urllib3_context

        # 完全禁用 SSL 的 Adapter
        class NoVerifyHTTPAdapter(HTTPAdapter):
            def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
                from urllib3.poolmanager import PoolManager
                pool_kwargs['cert_reqs'] = 'CERT_NONE'
                pool_kwargs['assert_hostname'] = False
                pool_kwargs['assert_fingerprint'] = None
                return PoolManager(connections, maxsize, block, **pool_kwargs)

        session = requests.Session()

        # 如果使用自定义域名解析，使用完全禁用 SSL 的 Adapter
        if CUSTOM_HOST:
            session.mount('https://', NoVerifyHTTPAdapter())

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'identity',  # 禁用压缩
            'Cookie': self.cookie,
        }

        # 如果使用自定义域名解析，需要设置 Host 头
        if CUSTOM_HOST:
            headers['Host'] = 'laowang.vip'

        session.headers.update(headers)

        # 设置代理
        proxies = get_proxies()
        if proxies:
            session.proxies.update(proxies)
            logger.info(f"🌐 使用代理: {proxies['http']}")

        # 禁用 SSL 验证和警告
        session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        return session

    def do_sign(self):
        """执行签到"""
        try:
            # 获取签到状态
            response = request_with_retry(self.session, 'get', SIGN_PAGE_URL)
            response.encoding = 'utf-8'
            html = response.text

            # 提取用户名
            username_match = re.search(r'title="访问我的空间">([^<]+)</a>', html)
            if username_match:
                self.display_name = username_match.group(1).strip()

            # 检查登录状态
            has_logout = 'member.php?mod=logging&action=logout' in html
            has_userlink = username_match is not None

            if not has_logout and not has_userlink:
                if '登录' in html and '立即注册' in html:
                    return False, f"❌ {self.display_name}: Cookie 已失效"

            # 提取统计信息
            stats = {}
            patterns = {
                'lxdays': r'<input[^>]*id=["\']lxdays["\'][^>]*value=["\'](\d+)["\']',
                'lxlevel': r'<input[^>]*id=["\']lxlevel["\'][^>]*value=["\'](\d+)["\']',
                'lxtdays': r'<input[^>]*id=["\']lxtdays["\'][^>]*value=["\'](\d+)["\']',
            }
            for key, pattern in patterns.items():
                match = re.search(pattern, html)
                if match:
                    stats[key] = match.group(1)

            # 检查已签到
            if any(x in html for x in ['btnvisted', '已签到', '今日已签']):
                msg = f"✅ {self.display_name} 今日已签到"
                if stats:
                    msg += f"\n   连续: {stats.get('lxdays', '-')}天 | 总计: {stats.get('lxtdays', '-')}天"
                return True, msg

            # 执行签到
            logger.info("📝 正在执行签到...")

            # 提取签到链接
            sign_url = SIGN_API_URL
            href_pattern = r'href=["\']([^"\']*operation=qiandao[^"\']*)["\']'
            match = re.search(href_pattern, html)
            if match:
                url = match.group(1)
                if not url.startswith('http'):
                    url = urljoin(BASE_URL, url)
                sign_url = url

            response = request_with_retry(self.session, 'get', sign_url, headers={'Referer': SIGN_PAGE_URL})
            response.encoding = 'utf-8'
            resp_text = response.text

            if DEBUG_MODE:
                logger.info(f"[签到响应] {resp_text[:500]}")

            # 使用解析工具判断真实结果
            is_success, msg_detail, raw = parse_ajax_response(resp_text)

            if is_success:
                return True, f"✅ {self.display_name} {msg_detail}"

            # 兜底：非 HTML 响应中精确匹配已知成功标志
            if not resp_text.startswith('<!') and not resp_text.startswith('<html'):
                if any(x in resp_text for x in ['签到成功', '恭喜您获得']):
                    return True, f"✅ {self.display_name} 签到成功"

                if any(x in resp_text for x in ['已经签到', '已签到', '今日已签']):
                    return True, f"✅ {self.display_name} 今日已签到"

            if any(x in resp_text for x in ['验证', 'captcha', '滑块']):
                return False, f"⚠️ {self.display_name} 需要滑块验证"

            return False, f"❌ {self.display_name} 签到失败: {msg_detail}"

        except Exception as e:
            return False, f"❌ {self.display_name}: {str(e)[:150]}"


# ============ 浏览器模式（处理滑块验证） ============
class LaowangBrowserSign:
    """浏览器模式签到（自动处理滑块验证）"""

    def __init__(self, username, password, index=1):
        self.username = username
        self.password = password
        self.index = index
        self.display_name = username
        self.browser = None

    def _init_browser(self):
        """初始化浏览器"""
        try:
            import DrissionPage

            co = DrissionPage.ChromiumOptions()
            # 设置更真实的 User-Agent
            co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            co.set_pref('credentials_enable_service', False)
            co.set_argument('--hide-crash-restore-bubble')
            co.set_argument('--no-sandbox')
            co.set_argument('--disable-gpu')
            co.set_argument('--disable-blink-features=AutomationControlled')
            co.set_argument('--disable-dev-shm-usage')
            co.set_argument('--window-size=1920,1080')
            co.auto_port()
            co.headless(True)

            # 如果使用自定义域名解析，设置代理
            if CUSTOM_HOST:
                co.set_argument(f'--host-resolver-rules=MAP laowang.vip {CUSTOM_HOST}')

            self.browser = DrissionPage.ChromiumPage(co)
            return True
        except ImportError:
            logger.error("❌ 未安装 DrissionPage，请运行: pip install DrissionPage")
            return False
        except Exception as e:
            logger.error(f"❌ 浏览器初始化失败: {e}")
            return False

    def _find_slider_element(self):
        """查找滑块元素（尝试多种选择器）"""
        selectors = [
            '.slide_block',
            '.tncode-slider',
            '.slider',
            '[class*="slide_block"]',
            '[class*="tncode"]',
            '.nc_iconfont',
            '.btn_slide',
            '.handler',
            '.slide-btn',
        ]
        for selector in selectors:
            try:
                ele = self.browser.ele(selector, timeout=1)
                if ele:
                    logger.debug(f"找到滑块元素: {selector}")
                    return ele
            except:
                continue
        return None

    def _check_verification_passed(self):
        """检查验证是否已通过 — 仅检查真实通过标志"""
        result = self.browser.run_js('''
        var t = window.tncode;
        // tncode 内部状态：验证成功
        if (t && t._result === true) return 'tncode_pass';
        // clicaptcha token 已生成（末尾 _ok 表示通过）
        var infoInput = document.getElementById('clicaptcha-submit-info');
        if (infoInput && infoInput.value) {
            var v = infoInput.value;
            if (v.indexOf('_ok') > -1 && v.length > 20) return 'token_ok';
        }
        return false;
        ''')
        if result:
            logger.info(f"✅ 验证通过检测: {result}")
            return True
        return False

    def _diagnose_verification_state(self):
        """诊断验证状态，帮助排查服务端拒绝的原因"""
        try:
            diag = self.browser.run_js('''
            var t = window.tncode;
            var info = {
                tncode_result: t ? t._result : 'no tncode',
                track_data_len: (t && t._track_data) ? t._track_data.length : 0,
                mark_offset: t ? t._mark_offset : 'N/A',
                doing: t ? t._doing : 'N/A',
                err_c: t ? t._err_c : 'N/A',
                clicaptcha_value: 'N/A',
                token_has_ok: false
            };
            var inp = document.getElementById('clicaptcha-submit-info');
            if (inp && inp.value) {
                info.clicaptcha_value = inp.value.substring(0, 60);
                info.token_has_ok = inp.value.indexOf('_ok') > -1;
            }
            // 检查表单中seccode相关字段
            var seccodeFields = {};
            var allHidden = document.querySelectorAll('input[type="hidden"]');
            for (var i = 0; i < allHidden.length; i++) {
                var name = allHidden[i].name || '';
                if (name.indexOf('seccode') > -1 || name.indexOf('hash') > -1 || name.indexOf('captcha') > -1 || name.indexOf('clicaptcha') > -1) {
                    seccodeFields[name] = allHidden[i].value.substring(0, 60);
                }
            }
            info.seccode_fields = JSON.stringify(seccodeFields);
            // 检查 tncode_div 可见性
            var div = document.getElementById('tncode_div');
            if (div) {
                var style = window.getComputedStyle(div);
                info.tncode_div_display = style.display;
                info.tncode_div_visibility = style.visibility;
            }
            return JSON.stringify(info);
            ''')
            logger.info(f"🔍 验证状态诊断: {diag}")
        except Exception as e:
            logger.debug(f"诊断异常: {e}")

    def _find_tncode_gap(self):
        """将背景canvas与完整图（sprite第3行）对比，精确定位缺口位置"""
        compare_js = '''
        var t = window.tncode;
        var bgCanvas = document.querySelector('.tncode_canvas_bg');
        if (!bgCanvas || bgCanvas.width === 0) return -1;

        var img = (t && t._img) || document.querySelector('.tncode_div img');
        if (!img || !img.complete || img.naturalWidth === 0) return -3;

        var imgW = (t && t._img_w) || 240;
        var imgH = (t && t._img_h) || 150;
        var markW = (t && t._mark_w) || 50;
        var maxOffset = imgW - markW;

        // 确保 bg 已绘制（_draw_bg 以自然尺寸 imgW×imgH 绘制，而非 canvas 尺寸）
        if (t && t._draw_bg && !t._is_draw_bg) {
            try { t._draw_bg(); } catch(e) {}
        }

        // bg 画布只有前 imgW 像素有内容（_draw_bg 使用自然尺寸）
        // 因此比对时也必须使用 imgW 宽度的像素数据，否则右侧空白区域会产生误检
        var tmpCanvas = document.createElement('canvas');
        tmpCanvas.width = imgW;
        tmpCanvas.height = imgH;
        var tmpCtx = tmpCanvas.getContext('2d');
        try {
            tmpCtx.drawImage(img, 0, imgH * 2, imgW, imgH, 0, 0, imgW, imgH);
        } catch(e) {
            return -4;
        }

        var bgData = bgCanvas.getContext('2d').getImageData(0, 0, imgW, imgH);
        var fullData = tmpCtx.getImageData(0, 0, imgW, imgH);

        var threshold = 30;
        var scale = 1.0;  // 都在自然尺寸下比对，无需缩放
        var markW_px = markW;

        var diffCounts = new Array(imgW).fill(0);
        var checkRows = [25, 40, 55, 70, 85, 100, 115, 130];
        for (var ri = 0; ri < checkRows.length; ri++) {
            var y = checkRows[ri];
            for (var x = 0; x < imgW; x++) {
                var idx = (y * imgW + x) * 4;
                var dr = Math.abs(bgData.data[idx] - fullData.data[idx]);
                var dg = Math.abs(bgData.data[idx+1] - fullData.data[idx+1]);
                var db = Math.abs(bgData.data[idx+2] - fullData.data[idx+2]);
                if (dr + dg + db > threshold) {
                    diffCounts[x]++;
                }
            }
        }

        // 滑动窗口找到缺口区域
        var bestX = -1, bestSum = 0;
        for (var x = 0; x <= maxOffset; x++) {
            var sum = 0;
            for (var w = 0; w < markW_px; w++) {
                sum += diffCounts[x + w];
            }
            if (sum > bestSum) {
                bestSum = sum;
                bestX = x;
            }
        }

        var minDiffRequired = checkRows.length * markW_px * 0.2;
        if (bestSum < minDiffRequired) return -5;

        // bestX 已是图像像素坐标，直接作为 _mark_offset 使用
        // （tncode._block_on_move 中 _mark_offset = dx，dx 为屏幕像素位移，
        //   但 maxDx = imgW - markW 混合了单位，实际 _mark_offset = dx 屏幕像素 ≈ 图像偏移量）
        var imageX = bestX;
        if (imageX < 0) imageX = 0;
        if (imageX > maxOffset) imageX = maxOffset;
        return imageX;
        '''
        try:
            gap = self.browser.run_js(compare_js)
            if gap == -1:
                logger.info("比对分析: 未找到背景canvas")
            elif gap == -2:
                logger.info("比对分析: 背景canvas为空白")
            elif gap == -3:
                logger.info("比对分析: 未找到tncode图片元素或图片未加载")
            elif gap == -4:
                logger.info("比对分析: drawImage失败（图片元素不可用于绘制）")
            elif gap == -5:
                logger.info(f"比对分析: 未找到足够的差异区域 (bestSum不足)")
            elif gap is not None and gap > 5:
                logger.info(f"🎯 比对分析: 缺口位置 = {gap}px (max=190)")
                return int(gap)
            else:
                logger.info(f"比对分析返回: {gap}")
            return -1
        except Exception as e:
            logger.info(f"比对分析异常: {e}")
            return -1

    def _try_tncode_drag(self, distance):
        """
        纯 JS 拖动：直接调用 tncode 原生函数 + MouseEvent。
        使用 JS busy-loop 确保精确的时间控制（服务器只看轨迹数据，不感知JS线程状态）。
        """
        logger.info(f"🖱️ _try_tncode_drag: image_gap={distance}")
        try:
            import random as _rnd

            # 预生成轨迹参数（Python 随机，避免 JS Math.random 的模式）
            total_time = _rnd.randint(1200, 2200)
            target_points = _rnd.randint(25, 40)
            y_variance = _rnd.randint(5, 10)

            js_code = f'''
            var IMAGE_GAP = {distance};
            var SCREEN_DIST = IMAGE_GAP;
            var TOTAL_TIME = {total_time};
            var TARGET_POINTS = {target_points};
            var Y_VARIANCE = {y_variance};

            var t = window.tncode;
            var slider = document.querySelector('.slide_block');
            if (!t || !slider) return 'no_handler';

            try {{ t._reset(); }} catch(e) {{}}

            var rect = slider.getBoundingClientRect();
            var startX = Math.round(rect.left + rect.width / 2);
            var startY = Math.round(rect.top + rect.height / 2);

            function makeME(type, x, y, isUp) {{
                return new MouseEvent(type, {{
                    bubbles: true, cancelable: true,
                    clientX: x, clientY: y,
                    button: 0, buttons: isUp ? 0 : 1
                }});
            }}

            function rnd(min, max) {{
                return min + Math.floor(Math.random() * (max - min + 1));
            }}

            // 生成轨迹时间序列
            var steps = TARGET_POINTS;
            var times = new Array(steps);
            var base = TOTAL_TIME / steps;
            for (var i = 0; i < steps; i++) {{
                var t_step = base + rnd(-15, 15);
                if (Math.random() < 0.05) t_step += rnd(20, 60);
                if (Math.random() < 0.03) t_step += rnd(40, 100);
                times[i] = Math.max(2, Math.round(t_step));
            }}

            // 生成轨迹位置序列（带 Y 抖动）
            var xs = new Array(steps);
            for (var i = 0; i < steps; i++) {{
                var frac = (i + 1) / steps;
                // 加速-减速曲线
                var eased;
                if (frac < 0.3) {{
                    eased = 0.5 * Math.pow(frac / 0.3, 2);
                }} else if (frac < 0.8) {{
                    eased = 0.5 + 0.5 * ((frac - 0.3) / 0.5);
                }} else {{
                    eased = 1 - 0.5 * Math.pow((1 - frac) / 0.2, 2);
                }}
                xs[i] = Math.round(eased * SCREEN_DIST);
            }}

            // === 1. 开始拖动 ===
            t._block_start_move(makeME('mousedown', startX, startY, false));

            // === 2. 执行轨迹 ===
            var startMs = Date.now();
            var cumulative = 0;
            for (var i = 0; i < steps; i++) {{
                cumulative += times[i];
                var target = startMs + cumulative;
                var wait = target - Date.now();
                if (wait > 0) {{
                    var endWait = Date.now() + wait;
                    while (Date.now() < endWait) {{}}
                }}

                var x = startX + xs[i];
                var y = startY + Math.round((Math.random() - 0.5) * Y_VARIANCE * 2);
                // 偶尔的垂直抖动
                if (Math.random() < 0.08) {{
                    y += Math.round((Math.random() - 0.5) * Y_VARIANCE * 4);
                }}
                t._block_on_move(makeME('mousemove', x, y, false));
            }}

            // === 3. 超调回退 ===
            var wait = rnd(30, 60);
            var endWait = Date.now() + wait;
            while (Date.now() < endWait) {{}}
            var overshoot = rnd(1, 4);
            t._block_on_move(makeME('mousemove', startX + SCREEN_DIST + overshoot, startY, false));
            wait = rnd(35, 65);
            endWait = Date.now() + wait;
            while (Date.now() < endWait) {{}}
            t._block_on_move(makeME('mousemove', startX + SCREEN_DIST, startY, false));

            // === 4. 释放前停顿 ===
            wait = rnd(40, 80);
            endWait = Date.now() + wait;
            while (Date.now() < endWait) {{}}

            // === 5. 释放 ===
            t._block_on_end(makeME('mouseup', startX + SCREEN_DIST, startY, true));

            var trackLen = t._track_data ? t._track_data.length : 0;
            var totalT = (trackLen > 0 && t._track_data) ? t._track_data[trackLen-1].t : 0;

            return 'ok: img_gap=' + IMAGE_GAP + ' scr_dist=' + SCREEN_DIST +
                   ' track=' + trackLen + ' time=' + totalT + 'ms offset=' + t._mark_offset;
            '''
            result = self.browser.run_js(js_code)
            logger.info(f"🖱️ _try_tncode_drag 结果: {result}")
            if isinstance(result, str) and result.startswith('err:'):
                logger.warning(f"tncode拖动错误: {result}")
                return False
            if result == 'no_handler':
                logger.warning("tncode拖动: 未找到处理器")
                return False
            return bool(result) and str(result).startswith('ok')
        except Exception as e:
            logger.debug(f"tncode拖动失败: {e}")
            return False

    def _wait_for_tncode_result(self, timeout=6):
        """轮询等待 tncode 验证结果（不阻塞 JS 主线程）"""
        check_js = '''
        var t = window.tncode;
        if (!t) return 'no_tncode';
        if (t._result === true) return 'pass';
        // 检查 clicaptcha token 是否已包含 _ok
        var infoInput = document.getElementById('clicaptcha-submit-info');
        if (infoInput && infoInput.value && infoInput.value.indexOf('_ok') > -1) return 'pass';
        if (t._doing === true) return 'dragging';
        if (t._doing === false && t._track_data && t._track_data.length > 1) return 'sent';
        return 'wait';
        '''
        start = time.time()
        sent_time = None
        while time.time() - start < timeout:
            try:
                result = self.browser.run_js(check_js)
                if result in ('pass',):
                    return True
                if result == 'sent':
                    # 拖动已完成，请求已发送，记录时间并继续等待服务器响应
                    if sent_time is None:
                        sent_time = time.time()
                    elif time.time() - sent_time > 2.5:
                        # 等待 2.5 秒后仍无响应，判定失败
                        return 'retry'
                # 'dragging' / 'wait' → 继续等待
            except:
                pass
            time.sleep(0.3)
        # 超时，最后检查一次
        try:
            final = self.browser.run_js('''
            var t = window.tncode;
            if (t && t._result === true) return true;
            var inp = document.getElementById('clicaptcha-submit-info');
            if (inp && inp.value && inp.value.indexOf('_ok') > -1) return true;
            return false;
            ''')
            return bool(final)
        except:
            return False

    def _refresh_tncode(self):
        """刷新 tncode 验证码"""
        try:
            result = self.browser.run_js('''
            var t = window.tncode;
            if (t && typeof t.refresh === 'function') {
                t.refresh();
                return true;
            }
            var btn = document.querySelector('.tncode_refresh');
            if (btn) { btn.click(); return true; }
            return false;
            ''')
            if result:
                time.sleep(1.5)
                return True
        except Exception as e:
            logger.info(f"刷新tncode失败: {e}")
        return False

    def pass_slide_verification(self):
        """处理滑块验证 — Canvas分析 + tncode原生事件"""
        logger.info("🤖 开始破解滑块验证...")

        if self._check_verification_passed():
            logger.info("✅ 验证已自动通过")
            return True

        # 等待滑块出现并确保 tncode 初始化
        time.sleep(2)
        for _ in range(3):
            if self._find_slider_element():
                break
            time.sleep(1)
        else:
            if self._check_verification_passed():
                logger.info("✅ 滑块已消失，验证通过")
                return True
            logger.warning("⚠️ 未找到滑块元素")
            return False

        max_attempts = 5
        for attempt in range(max_attempts):
            if self._check_verification_passed():
                logger.info("✅ 验证已通过")
                return True

            logger.info(f"🔄 第 {attempt+1}/{max_attempts} 次尝试...")

            # 等待 tncode 图片加载完成
            if attempt == 0:
                img_ready = False
                for w in range(10):
                    ready = self.browser.run_js('''
                    var t = window.tncode;
                    var img = document.querySelector('.tncode_div img');
                    return !!(t && t._img_loaded && img && img.complete && img.naturalWidth > 0);
                    ''')
                    if ready:
                        img_ready = True
                        break
                    time.sleep(0.5)
                if not img_ready:
                    logger.info("⏳ 图片加载超时，尝试刷新...")
                    self._refresh_tncode()
                    time.sleep(1)

            # 方法1: Canvas分析获取精确缺口位置
            gap = self._find_tncode_gap()
            if gap > 5:
                logger.info(f"🎯 检测到缺口: {gap}px，开始精确拖动...")
                if self._try_tncode_drag(gap):
                    time.sleep(1)
                    result = self._wait_for_tncode_result(timeout=4)
                    if result is True:
                        logger.info("✅ 滑块验证通过！(Canvas精确)")
                        # 诊断：检查验证状态是否真正反映到表单
                        self._diagnose_verification_state()
                        return True
                    elif result == 'retry':
                        logger.info("⚠️ 验证未通过，刷新重试...")
                    else:
                        logger.debug(f"tncode结果: {result}")

            # 方法2: 如果Canvas分析失败，尝试几个常见距离
            if gap <= 5:
                logger.info("⚠️ Canvas分析失败，尝试常见距离...")
                for dist in [60, 90, 120, 80, 110, 150]:
                    if self._try_tncode_drag(dist):
                        time.sleep(1)
                        result = self._wait_for_tncode_result(timeout=3)
                        if result is True:
                            logger.info(f"✅ 滑块验证通过！(距离: {dist}px)")
                            return True

            # 刷新验证码准备下次尝试
            if attempt < max_attempts - 1:
                self._refresh_tncode()
                time.sleep(1)

        logger.error("❌ 滑块验证失败，已达最大尝试次数")
        return False

    def _extract_cookies(self):
        """从浏览器提取 Cookie"""
        try:
            cookies = self.browser.cookies()
            if not cookies:
                return ""

            cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
            return cookie_str
        except Exception as e:
            logger.debug(f"提取Cookie失败: {e}")
            return ""

    def do_sign(self):
        """执行浏览器签到"""
        if not self._init_browser():
            return False, "浏览器初始化失败"

        try:
            login_attempts = 3

            for login_try in range(login_attempts):
                if login_try > 0:
                    logger.info(f"🔄 登录重试 {login_try+1}/{login_attempts}...")
                    time.sleep(2)

                try:
                    # 访问登录页面
                    logger.info("🌐 正在访问登录页面...")
                    self.browser.get(LOGIN_URL)
                    time.sleep(2)

                    # 输入账号密码
                    logger.info(f"🔐 正在输入账号: {self.username}")
                    self.browser.ele('@name=username').input(self.username)
                    self.browser.ele('@name=password').input(self.password)

                    # 处理滑块验证
                    has_captcha = True
                    try:
                        tncode = self.browser.ele('.tncode', timeout=3)
                        if tncode:
                            text_span = self.browser.ele('.tncode-text', timeout=1)
                            if text_span and '点击' in text_span.text:
                                logger.info("🖱️ 点击触发滑块验证...")
                                tncode.click()
                                time.sleep(2)

                            if not self.pass_slide_verification():
                                logger.warning("⚠️ 滑块验证破解未成功，重试登录流程...")
                                continue  # 重试整个登录流程
                        else:
                            has_captcha = False
                    except Exception as e:
                        has_captcha = False
                        logger.debug(f"未找到 tncode 验证码: {e}")

                    # 提交登录 — 先 JS 直接提交表单
                    logger.info("🔑 正在提交登录...")
                    login_result = self.browser.run_js('''
                    var infoInput = document.getElementById("clicaptcha-submit-info");
                    var loginForm = document.querySelector("form[name='login']");
                    if (!loginForm) return 'no_form';
                    if (infoInput && !loginForm.contains(infoInput)) {
                        loginForm.appendChild(infoInput);
                    }
                    // 直接提交表单（触发完整的表单提交流程）
                    loginForm.submit();
                    return 'form_submitted';
                    ''')
                    logger.debug(f"登录提交结果: {login_result}")

                    # 等待跳转或页面更新
                    time.sleep(4)

                    # 验证登录成功（多种检测方式）
                    current_html = self.browser.html
                    current_url = self.browser.url
                    if 'member.php?mod=logging&action=logout' in current_html:
                        logger.info("✅ 检测到 logout 链接，登录成功")
                        break
                    if 'succeedmessage' in current_html or '欢迎您回来' in current_html:
                        logger.info("✅ 检测到登录成功消息")
                        time.sleep(2)
                        break
                    # 已不再停留在登录页 → 登录成功
                    if 'member.php?mod=logging' not in current_url:
                        logger.info(f"✅ 已跳转离开登录页: {current_url[:60]}")
                        break

                    # 诊断登录失败
                    login_diag = self.browser.run_js('''
                    var errors = {};
                    var e = document.querySelector(".pc_inner, .loginf, [class*='error'], [class*='alert'], [id*='error'], [id*='notice']");
                    if (e) errors.page_msg = e.innerText ? e.innerText.substring(0, 200) : e.textContent.substring(0, 200);
                    var form = document.querySelector("form[name='login']");
                    if (form) {
                        errors.form_action = form.action;
                        errors.form_method = form.method;
                    }
                    return JSON.stringify(errors);
                    ''')
                    logger.info(f"🔍 登录失败诊断: {login_diag}")

                    # 登录失败，检查原因
                    current_url = self.browser.url
                    logger.warning(f"⚠️ 登录可能未成功，当前 URL: {current_url[:80]}")

                    if 'member.php?mod=logging' in current_url:
                        if has_captcha:
                            logger.warning("⚠️ 滑块验证可能未正确通过，正在重试...")
                            continue
                        else:
                            logger.error("❌ 登录失败（无验证码但密码可能错误）")
                            return False, f"❌ {self.username}: 登录失败，请检查账号密码"

                    continue

                except Exception as e:
                    logger.error(f"登录流程异常: {e}")
                    # 如果找不到用户名输入框，可能已登录
                    if '没有找到元素' in str(e) or '@name=username' in str(e):
                        current_url = self.browser.url if self.browser else ''
                        current_html = self.browser.html if self.browser else ''
                        # 不在登录页、已在首页/论坛 → 已登录
                        if 'member.php?mod=logging' not in current_url:
                            logger.info(f"✅ 已处于登录状态（当前URL: {current_url[:60]}）")
                            break
                        if '退出' in current_html or '我的' in current_html or '个人中心' in current_html:
                            logger.info("✅ 已处于登录状态（页面显示已登录信息）")
                            break
                    if login_try < login_attempts - 1:
                        continue
                    return False, f"❌ {self.username}: 浏览器操作失败: {e}"

            # 确认登录成功后再进行后续操作
            current_html = self.browser.html
            current_url = self.browser.url
            logged_in = (
                'member.php?mod=logging&action=logout' in current_html or
                '退出' in current_html or
                '我的' in current_html or
                ('member.php?mod=logging' not in current_url and 'laowang.vip' in current_url) or
                '欢迎您回来' in current_html or
                '签到' in current_html  # 签到按钮说明已登录
            )
            if not logged_in:
                logger.warning(f"未检测到登录状态，URL={current_url[:60]}")
                return False, f"❌ {self.username}: 登录失败（{login_attempts}次尝试后仍失败）"

            # 提取用户名
            try:
                username_match = re.search(r'title="访问我的空间">([^<]+)</a>', current_html)
                if username_match:
                    self.display_name = username_match.group(1).strip()
            except:
                pass

            logger.info(f"✅ 登录成功: {self.display_name}")

            # 提取 Cookie 供后续使用
            cookie_str = self._extract_cookies()
            if cookie_str:
                logger.info(f"📋 已提取 Cookie（可复制到环境变量使用）:\n{cookie_str[:200]}...")
                if notify:
                    notify("老王论坛 Cookie 提取", f"账号: {self.display_name}\nCookie: {cookie_str[:300]}...\n\n请将完整 Cookie 设置到 LAOWANG_COOKIE 环境变量中使用 Cookie 模式（更稳定）")

            # 访问签到页面
            logger.info("📝 正在访问签到页面...")
            self.browser.get(SIGN_PAGE_URL)
            time.sleep(3)

            # 检查是否还在登录状态（签到页面可能要求重新登录）
            current_html = self.browser.html
            current_url = self.browser.url
            if 'member.php?mod=logging' in current_url:
                logger.warning("⚠️ 访问签到页面后被重定向到登录页，尝试重新登录...")
                # 重新输入账号密码并登录
                try:
                    self.browser.run_js(f'''
                    var u = document.querySelector("input[name=username]");
                    var p = document.querySelector("input[name=password]");
                    if (u) u.value = "{self.username}";
                    if (p) p.value = "{self.password}";
                    ''')
                    time.sleep(1)
                    # 触发 tncode
                    self.browser.run_js('var t = document.querySelector("#tncode"); if(t) t.click();')
                    time.sleep(2)
                    # 尝试破解 tncode
                    self.pass_slide_verification()
                    time.sleep(1)
                    # 提交登录
                    self.browser.run_js('''
                    var f = document.querySelector("form[name=login]");
                    if (f) f.submit();
                    ''')
                    time.sleep(4)
                    # 再次访问签到页面
                    self.browser.get(SIGN_PAGE_URL)
                    time.sleep(3)
                    current_html = self.browser.html
                except Exception as e:
                    logger.error(f"重新登录失败: {e}")

            # 检查是否已签到
            page_html = self.browser.html
            if any(x in page_html for x in ['今日已签', 'btnvisted', '已签到']):
                return True, f"✅ {self.display_name} 今日已签到"

            # 点击签到按钮（DrissionPage ele() 无法匹配复合类名，用 JS 直接点击）
            try:
                clicked = self.browser.run_js('''
                var btn = document.querySelector('.btn.J_chkitot') || document.querySelector('[class*="chkitot"]');
                if (btn) { btn.click(); return true; }
                return false;
                ''')
                if clicked:
                    time.sleep(2)

                    # 检查是否需要再次滑块验证
                    try:
                        tncode = self.browser.ele('.tncode', timeout=3)
                        if tncode:
                            tncode.click()
                            logger.info("🤖 签到需要滑块验证，开始破解...")
                            if not self.pass_slide_verification():
                                return False, f"❌ {self.display_name}: 签到滑块验证失败"

                            # 验证通过后，点击提交按钮
                            time.sleep(1)
                            try:
                                submit_btn = self.browser.ele('#submit-btn', timeout=2)
                                if submit_btn:
                                    logger.info("📤 点击提交按钮...")
                                    submit_btn.click()
                                    time.sleep(2)
                            except:
                                pass
                    except:
                        pass

                    # 检查签到结果
                    time.sleep(2)
                    result_html = self.browser.html
                    result_url = self.browser.url
                    logger.info(f"签到结果页面 URL: {result_url[:80]}")
                    # 检查页面内容中的关键信息
                    result_text = self.browser.run_js('return document.body ? document.body.innerText.substring(0, 500) : "";')
                    logger.info(f"签到结果页面内容: {result_text[:200]}")
                    if any(x in result_html for x in ['今日已签', 'btnvisted', '已签到', '签到成功']):
                        return True, f"✅ {self.display_name} 签到成功"

                    # 没有明确成功标志，当作失败
                    logger.warning(f"签到按钮已点击但未检测到成功标志，URL: {self.browser.url[:80]}")
                    return False, f"❌ {self.display_name}: 签到结果不明确，请检查日志"
                else:
                    return False, f"❌ {self.display_name}: 未找到签到按钮（JS点击失败）"

            except Exception as e:
                return False, f"❌ {self.display_name}: 签到操作失败: {e}"

        finally:
            if self.browser:
                try:
                    self.browser.quit()
                except:
                    pass


# ============ 账号解析 ============
def parse_accounts(env_str):
    """解析账号配置
    支持格式:
    - 账号密码: username:password&username2:password2
    - Cookie: cookie_string
    """
    if not env_str:
        return []

    accounts = []

    # 按 & 或换行分割多账号
    items = re.split(r'[&\n]', env_str.strip())

    for item in items:
        item = item.strip()
        if not item:
            continue

        # 检查是否包含 : （可能是账号密码格式）
        if ':' in item and '=' not in item.split(':')[0]:
            # 可能是账号密码格式
            parts = item.split(':', 1)
            if len(parts) == 2:
                username, password = parts
                # 简单判断：如果username不含特殊cookie字符，则认为是账号密码
                if not any(x in username for x in ['=', ';', '__cf', 'auth', 'uid']):
                    accounts.append({
                        'type': 'password',
                        'username': username.strip(),
                        'password': password.strip()
                    })
                    continue

        # 否则认为是 Cookie
        accounts.append({
            'type': 'cookie',
            'cookie': item
        })

    return accounts


# ============ 主程序 ============
def main():
    """主函数"""
    # 检测是否在青龙面板运行
    is_qinglong = os.path.exists('/ql') or 'QL_DIR' in os.environ

    print("""
╔══════════════════════════════════════════╗
║     老王论坛自动签到脚本 v4.1             ║
║     支持 账号密码 / Cookie 双模式         ║
╚══════════════════════════════════════════╝
""")

    if is_qinglong:
        print("🐉 检测到青龙面板环境")

    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 随机延迟
    max_delay = int(os.getenv('MAX_RANDOM_DELAY', '300'))
    use_random = os.getenv('RANDOM_SIGNIN', 'true').lower() == 'true'

    if use_random and max_delay > 0:
        delay = random.randint(0, max_delay)
        wait_countdown(delay, "老王论坛签到")

    # 获取配置
    env_str = os.getenv('LAOWANG_ACCOUNT', '').strip() or os.getenv('LAOWANG_COOKIE', '').strip()

    if not env_str:
        error_msg = """❌ 未配置 LAOWANG_ACCOUNT 或 LAOWANG_COOKIE 环境变量

🔧 配置方式（三选一）:

方式1 - 账号密码 + 浏览器模式（自动处理滑块）:
LAOWANG_ACCOUNT=用户名:密码
LAOWANG_BROWSER_MODE=true

方式2 - 账号密码（HTTP模式，可能遇到滑块）:
LAOWANG_ACCOUNT=用户名:密码

方式3 - Cookie（无需处理滑块）:
LAOWANG_COOKIE=cookie1&cookie2

🌐 代理配置（国内需要）:
LAOWANG_PROXY=http://127.0.0.1:7890

💡 提示:
- Cookie模式最稳定，需要定期更新Cookie
- 浏览器模式需要安装: pip install DrissionPage
- 调试模式: LAOWANG_DEBUG=true（可查看原始响应）
"""
        print(error_msg)
        push_notify("老王论坛签到失败", error_msg)
        sys.exit(1)

    # 调试模式：测试网络连接
    if DEBUG_MODE:
        connection_ok = test_connection()
        if not connection_ok and not CUSTOM_HOST:
            # 自动寻找可用 IP
            working_ip = find_working_ip()
            if working_ip:
                logger.info(f"💡 发现可用 IP: {working_ip}")
                logger.info(f"   请设置环境变量: LAOWANG_CUSTOM_HOST={working_ip}")
            else:
                logger.error("❌ 未找到可用 IP，请手动检查网络")
        print("")

    # 解析账号
    accounts = parse_accounts(env_str)
    print(f"✅ 检测到 {len(accounts)} 个账号\n")

    # 检查 DrissionPage 是否可用
    drissionpage_available = False
    try:
        import DrissionPage
        drissionpage_available = True
    except ImportError:
        pass

    # 浏览器模式设置
    # auto: 自动选择（账号密码优先用浏览器模式）
    # true: 强制使用浏览器模式
    # false: 禁用浏览器模式（只用HTTP）
    if BROWSER_MODE == 'true':
        use_browser = True
        force_browser = True
    elif BROWSER_MODE == 'false':
        use_browser = False
        force_browser = False
    else:  # auto
        use_browser = drissionpage_available
        force_browser = False

    if use_browser and drissionpage_available:
        print("🤖 浏览器模式已启用（自动处理滑块验证）\n")
    elif not drissionpage_available and BROWSER_MODE == 'true':
        print("⚠️  警告: 未安装 DrissionPage，无法使用浏览器模式")
        print("   请运行: pip install DrissionPage\n")

    # 签到结果
    results = []

    for idx, account in enumerate(accounts, 1):
        print(f"{'─' * 50}")
        print(f"🙍🏻 账号 {idx}/{len(accounts)}")
        print(f"{'─' * 50}")

        if account['type'] == 'password':
            # 账号密码模式：优先使用浏览器模式（处理滑块）
            if use_browser and drissionpage_available:
                signer = LaowangBrowserSign(
                    account['username'],
                    account['password'],
                    idx
                )
                success, msg = signer.do_sign()

                # 如果浏览器模式失败且不是强制模式，尝试HTTP模式
                if not success and not force_browser and '滑块' not in msg:
                    logger.info("🔄 浏览器模式失败，尝试HTTP模式...")
                    signer = LaowangLoginSign(
                        account['username'],
                        account['password'],
                        idx
                    )
                    success, msg = signer.do_sign()
            else:
                # HTTP模式（可能遇到滑块）
                signer = LaowangLoginSign(
                    account['username'],
                    account['password'],
                    idx
                )
                success, msg = signer.do_sign()

                # 如果是因为滑块失败且安装了DrissionPage，提示使用浏览器模式
                if not success and '滑块' in msg and drissionpage_available:
                    msg += "\n💡 提示: 安装 DrissionPage 可自动处理滑块"
        else:
            # Cookie 模式
            signer = LaowangCookieSign(account['cookie'], idx)
            success, msg = signer.do_sign()

        results.append((idx, success, msg))
        print(msg)

        # 账号间延迟
        if idx < len(accounts):
            delay = random.uniform(3, 8)
            print(f"\n⏱️ 等待 {delay:.1f} 秒后处理下一个账号...")
            time.sleep(delay)

    # 汇总结果
    print(f"\n{'─' * 50}")
    print(f"📊 签到汇总")
    print(f"{'─' * 50}")

    success_count = sum(1 for _, success, _ in results if success)

    summary = f"成功: {success_count}/{len(accounts)}\n"
    for idx, success, msg in results:
        status = "✅" if success else "❌"
        # 只取第一行
        first_line = msg.split('\n')[0]
        summary += f"\n{status} 账号{idx}: {first_line}"

    print(summary)
    print(f"\n⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 推送通知
    push_notify("老王论坛签到结果", summary)


if __name__ == "__main__":
    main()
