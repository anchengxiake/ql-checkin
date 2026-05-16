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
    level=logging.INFO,
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
        """检查验证是否已通过 — 必须非常准确，避免误判"""
        # 方法0: 能否找到 tncode 容器？找不到说明可能已经过了验证
        try:
            tncode_div = self.browser.ele('#tncode_div, .tncode', timeout=0.3)
            if tncode_div:
                display = self.browser.run_js('return window.getComputedStyle(arguments[0]).display', tncode_div)
                if display == 'none':
                    return True
            else:
                # 找不到 tncode 容器，且找不到滑块 → 验证可能已过
                try:
                    self.browser.ele('.slide_block', timeout=0.2)
                except:
                    return True
        except:
            pass

        # 方法1: 只检查特定的 captcha 结果输入框（不是所有隐藏输入框）
        captcha_input_ids = ['#clicaptcha-submit-info', '#captcha-result', '#tncode-result',
                            'input[name="captcha_hash"]', 'input[name="tncode_hash"]']
        for sel in captcha_input_ids:
            try:
                inp = self.browser.ele(sel, timeout=0.2)
                if inp:
                    val = inp.value or inp.attr('value') or ''
                    if val and len(str(val)) > 20:
                        logger.debug(f"验证输入框有值: {sel}")
                        return True
            except:
                pass

        # 方法2: 只检查 body 可视文本中的成功标志（不检查 HTML 源码）
        try:
            body_ele = self.browser.ele('body', timeout=0.3)
            if body_ele:
                body_text = body_ele.text
                if any(k in body_text for k in ['验证成功', '验证通过', '校验成功']):
                    return True
        except:
            pass

        # 方法3: 检查是否有 tnc 滑块验证通过后的跳转/状态变化
        try:
            # tncode 验证通过后，通常会 show/hide 一些元素
            slider = self.browser.ele('.slide_block', timeout=0.3)
            if slider:
                # 滑块还在，验证一定没通过
                return False
        except:
            # 滑块找不到了，可能是通过了
            return True

        return False

    def _try_js_drag(self, distance):
        """使用 JavaScript 模拟拖动 - 在 document 上分派事件确保 tncode 捕获"""
        try:
            js_code = '''
            (function() {
                var slider = document.querySelector('.slide_block');
                if (!slider) return 'no_slider';

                var distance = arguments[0];
                var rect = slider.getBoundingClientRect();
                var startX = rect.left + rect.width / 2;
                var startY = rect.top + rect.height / 2;
                var endX = startX + distance;

                function sendMouseEvent(type, x, y) {
                    var evt = new MouseEvent(type, {
                        bubbles: true,
                        cancelable: true,
                        view: window,
                        clientX: x, clientY: y,
                        screenX: x, screenY: y,
                        button: 0,
                        buttons: type === 'mouseup' ? 0 : 1
                    });
                    // 在 slider 和 document 上都 dispatch
                    slider.dispatchEvent(evt);
                    document.dispatchEvent(evt);
                }

                function sendTouchEvent(type, x, y) {
                    try {
                        var touch = new Touch({
                            identifier: 0,
                            target: slider,
                            clientX: x, clientY: y,
                            screenX: x, screenY: y,
                            pageX: x, pageY: y
                        });
                        var evt = new TouchEvent(type, {
                            bubbles: true,
                            cancelable: true,
                            view: window,
                            touches: type === 'touchend' ? [] : [touch],
                            targetTouches: type === 'touchend' ? [] : [touch],
                            changedTouches: [touch]
                        });
                        slider.dispatchEvent(evt);
                    } catch(e) {}
                }

                // 先尝试 mouse 事件
                sendMouseEvent('mousedown', startX, startY);
                sendTouchEvent('touchstart', startX, startY);

                var steps = 8 + Math.floor(Math.random() * 5);
                for (var i = 1; i <= steps; i++) {
                    var progress = i / steps;
                    var ease = 1 - Math.pow(1 - progress, 3);
                    var currentX = startX + (endX - startX) * ease;
                    var currentY = startY + (Math.random() - 0.5) * 2;
                    sendMouseEvent('mousemove', currentX, currentY);
                    sendTouchEvent('touchmove', currentX, currentY);
                }

                sendMouseEvent('mouseup', endX, startY);
                sendTouchEvent('touchend', endX, startY);
                return 'ok';
            })()
            '''
            result = self.browser.run_js(js_code, distance)
            if result == 'no_slider':
                logger.debug("JS拖动: 未找到滑块元素")
                return False
            return True
        except Exception as e:
            logger.debug(f"JS拖动失败: {e}")
            return False

    def _try_actions_drag(self, distance):
        """使用 DrissionPage actions 真实鼠标拖动"""
        slider = self._find_slider_element()
        if not slider:
            return False
        try:
            self.browser.actions.move_to(slider)
            self.browser.actions.hold()
            time.sleep(0.05)

            steps = random.randint(6, 12)
            step_dist = distance / steps
            for i in range(steps):
                offset_y = random.randint(-2, 2)
                self.browser.actions.move(step_dist, offset_y)
                time.sleep(random.uniform(0.02, 0.06))

            self.browser.actions.release()
            time.sleep(0.3)
            return True
        except Exception as e:
            logger.debug(f"Actions拖动失败: {e}")
            return False

    def _refresh_captcha(self):
        """刷新验证码"""
        try:
            refresh_btn = self.browser.ele('.tncode-refresh, .refresh, [class*="refresh"]', timeout=1)
            if refresh_btn:
                refresh_btn.click()
                time.sleep(1)
                return True
        except:
            pass
        return False

    def pass_slide_verification(self):
        """处理滑块验证 - JS事件注入 + 真实鼠标拖动"""
        logger.info("🤖 开始破解滑块验证...")

        if self._check_verification_passed():
            logger.info("✅ 验证已自动通过")
            return True

        # 等待滑块出现
        time.sleep(1.5)
        if not self._find_slider_element():
            time.sleep(2)
            if not self._find_slider_element():
                if self._check_verification_passed():
                    logger.info("✅ 滑块已消失，验证通过")
                    return True
                logger.warning("⚠️ 未找到滑块元素")
                return False

        # 获取轨道宽度
        track_width = 260
        try:
            slider = self._find_slider_element()
            if slider:
                track = slider.parent()
                if track:
                    track_width = max(50, track.rect.size[0] - slider.rect.size[0])
        except:
            pass
        logger.info(f"轨道宽度约: {track_width}px")

        # 尝试不同距离
        distances = list(range(30, track_width + 1, 6))
        random.shuffle(distances[:15])

        for i, distance in enumerate(distances):
            if i > 0 and i % 12 == 0:
                logger.info("🔄 刷新验证码...")
                self._refresh_captcha()
                time.sleep(1.5)
                if not self._find_slider_element():
                    if self._check_verification_passed():
                        return True
                    break

            # JS 事件注入拖动
            if self._try_js_drag(distance):
                time.sleep(0.6)
                if self._check_verification_passed():
                    logger.info(f"✅ 滑块验证通过！(JS, 距离: {distance}px)")
                    return True

            # 真实鼠标拖动
            if self._try_actions_drag(distance):
                time.sleep(0.6)
                if self._check_verification_passed():
                    logger.info(f"✅ 滑块验证通过！(Actions, 距离: {distance}px)")
                    return True

        logger.error("❌ 滑块验证失败，所有距离都尝试过")
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
                                time.sleep(0.5)

                            if not self.pass_slide_verification():
                                logger.warning("⚠️ 滑块验证破解未成功，重试登录流程...")
                                continue  # 重试整个登录流程
                        else:
                            has_captcha = False
                    except Exception as e:
                        has_captcha = False
                        logger.debug(f"未找到 tncode 验证码: {e}")

                    # 点击登录
                    logger.info("🔑 正在提交登录...")
                    self.browser.ele('@name=loginsubmit').click()

                    # 等待跳转或页面更新
                    time.sleep(3)

                    # 验证登录成功
                    current_html = self.browser.html
                    if 'member.php?mod=logging&action=logout' in current_html:
                        break  # 登录成功！

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
                    if login_try < login_attempts - 1:
                        continue
                    return False, f"❌ {self.username}: 浏览器操作失败: {e}"

            # 确认登录成功后再进行后续操作
            current_html = self.browser.html
            if 'member.php?mod=logging&action=logout' not in current_html:
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
            time.sleep(2)

            # 检查是否已签到
            page_html = self.browser.html
            if any(x in page_html for x in ['今日已签', 'btnvisted', '已签到']):
                return True, f"✅ {self.display_name} 今日已签到"

            # 点击签到按钮
            try:
                sign_btn = self.browser.ele('.btn.J_chkitot, .J_chkitot, [class*="chkitot"]', timeout=5)
                if sign_btn:
                    sign_btn.click()
                    time.sleep(2)

                    # 检查是否需要再次滑块验证
                    try:
                        tncode = self.browser.ele('.tncode', timeout=3)
                        if tncode:
                            tncode.click()
                            logger.info("🤖 签到需要滑块验证，开始破解...")
                            if not self.pass_slide_verification():
                                return False, f"❌ {self.display_name}: 签到滑块验证失败"
                    except:
                        pass

                    # 检查签到结果
                    time.sleep(2)
                    result_html = self.browser.html
                    if any(x in result_html for x in ['今日已签', 'btnvisted', '已签到', '签到成功']):
                        return True, f"✅ {self.display_name} 签到成功"

                    # 没有明确成功标志，当作失败
                    logger.warning(f"签到按钮已点击但未检测到成功标志，URL: {self.browser.url[:80]}")
                    return False, f"❌ {self.display_name}: 签到结果不明确，请检查日志"
                else:
                    return False, f"❌ {self.display_name}: 未找到签到按钮"

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
