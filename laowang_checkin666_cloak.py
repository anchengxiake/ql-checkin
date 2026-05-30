#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
老王论坛自动签到脚本 v5.0 (CloakBrowser 版)
使用 CloakBrowser (Playwright) 替代 DrissionPage，更好的反检测能力

支持三种模式：
1. 账号密码登录模式（推荐）：自动登录获取 Cookie 并签到
2. Cookie 模式：使用已有 Cookie 签到
3. CloakBrowser 模式（新增）：反检测浏览器，通过率更高

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
CUSTOM_HOST = os.getenv('LAOWANG_CUSTOM_HOST', '')

if CUSTOM_HOST:
    BASE_URL = f"https://{CUSTOM_HOST}"
    logger.info(f"🌐 使用自定义域名解析: {CUSTOM_HOST}")
else:
    BASE_URL = "https://laowang.vip"

LOGIN_URL = f"{BASE_URL}/member.php?mod=logging&action=login"
SIGN_PAGE_URL = f"{BASE_URL}/plugin.php?id=k_misign:sign"
SIGN_API_URL = f"{BASE_URL}/plugin.php?id=k_misign:sign&operation=qiandao&format=button_inajax"

MAX_RETRIES = 3
RETRY_DELAY = 5
VERIFY_SSL = os.getenv('LAOWANG_VERIFY_SSL', 'true').lower() != 'false'
DEBUG_MODE = os.getenv('LAOWANG_DEBUG', 'false').lower() == 'true'

# CloakBrowser 模式（默认启用）
# auto = 自动检测，true = 强制使用，false = 禁用
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
        return proxy
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
    """解析 Discuz! AJAX 响应"""
    raw = resp_text.strip()

    if DEBUG_MODE:
        logger.debug(f"[AJAX原始响应] {raw[:500]}")

    cdata_match = re.search(r'<!\[CDATA\[(.*?)\]\]>', raw, re.DOTALL)
    if cdata_match:
        msg = cdata_match.group(1).strip()
        msg_clean = re.sub(r'<[^>]+>', '', msg).strip()

        success_keywords = ['签到成功', '恭喜您', '已获得奖励', '签到奖励']
        already_keywords = ['已经签到', '今日已签', '已签到', '请勿重复']
        fail_keywords = ['请先登录', '登录后', '需要登录', '登录失败', '密码错误',
                        '表单错误', '验证失败', '无权', '已过期', '已失效', 'Cookie']

        if any(k in msg_clean for k in already_keywords):
            return True, f"已签到 ({msg_clean})", raw
        if any(k in msg_clean for k in fail_keywords):
            return False, f"签到失败: {msg_clean}", raw
        if any(k in msg_clean for k in success_keywords):
            return True, f"签到成功 ({msg_clean})", raw

        logger.warning(f"未知的CDATA响应: {msg_clean[:200]}")
        return False, f"未知响应: {msg_clean[:100]}", raw

    if not raw:
        return False, "空响应", raw
    if len(raw) < 10:
        return False, f"响应过短（{len(raw)} 字节）", raw
    if raw.startswith('<!DOCTYPE') or raw.startswith('<html'):
        return False, "返回 HTML 页面而非 AJAX 数据", raw

    return False, f"非标准响应: {raw[:100]}", raw


