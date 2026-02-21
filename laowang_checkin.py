#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
老王论坛自动签到脚本 v4.0
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
BASE_URL = "https://laowang.vip"
LOGIN_URL = f"{BASE_URL}/member.php?mod=logging&action=login"
SIGN_PAGE_URL = f"{BASE_URL}/plugin.php?id=k_misign:sign"
SIGN_API_URL = f"{BASE_URL}/plugin.php?id=k_misign:sign&operation=qiandao&format=button_inajax"

# 请求重试配置
MAX_RETRIES = 3
RETRY_DELAY = 5

# 截图配置（青龙面板建议关闭或配置正确路径）
ENABLE_SCREENSHOT = os.getenv('LAOWANG_SCREENSHOT', 'false').lower() == 'true'
SCREENSHOT_PATH = os.getenv('LAOWANG_SCREENSHOT_PATH', './laowang_screenshot.png')

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

# ============ 请求工具（带重试） ============
def request_with_retry(session, method, url, **kwargs):
    """带重试的请求"""
    import requests
    
    # 默认超时
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 30
    
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
            last_error = f"连接错误: {str(e)[:100]}"
            logger.warning(f"连接失败 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")
        except Exception as e:
            last_error = f"请求异常: {str(e)[:100]}"
            logger.warning(f"请求异常 (尝试 {attempt+1}/{MAX_RETRIES}): {last_error}")
        
        if attempt < MAX_RETRIES - 1:
            sleep_time = RETRY_DELAY * (attempt + 1)
            logger.info(f"⏳ {RETRY_DELAY}秒后重试...")
            time.sleep(sleep_time)
    
    raise Exception(f"请求失败 ({MAX_RETRIES}次重试): {last_error}")

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
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': BASE_URL,
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # 设置代理
        proxies = get_proxies()
        if proxies:
            session.proxies.update(proxies)
            logger.info(f"🌐 使用代理: {proxies['http']}")
        
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
            
            # 提取 formhash
            formhash_match = re.search(r'name="formhash" value="([a-f0-9]{8})"', response.text)
            if not formhash_match:
                formhash_match = re.search(r'formhash=([a-f0-9]{8})', response.text)
            
            if not formhash_match:
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
            
            # 检查是否已登录
            if '登录' in response.text and '立即注册' in response.text:
                if 'member.php?mod=logging&action=logout' not in response.text:
                    return False, "登录失败，无法验证登录状态"
            
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
                response = request_with_retry(self.session, 'get', sign_url)
                response.encoding = 'utf-8'
                
                resp_text = response.text
                
                # 成功标识
                if any(x in resp_text for x in ['成功', '签到成功', '恭喜', 'CDATA']):
                    return True, f"✅ {self.display_name} 签到成功"
                
                # 已签到
                if any(x in resp_text for x in ['已经签到', '已签到', '今日已签']):
                    return True, f"✅ {self.display_name} 今日已签到"
                
                # 需要验证
                if any(x in resp_text for x in ['验证', 'captcha', '滑块', '安全验证']):
                    return False, f"⚠️ {self.display_name} 需要滑块验证，建议手动签到一次"
                
                return False, f"❌ {self.display_name} 签到响应异常"
                
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
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cookie': self.cookie,
        })
        
        # 设置代理
        proxies = get_proxies()
        if proxies:
            session.proxies.update(proxies)
            logger.info(f"🌐 使用代理: {proxies['http']}")
        
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
            if '登录' in html and '立即注册' in html:
                if 'member.php?mod=logging&action=logout' not in html:
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
            
            response = request_with_retry(self.session, 'get', sign_url)
            response.encoding = 'utf-8'
            
            resp_text = response.text
            
            # 成功
            if any(x in resp_text for x in ['成功', '签到成功', '恭喜', 'CDATA']):
                return True, f"✅ {self.display_name} 签到成功"
            
            # 已签到
            if any(x in resp_text for x in ['已经签到', '已签到', '今日已签']):
                return True, f"✅ {self.display_name} 今日已签到"
            
            # 需要验证
            if any(x in resp_text for x in ['验证', 'captcha', '滑块']):
                return False, f"⚠️ {self.display_name} 需要滑块验证"
            
            return False, f"❌ {self.display_name} 签到失败"
            
        except Exception as e:
            return False, f"❌ {self.display_name}: {str(e)[:150]}"


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
║     老王论坛自动签到脚本 v4.0             ║
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

🔧 配置方式（二选一）:

方式1 - 账号密码（推荐）:
LAOWANG_ACCOUNT=用户名1:密码1&用户名2:密码2

方式2 - Cookie:
LAOWANG_COOKIE=cookie1&cookie2

🌐 代理配置（国内需要）:
LAOWANG_PROXY=http://127.0.0.1:7890
"""
        print(error_msg)
        push_notify("老王论坛签到失败", error_msg)
        sys.exit(1)
    
    # 解析账号
    accounts = parse_accounts(env_str)
    print(f"✅ 检测到 {len(accounts)} 个账号\n")
    
    # 签到结果
    results = []
    
    for idx, account in enumerate(accounts, 1):
        print(f"{'─' * 50}")
        print(f"🙍🏻 账号 {idx}/{len(accounts)}")
        print(f"{'─' * 50}")
        
        if account['type'] == 'password':
            # 账号密码模式
            signer = LaowangLoginSign(
                account['username'],
                account['password'],
                idx
            )
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