# ============ HTTP 请求工具 ============
def request_with_retry(session, method, url, **kwargs):
    """带重试的请求"""
    import requests
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if 'timeout' not in kwargs:
        kwargs['timeout'] = 30

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
            if 'SSL' in error_str or 'TLS' in error_str or 'CERTIFICATE' in error_str:
                last_error = f"SSL/TLS证书错误: {error_str[:100]}"
                logger.warning(f"SSL错误 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")
            elif 'Name or service not known' in error_str or 'getaddrinfo' in error_str:
                last_error = f"DNS解析失败: {error_str[:100]}"
                logger.warning(f"DNS错误 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")
            else:
                last_error = f"连接错误: {error_str[:100]}"
                logger.warning(f"连接失败 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")
        except requests.exceptions.SSLError as e:
            last_error = f"SSL错误: {str(e)[:100]}"
            logger.warning(f"SSL错误 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")
        except Exception as e:
            last_error = f"请求异常: {str(e)[:100]}"
            logger.warning(f"请求异常 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")

        if attempt < MAX_RETRIES - 1:
            sleep_time = RETRY_DELAY * (attempt + 1)
            logger.info(f"⏳ {sleep_time}秒后重试...")
            time.sleep(sleep_time)

    raise Exception(f"请求失败 ({MAX_RETRIES}次重试): {last_error}")


# ============ 账号密码登录模式 (HTTP) ============
class LaowangLoginSign:
    """HTTP 登录签到模式"""

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

        class NoVerifyHTTPAdapter(HTTPAdapter):
            def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
                from urllib3.poolmanager import PoolManager
                pool_kwargs['cert_reqs'] = 'CERT_NONE'
                pool_kwargs['assert_hostname'] = False
                pool_kwargs['assert_fingerprint'] = None
                return PoolManager(connections, maxsize, block, **pool_kwargs)

        session = requests.Session()

        if CUSTOM_HOST:
            session.mount('https://', NoVerifyHTTPAdapter())

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        if CUSTOM_HOST:
            headers['Host'] = 'laowang.vip'

        session.headers.update(headers)

        proxy = get_proxies()
        if proxy:
            session.proxies.update({'http': proxy, 'https': proxy})
            logger.info(f"🌐 使用代理: {proxy}")

        session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        return session

    def login(self):
        """登录获取 Cookie"""
        try:
            logger.info(f"🔐 正在登录: {self.username}")

            logger.info("📄 获取登录页面...")
            response = request_with_retry(self.session, 'get', LOGIN_URL)
            response.encoding = 'utf-8'

            if DEBUG_MODE:
                logger.debug(f"登录页面内容: {response.text[:1000]}")

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
                if 'member.php?mod=logging&action=logout' in response.text:
                    logger.info("✅ 已经是登录状态")
                    username_match = re.search(r'title="访问我的空间">([^<]+)</a>', response.text)
                    if username_match:
                        self.display_name = username_match.group(1).strip()
                    return True, "已经是登录状态"

                if DEBUG_MODE:
                    logger.error(f"页面内容（前2000字符）: {response.text[:2000]}")
                return False, "未找到 formhash，登录失败"

            formhash = formhash_match.group(1)
            logger.info(f"✅ 获取 formhash: {formhash}")

            login_data = {
                'formhash': formhash,
                'referer': BASE_URL,
                'username': self.username,
                'password': self.password,
                'questionid': '0',
                'answer': '',
                'cookietime': '2592000',
            }

            logger.info("🔑 提交登录...")
            response = request_with_retry(
                self.session, 'post', LOGIN_URL,
                data=login_data,
                headers={'Referer': LOGIN_URL}
            )
            response.encoding = 'utf-8'

            if '登录失败' in response.text:
                error_match = re.search(r'<div[^>]*class="[^"]*alert_error[^"]*"[^>]*>(.*?)</div>', response.text, re.DOTALL)
                if error_match:
                    error_msg = re.sub(r'<[^>]+>', '', error_match.group(1)).strip()
                    return False, f"登录失败: {error_msg}"
                return False, "登录失败: 用户名或密码错误"

            logger.info("✅ 验证登录状态...")
            time.sleep(2)

            response = request_with_retry(self.session, 'get', BASE_URL)
            response.encoding = 'utf-8'

            has_logout = 'member.php?mod=logging&action=logout' in response.text
            has_userlink = re.search(r'title="访问我的空间">([^<]+)</a>', response.text) is not None

            if not has_logout and not has_userlink:
                if '登录' in response.text and '立即注册' in response.text:
                    return False, "登录失败，页面仍显示未登录状态"

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

            stats = self._extract_stats(html)

            if any(x in html for x in ['btnvisted', '已签到', '今日已签', '今日已领']):
                return 'already_signed', stats

            if any(x in html for x in ['qiandao', '签到', 'J_chkitot']):
                sign_url = self._extract_sign_url(html)
                return 'can_sign', sign_url

            if '登录' in html and '注册' in html and '立即注册' in html:
                if 'member.php?mod=logging&action=logout' not in html:
                    return 'not_logged_in', None

            return 'unknown', None

        except Exception as e:
            return 'error', str(e)

    def _extract_stats(self, html):
        """提取签到统计信息"""
        stats = {}
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
        onclick_pattern = r'<a[^>]*onclick=["\'][^"\']*?(plugin\.php\?id=k_misign:sign[^"\']+)["\']'
        match = re.search(onclick_pattern, html)
        if match:
            url = match.group(1)
            if not url.startswith('http'):
                url = urljoin(BASE_URL, url)
            return url

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
        success, msg = self.login()
        if not success:
            return False, f"❌ {self.username}: {msg}"

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

                is_success, msg_detail, raw = parse_ajax_response(resp_text)

                if is_success:
                    return True, f"✅ {self.display_name} {msg_detail}"

                if not resp_text.startswith('<!') and not resp_text.startswith('<html'):
                    if any(x in resp_text for x in ['签到成功', '恭喜您获得']):
                        return True, f"✅ {self.display_name} 签到成功"
                    if any(x in resp_text for x in ['已经签到', '已签到', '今日已签']):
                        return True, f"✅ {self.display_name} 今日已签到"

                if any(x in resp_text for x in ['验证', 'captcha', '滑块', '安全验证']):
                    return False, f"⚠️ {self.display_name} 需要滑块验证，建议使用浏览器模式"

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

        class NoVerifyHTTPAdapter(HTTPAdapter):
            def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
                from urllib3.poolmanager import PoolManager
                pool_kwargs['cert_reqs'] = 'CERT_NONE'
                pool_kwargs['assert_hostname'] = False
                pool_kwargs['assert_fingerprint'] = None
                return PoolManager(connections, maxsize, block, **pool_kwargs)

        session = requests.Session()

        if CUSTOM_HOST:
            session.mount('https://', NoVerifyHTTPAdapter())

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'identity',
            'Cookie': self.cookie,
        }

        if CUSTOM_HOST:
            headers['Host'] = 'laowang.vip'

        session.headers.update(headers)

        proxy = get_proxies()
        if proxy:
            session.proxies.update({'http': proxy, 'https': proxy})
            logger.info(f"🌐 使用代理: {proxy}")

        session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        return session

    def do_sign(self):
        """执行签到"""
        try:
            response = request_with_retry(self.session, 'get', SIGN_PAGE_URL)
            response.encoding = 'utf-8'
            html = response.text

            username_match = re.search(r'title="访问我的空间">([^<]+)</a>', html)
            if username_match:
                self.display_name = username_match.group(1).strip()

            has_logout = 'member.php?mod=logging&action=logout' in html
            has_userlink = username_match is not None

            if not has_logout and not has_userlink:
                if '登录' in html and '立即注册' in html:
                    return False, f"❌ {self.display_name}: Cookie 已失效"

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

            if any(x in html for x in ['btnvisted', '已签到', '今日已签']):
                msg = f"✅ {self.display_name} 今日已签到"
                if stats:
                    msg += f"\n   连续: {stats.get('lxdays', '-')}天 | 总计: {stats.get('lxtdays', '-')}天"
                return True, msg

            logger.info("📝 正在执行签到...")

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

            is_success, msg_detail, raw = parse_ajax_response(resp_text)

            if is_success:
                return True, f"✅ {self.display_name} {msg_detail}"

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


# ============ CloakBrowser 模式 ============
class LaowangCloakBrowserSign:
    """
    CloakBrowser 签到模式
    使用 CloakBrowser (Playwright) 的反检测能力，自动处理滑块验证
    """

    def __init__(self, username, password, index=1):
        self.username = username
        self.password = password
        self.index = index
        self.display_name = username
        self.browser = None
        self.page = None

    def _init_browser(self):
        """初始化 CloakBrowser"""
        try:
            from cloakbrowser import launch

            proxy = get_proxies()
            launch_kwargs = {
                'headless': os.getenv('LAOWANG_HEADLESS', 'false').lower() == 'true',
                'humanize': True,  # 启用人类化行为
            }

            if proxy:
                launch_kwargs['proxy'] = proxy
                launch_kwargs['geoip'] = True  # 自动匹配时区和语言

            if CUSTOM_HOST:
                # CloakBrowser 不直接支持自定义 host，需要通过代理或浏览器参数
                launch_kwargs['args'] = [f'--host-resolver-rules=MAP laowang.vip {CUSTOM_HOST}']

            logger.info("🚀 正在启动 CloakBrowser...")
            self.browser = launch(**launch_kwargs)
            self.page = self.browser.new_page()

            logger.info("✅ CloakBrowser 启动成功")
            return True

        except ImportError:
            logger.error("❌ 未安装 CloakBrowser，请运行: pip install cloakbrowser")
            return False
        except Exception as e:
            logger.error(f"❌ CloakBrowser 初始化失败: {e}")
            return False

    def _wait_for_cloudflare(self, timeout=30):
        """等待 Cloudflare 验证通过"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                title = self.page.title()
                content = self.page.content()

                # 检查是否还在 Cloudflare 验证页面
                if 'Just a moment' in title or 'Checking' in title:
                    logger.info("⏳ 等待 Cloudflare 验证...")
                    time.sleep(2)
                    continue

                # 检查是否有 Challenge 平台
                if 'challenges.cloudflare.com' in content:
                    logger.info("⏳ Cloudflare Challenge 检测中...")
                    time.sleep(2)
                    continue

                # 通过验证
                logger.info("✅ Cloudflare 验证已通过")
                return True

            except Exception as e:
                logger.debug(f"检查 Cloudflare 状态时出错: {e}")
                time.sleep(1)

        logger.warning("⚠️ Cloudflare 验证超时")
        return False

    def _check_tncode(self):
        """检查是否出现 tncode 验证码"""
        try:
            has_tncode = self.page.evaluate('''
            () => {
                var t = window.tncode;
                if (t && t._doing === false && t._result === false) {
                    var div = document.getElementById('tncode_div');
                    if (div && getComputedStyle(div).display !== 'none') {
                        return true;
                    }
                }
                return false;
            }
            ''')
            return has_tncode
        except:
            return False

    def _solve_tncode(self):
        """尝试解决 tncode 滑块验证"""
        logger.info("🤖 检测到 tncode 验证码，尝试自动解决...")

        max_attempts = 5
        for attempt in range(max_attempts):
            logger.info(f"🔄 第 {attempt+1}/{max_attempts} 次尝试...")

            # 等待图片加载
            time.sleep(2)

            # 使用 Canvas 分析获取缺口位置
            gap = self.page.evaluate('''
            () => {
                var t = window.tncode;
                var bgCanvas = document.querySelector('.tncode_canvas_bg');
                if (!bgCanvas || bgCanvas.width === 0) return -1;

                var img = (t && t._img) || document.querySelector('.tncode_div img');
                if (!img || !img.complete || img.naturalWidth === 0) return -3;

                var imgW = (t && t._img_w) || 240;
                var imgH = (t && t._img_h) || 150;
                var markW = (t && t._mark_w) || 50;
                var maxOffset = imgW - markW;

                if (t && t._draw_bg && !t._is_draw_bg) {
                    try { t._draw_bg(); } catch(e) {}
                }

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

                return bestX;
            }
            ''')

            if gap and gap > 5:
                logger.info(f"🎯 检测到缺口: {gap}px")

                # 执行拖动
                drag_result = self.page.evaluate(f'''
                () => {{
                    var IMAGE_GAP = {gap};
                    var t = window.tncode;
                    var slider = document.querySelector('.slide_block');
                    if (!t || !slider) return 'no_handler';

                    try {{ t._reset(); }} catch(e) {{}}

                    var rect = slider.getBoundingClientRect();
                    var startX = Math.round(rect.left + rect.width / 2);
                    var startY = Math.round(rect.top + rect.height / 2);
                    var SCREEN_DIST = IMAGE_GAP;

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

                    var steps = rnd(25, 40);
                    var times = new Array(steps);
                    var base = rnd(1200, 2200) / steps;
                    for (var i = 0; i < steps; i++) {{
                        var t_step = base + rnd(-15, 15);
                        if (Math.random() < 0.05) t_step += rnd(20, 60);
                        times[i] = Math.max(2, Math.round(t_step));
                    }}

                    var xs = new Array(steps);
                    for (var i = 0; i < steps; i++) {{
                        var frac = (i + 1) / steps;
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

                    t._block_start_move(makeME('mousedown', startX, startY, false));

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
                        var y = startY + rnd(-5, 5);
                        t._block_on_move(makeME('mousemove', x, y, false));
                    }}

                    var wait = rnd(30, 60);
                    var endWait = Date.now() + wait;
                    while (Date.now() < endWait) {{}}
                    var overshoot = rnd(1, 4);
                    t._block_on_move(makeME('mousemove', startX + SCREEN_DIST + overshoot, startY, false));
                    wait = rnd(35, 65);
                    endWait = Date.now() + wait;
                    while (Date.now() < endWait) {{}}
                    t._block_on_move(makeME('mousemove', startX + SCREEN_DIST, startY, false));

                    wait = rnd(40, 80);
                    endWait = Date.now() + wait;
                    while (Date.now() < endWait) {{}}

                    t._block_on_end(makeME('mouseup', startX + SCREEN_DIST, startY, true));

                    var trackLen = t._track_data ? t._track_data.length : 0;
                    return 'ok: track=' + trackLen + ' offset=' + t._mark_offset;
                }}
                ''')

                logger.info(f"🖱️ 拖动结果: {drag_result}")

                # 等待验证结果
                time.sleep(2)

                # 检查是否通过
                passed = self.page.evaluate('''
                () => {
                    var t = window.tncode;
                    if (t && t._result === true) return true;
                    var infoInput = document.getElementById('clicaptcha-submit-info');
                    if (infoInput && infoInput.value && infoInput.value.indexOf('_ok') > -1) return true;
                    return false;
                }
                ''')

                if passed:
                    logger.info("✅ tncode 验证通过！")
                    return True

                # 刷新验证码
                self.page.evaluate('''
                () => {
                    var t = window.tncode;
                    if (t && typeof t.refresh === 'function') {
                        t.refresh();
                    } else {
                        var btn = document.querySelector('.tncode_refresh');
                        if (btn) btn.click();
                    }
                }
                ''')
                time.sleep(2)
            else:
                logger.info(f"⚠️ 缺口检测失败 (返回值: {gap})，刷新重试...")
                self.page.evaluate('''
                () => {
                    var t = window.tncode;
                    if (t && typeof t.refresh === 'function') t.refresh();
                }
                ''')
                time.sleep(2)

        logger.error("❌ tncode 验证失败，已达最大尝试次数")
        return False

    def _extract_cookies(self):
        """从浏览器提取 Cookie"""
        try:
            cookies = self.page.context.cookies()
            if not cookies:
                return ""

            cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
            return cookie_str
        except Exception as e:
            logger.debug(f"提取Cookie失败: {e}")
            return ""

    def do_sign(self):
        """执行 CloakBrowser 签到"""
        if not self._init_browser():
            return False, "CloakBrowser 初始化失败"

        try:
            login_attempts = 3

            for login_try in range(login_attempts):
                if login_try > 0:
                    logger.info(f"🔄 登录重试 {login_try+1}/{login_attempts}...")
                    time.sleep(2)

                try:
                    # 访问登录页面
                    logger.info("🌐 正在访问登录页面...")
                    self.page.goto(LOGIN_URL, wait_until='domcontentloaded', timeout=30000)
                    time.sleep(2)

                    # 等待 Cloudflare
                    self._wait_for_cloudflare()

                    # 输入账号密码
                    logger.info(f"🔐 正在输入账号: {self.username}")

                    # 等待输入框出现
                    self.page.wait_for_selector('input[name="username"]', timeout=10000)
                    self.page.fill('input[name="username"]', self.username)
                    time.sleep(0.5)
                    self.page.fill('input[name="password"]', self.password)
                    time.sleep(0.5)

                    # 检查是否需要 tncode 验证
                    if self._check_tncode():
                        logger.info("🤖 检测到 tncode 验证码，点击触发...")
                        self.page.click('.tncode')
                        time.sleep(2)

                        if not self._solve_tncode():
                            logger.warning("⚠️ tncode 验证失败，重试登录流程...")
                            continue

                    # 提交登录
                    logger.info("🔑 正在提交登录...")
                    self.page.evaluate('''
                    () => {
                        var form = document.querySelector("form[name='login']");
                        if (form) form.submit();
                    }
                    ''')

                    # 等待跳转
                    time.sleep(4)

                    # 验证登录成功
                    current_html = self.page.content()
                    current_url = self.page.url

                    if 'member.php?mod=logging&action=logout' in current_html:
                        logger.info("✅ 检测到 logout 链接，登录成功")
                        break
                    if 'succeedmessage' in current_html or '欢迎您回来' in current_html:
                        logger.info("✅ 检测到登录成功消息")
                        time.sleep(2)
                        break
                    if 'member.php?mod=logging' not in current_url:
                        logger.info(f"✅ 已跳转离开登录页: {current_url[:60]}")
                        break

                    logger.warning(f"⚠️ 登录可能未成功，当前 URL: {current_url[:80]}")

                except Exception as e:
                    logger.error(f"登录流程异常: {e}")
                    if login_try < login_attempts - 1:
                        continue
                    return False, f"❌ {self.username}: CloakBrowser 操作失败: {e}"

            # 确认登录状态
            current_html = self.page.content()
            current_url = self.page.url
            logged_in = (
                'member.php?mod=logging&action=logout' in current_html or
                '退出' in current_html or
                '我的' in current_html or
                ('member.php?mod=logging' not in current_url and 'laowang.vip' in current_url)
            )

            if not logged_in:
                return False, f"❌ {self.username}: 登录失败（{login_attempts}次尝试后仍失败）"

            # 提取用户名
            try:
                username_match = re.search(r'title="访问我的空间">([^<]+)</a>', current_html)
                if username_match:
                    self.display_name = username_match.group(1).strip()
            except:
                pass

            logger.info(f"✅ 登录成功: {self.display_name}")

            # 提取 Cookie
            cookie_str = self._extract_cookies()
            if cookie_str:
                logger.info(f"📋 已提取 Cookie（可复制到环境变量使用）:\n{cookie_str[:200]}...")

            # 访问签到页面
            logger.info("📝 正在访问签到页面...")
            self.page.goto(SIGN_PAGE_URL, wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)

            # 检查是否已签到
            page_html = self.page.content()
            if any(x in page_html for x in ['今日已签', 'btnvisted', '已签到']):
                return True, f"✅ {self.display_name} 今日已签到"

            # 点击签到按钮
            try:
                clicked = self.page.evaluate('''
                () => {
                    var btn = document.querySelector('.btn.J_chkitot') || document.querySelector('[class*="chkitot"]');
                    if (btn) { btn.click(); return true; }
                    return false;
                }
                ''')

                if clicked:
                    time.sleep(2)

                    # 检查是否需要 tncode 验证
                    if self._check_tncode():
                        logger.info("🤖 签到需要 tncode 验证...")
                        self.page.click('.tncode')
                        time.sleep(2)
                        if not self._solve_tncode():
                            return False, f"❌ {self.display_name}: 签到 tncode 验证失败"

                    # 检查签到结果
                    time.sleep(2)
                    result_html = self.page.content()

                    if any(x in result_html for x in ['今日已签', 'btnvisted', '已签到', '签到成功']):
                        return True, f"✅ {self.display_name} 签到成功"

                    # 检查是否跳转到了验证页面
                    if '验证页面' in result_html or '请点击下面的按钮验证' in result_html:
                        logger.info("🤖 检测到验证页面，尝试解决...")
                        if self._check_tncode():
                            self.page.click('.tncode')
                            time.sleep(2)
                            if self._solve_tncode():
                                # 提交验证
                                self.page.click('#submit-btn')
                                time.sleep(3)
                                result_html = self.page.content()
                                if any(x in result_html for x in ['今日已签', '已签到', '签到成功']):
                                    return True, f"✅ {self.display_name} 签到成功"

                    return False, f"❌ {self.display_name}: 签到结果不明确，请检查日志"
                else:
                    return False, f"❌ {self.display_name}: 未找到签到按钮"

            except Exception as e:
                return False, f"❌ {self.display_name}: 签到操作失败: {e}"

        finally:
            if self.browser:
                try:
                    self.browser.close()
                except:
                    pass


# ============ 账号解析 ============
def parse_accounts(env_str):
    """解析账号配置"""
    if not env_str:
        return []

    accounts = []
    items = re.split(r'[&\n]', env_str.strip())

    for item in items:
        item = item.strip()
        if not item:
            continue

        if ':' in item and '=' not in item.split(':')[0]:
            parts = item.split(':', 1)
            if len(parts) == 2:
                username, password = parts
                if not any(x in username for x in ['=', ';', '__cf', 'auth', 'uid']):
                    accounts.append({
                        'type': 'password',
                        'username': username.strip(),
                        'password': password.strip()
                    })
                    continue

        accounts.append({
            'type': 'cookie',
            'cookie': item
        })

    return accounts


# ============ 主程序 ============
def main():
    """主函数"""
    is_qinglong = os.path.exists('/ql') or 'QL_DIR' in os.environ

    print("""
╔══════════════════════════════════════════════╗
║     老王论坛自动签到脚本 v5.0                ║
║     CloakBrowser 反检测版                    ║
║     支持 账号密码 / Cookie / 浏览器 三模式    ║
╚══════════════════════════════════════════════╝
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

🔧 配置方式（四选一）:

方式1 - CloakBrowser 模式（推荐，反检测最强）:
LAOWANG_ACCOUNT=用户名:密码
LAOWANG_BROWSER_MODE=true

方式2 - 账号密码 + 浏览器模式（DrissionPage）:
LAOWANG_ACCOUNT=用户名:密码
LAOWANG_BROWSER_MODE=drissionpage

方式3 - 账号密码（HTTP模式，可能遇到滑块）:
LAOWANG_ACCOUNT=用户名:密码

方式4 - Cookie（无需处理滑块）:
LAOWANG_COOKIE=cookie1&cookie2

🌐 代理配置（国内需要）:
LAOWANG_PROXY=http://127.0.0.1:7890

💡 提示:
- CloakBrowser 模式需要: pip install cloakbrowser
- Cookie 模式最稳定，需要定期更新 Cookie
- 调试模式: LAOWANG_DEBUG=true
"""
        print(error_msg)
        push_notify("老王论坛签到失败", error_msg)
        sys.exit(1)

    # 解析账号
    accounts = parse_accounts(env_str)
    print(f"✅ 检测到 {len(accounts)} 个账号\n")

    # 检查可用的浏览器模式
    cloakbrowser_available = False
    drissionpage_available = False

    try:
        import cloakbrowser
        cloakbrowser_available = True
        logger.info("✅ CloakBrowser 可用")
    except ImportError:
        pass

    try:
        import DrissionPage
        drissionpage_available = True
        logger.info("✅ DrissionPage 可用")
    except ImportError:
        pass

    # 浏览器模式选择
    if BROWSER_MODE == 'cloakbrowser':
        use_browser = 'cloakbrowser'
    elif BROWSER_MODE == 'drissionpage':
        use_browser = 'drissionpage' if drissionpage_available else None
    elif BROWSER_MODE == 'true':
        # 优先使用 CloakBrowser，其次 DrissionPage
        if cloakbrowser_available:
            use_browser = 'cloakbrowser'
        elif drissionpage_available:
            use_browser = 'drissionpage'
        else:
            use_browser = None
    elif BROWSER_MODE == 'false':
        use_browser = None
    else:  # auto
        # 优先使用 CloakBrowser
        if cloakbrowser_available:
            use_browser = 'cloakbrowser'
        elif drissionpage_available:
            use_browser = 'drissionpage'
        else:
            use_browser = None

    if use_browser == 'cloakbrowser':
        print("🤖 CloakBrowser 模式已启用（反检测 + 人类化行为）\n")
    elif use_browser == 'drissionpage':
        print("🤖 DrissionPage 模式已启用\n")
    else:
        print("📡 HTTP 模式（可能遇到滑块验证）\n")

    # 签到结果
    results = []

    for idx, account in enumerate(accounts, 1):
        print(f"{'─' * 50}")
        print(f"🙍🏻 账号 {idx}/{len(accounts)}")
        print(f"{'─' * 50}")

        if account['type'] == 'password':
            if use_browser == 'cloakbrowser':
                signer = LaowangCloakBrowserSign(
                    account['username'],
                    account['password'],
                    idx
                )
                success, msg = signer.do_sign()

                # 如果 CloakBrowser 失败，尝试其他模式
                if not success and drissionpage_available:
                    logger.info("🔄 CloakBrowser 失败，尝试 DrissionPage...")
                    try:
                        # 导入 DrissionPage 版本
                        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                        from laowang_checkin666 import LaowangBrowserSign
                        signer = LaowangBrowserSign(
                            account['username'],
                            account['password'],
                            idx
                        )
                        success, msg = signer.do_sign()
                    except Exception as e:
                        logger.error(f"DrissionPage 失败: {e}")

                if not success:
                    logger.info("🔄 浏览器模式失败，尝试 HTTP 模式...")
                    signer = LaowangLoginSign(
                        account['username'],
                        account['password'],
                        idx
                    )
                    success, msg = signer.do_sign()

            elif use_browser == 'drissionpage':
                try:
                    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                    from laowang_checkin666 import LaowangBrowserSign
                    signer = LaowangBrowserSign(
                        account['username'],
                        account['password'],
                        idx
                    )
                    success, msg = signer.do_sign()
                except Exception as e:
                    logger.error(f"DrissionPage 失败: {e}")
                    signer = LaowangLoginSign(
                        account['username'],
                        account['password'],
                        idx
                    )
                    success, msg = signer.do_sign()
            else:
                signer = LaowangLoginSign(
                    account['username'],
                    account['password'],
                    idx
                )
                success, msg = signer.do_sign()
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
        first_line = msg.split('\n')[0]
        summary += f"\n{status} 账号{idx}: {first_line}"

    print(summary)
    print(f"\n⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 推送通知
    push_notify("老王论坛签到结果", summary)


if __name__ == "__main__":
    main()
