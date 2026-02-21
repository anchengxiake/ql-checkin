#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
老王论坛自动签到脚本（新版 - 支持滑块验证）
支持两种模式：
1. DrissionPage 模式（推荐）：自动处理滑块验证
2. Cookie 模式（备选）：轻量级，仅发送签到请求

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
from urllib.parse import urljoin, urlparse

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============ 配置常量 ============
BASE_URL = "https://laowang.vip"
SIGN_PAGE_URL = f"{BASE_URL}/plugin.php?id=k_misign:sign"
SIGN_API_URL = f"{BASE_URL}/plugin.php?id=k_misign:sign&operation=qiandao&format=button_inajax"

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

# ============ Cookie 模式 ============
class LaowangCookieSign:
    """Cookie 模式签到（轻量版）"""
    
    def __init__(self, cookie, index=1):
        self.cookie = cookie
        self.index = index
        self.session = self._create_session()
        self.username = None
        
    def _create_session(self):
        """创建请求会话"""
        import requests
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': BASE_URL,
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
        
        # 设置代理
        proxies = get_proxies()
        if proxies:
            session.proxies.update(proxies)
            logger.info(f"🌐 使用代理: {proxies['http']}")
        
        # 解析 Cookie
        self._parse_cookie(session)
        return session
    
    def _parse_cookie(self, session):
        """解析 Cookie 字符串"""
        if not self.cookie:
            return
        
        # 处理多种分隔符
        cookie_str = self.cookie.strip()
        if '\n' in cookie_str:
            parts = cookie_str.split('\n')
        else:
            parts = re.split(r'[;&]', cookie_str)
        
        for part in parts:
            part = part.strip()
            if '=' in part:
                key, value = part.split('=', 1)
                key = key.strip()
                value = value.strip()
                if key and value:
                    session.cookies.set(key, value)
        
        # 添加额外的请求头
        session.headers['Cookie'] = self.cookie
    
    def get_sign_status(self):
        """获取签到状态"""
        import requests
        
        try:
            response = self.session.get(SIGN_PAGE_URL, timeout=30)
            response.encoding = 'utf-8'
            html = response.text
            
            # 检查登录状态
            if '登录' in html and '注册' in html and '立即注册' in html:
                return None, "Cookie 已失效或未登录"
            
            # 提取用户名
            username_patterns = [
                r'title="访问我的空间">([^<]+)</a>',
                r'class="username">([^<]+)</',
                r'uid=\d+">([^<]+)</a>',
                r'欢迎回来，([^<]+)',
            ]
            for pattern in username_patterns:
                match = re.search(pattern, html)
                if match:
                    self.username = match.group(1).strip()
                    break
            
            if not self.username:
                self.username = f"账号{self.index}"
            
            # 检查签到状态
            # 已签到标识
            if any(x in html for x in ['btnvisted', '已签到', '今日已签', '今日已领']):
                # 提取签到统计
                stats = self._extract_stats(html)
                return self.username, ('already_signed', stats)
            
            # 检查是否有签到按钮
            if any(x in html for x in ['qiandao', '签到', 'J_chkitot']):
                # 提取签到链接
                sign_url = self._extract_sign_url(html)
                return self.username, ('can_sign', sign_url)
            
            # 需要滑块验证
            if any(x in html for x in ['验证', 'captcha', '滑块', '安全验证']):
                return self.username, 'need_captcha'
            
            return self.username, 'unknown'
            
        except requests.exceptions.ProxyError as e:
            return None, f"代理错误: {str(e)[:100]}"
        except requests.exceptions.Timeout:
            return None, "请求超时"
        except requests.exceptions.ConnectionError as e:
            return None, f"连接错误: {str(e)[:100]}"
        except Exception as e:
            return None, f"请求异常: {str(e)[:100]}"
    
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
            else:
                # 尝试从文本中提取
                text_patterns = {
                    'lxdays': r'连续签到[：:]?\s*(\d+)\s*天',
                    'lxlevel': r'等级[：:]?\s*(\d+)',
                    'lxtdays': r'总签到[：:]?\s*(\d+)\s*天',
                }
                if key in text_patterns:
                    match = re.search(text_patterns[key], html)
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
        
        # 默认签到链接
        return SIGN_API_URL
    
    def do_sign(self):
        """执行签到"""
        import requests
        
        username, status = self.get_sign_status()
        
        if status == "Cookie 已失效或未登录":
            return False, "❌ Cookie 已失效，请重新获取"
        
        if not username:
            return False, f"❌ {status}"
        
        # 已签到
        if isinstance(status, tuple) and status[0] == 'already_signed':
            stats = status[1] if len(status) > 1 else {}
            msg = f"✅ {username} 今日已签到"
            if stats:
                msg += f"\n   连续签到: {stats.get('lxdays', '-')} 天"
                msg += f" | 总签到: {stats.get('lxtdays', '-')} 天"
                msg += f" | 等级: Lv.{stats.get('lxlevel', '-')}"
            return True, msg
        
        # 需要滑块验证
        if status == 'need_captcha':
            return False, f"⚠️ {username} 需要滑块验证，建议切换到浏览器模式"
        
        # 可以签到
        if isinstance(status, tuple) and status[0] == 'can_sign':
            sign_url = status[1] if len(status) > 1 else SIGN_API_URL
            
            try:
                logger.info(f"📝 正在请求签到: {sign_url[:80]}...")
                
                response = self.session.get(sign_url, timeout=30)
                response.encoding = 'utf-8'
                
                # 检查响应
                resp_text = response.text
                
                # 成功标识
                if any(x in resp_text for x in ['成功', '签到成功', '恭喜', 'CDATA']):
                    return True, f"✅ {username} 签到成功"
                
                # 已签到
                if any(x in resp_text for x in ['已经签到', '已签到', '今日已签']):
                    return True, f"✅ {username} 今日已签到"
                
                # 需要验证
                if any(x in resp_text for x in ['验证', 'captcha', '滑块', '安全验证']):
                    return False, f"⚠️ {username} 需要滑块验证"
                
                return False, f"❌ {username} 签到响应异常"
                
            except Exception as e:
                return False, f"❌ {username} 签到请求失败: {str(e)[:100]}"
        
        return False, f"❌ {username} 未知状态: {status}"


# ============ DrissionPage 模式 ============
class LaowangBrowserSign:
    """浏览器模式签到（支持滑块验证）"""
    
    def __init__(self, cookie, index=1):
        self.cookie = cookie
        self.index = index
        self.username = f"账号{index}"
        self.page = None
        
    def _init_browser(self):
        """初始化浏览器"""
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
            
            # 配置浏览器选项
            co = ChromiumOptions()
            co.headless(True)  # 无头模式
            co.set_argument('--no-sandbox')
            co.set_argument('--disable-gpu')
            co.set_argument('--disable-dev-shm-usage')
            co.set_argument('--disable-setuid-sandbox')
            co.set_argument('--disable-blink-features=AutomationControlled')
            co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36')
            
            # 设置代理
            proxies = get_proxies()
            if proxies:
                proxy_url = proxies.get('http', '')
                if proxy_url:
                    co.set_proxy(proxy_url)
            
            self.page = ChromiumPage(co)
            return True
            
        except ImportError:
            logger.error("❌ 未安装 DrissionPage，请运行: pip install DrissionPage")
            return False
        except Exception as e:
            logger.error(f"❌ 浏览器初始化失败: {e}")
            return False
    
    def do_sign(self):
        """执行浏览器签到"""
        if not self._init_browser():
            return False, "浏览器初始化失败"
        
        try:
            # 访问签到页面（在get中传入headers）
            logger.info("🌐 正在访问签到页面...")
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36',
                'Referer': BASE_URL
            }
            
            # 尝试多种方式设置cookie
            try:
                # 方式1: 使用set_headers
                self.page.set.headers(headers)
            except:
                pass
            
            self.page.get(SIGN_PAGE_URL)
            time.sleep(3)
            
            # 检查登录状态
            page_text = self.page.html
            if '登录' in page_text and '注册' in page_text:
                return False, "❌ Cookie 已失效"
            
            # 提取用户名
            try:
                username_elem = self.page.ele('css:a[title="访问我的空间"]', timeout=2)
                if username_elem:
                    self.username = username_elem.text
            except:
                pass
            
            # 检查是否已签到
            if any(x in page_text for x in ['btnvisted', '已签到', '今日已签']):
                return True, f"✅ {self.username} 今日已签到"
            
            # 查找签到按钮
            try:
                # 保存页面截图用于调试
                try:
                    self.page.get_screenshot(path=f'/tmp/laowang_page_{self.index}.png', full_page=True)
                    logger.info(f"📸 页面截图已保存到 /tmp/laowang_page_{self.index}.png")
                except:
                    pass
                
                # 输出页面部分内容用于调试
                page_html = self.page.html
                logger.debug(f"页面HTML前2000字符: {page_html[:2000]}")
                
                # 尝试多种选择器
                sign_selectors = [
                    'css:a.J_chkitot',
                    'css:a[onclick*="qiandao"]',
                    'css:#fx_checkin_b a',
                    'css:.btn.J_chkitot',
                    'css:a[href*="operation=qiandao"]',
                    'css:button.J_chkitot',
                    'css:.J_chkitot',
                    'css:.checkin-btn',
                    'css:#k_misign_signbtn a',
                    'css:.sign-btn',
                    'css:a:contains(签到)',
                    'css:button:contains(签到)',
                ]
                
                sign_btn = None
                used_selector = None
                for selector in sign_selectors:
                    try:
                        sign_btn = self.page.ele(selector, timeout=2)
                        if sign_btn and sign_btn.is_displayed():
                            used_selector = selector
                            logger.info(f"✅ 找到签到按钮: {selector}")
                            break
                    except Exception as e:
                        logger.debug(f"选择器 {selector} 未找到: {e}")
                        continue
                
                if not sign_btn:
                    # 尝试通过文本查找
                    logger.info("🔍 尝试通过文本查找签到按钮...")
                    try:
                        sign_btn = self.page.ele('text:签到', timeout=3)
                        if sign_btn:
                            used_selector = "text:签到"
                            logger.info("✅ 通过文本找到签到按钮")
                    except:
                        pass
                
                if not sign_btn:
                    # 检查页面是否包含签到相关文字
                    if '签到' not in page_html and 'qiandao' not in page_html.lower():
                        return False, f"❌ {self.username} 页面中未找到签到相关内容，可能已签到或Cookie失效"
                    else:
                        logger.warning(f"页面包含签到文字但未找到按钮，可能是已签到或特殊状态")
                        # 再次检查是否已签到
                        if any(x in page_html for x in ['btnvisted', '已签到', '今日已签', '已领取']):
                            return True, f"✅ {self.username} 今日已签到"
                        return False, f"❌ {self.username} 页面包含签到文字但未找到签到按钮，请检查页面结构"
                
                # 点击签到
                logger.info(f"🖱️  正在点击签到按钮 (选择器: {used_selector})...")
                try:
                    sign_btn.click()
                except Exception as e:
                    # 尝试JavaScript点击
                    try:
                        self.page.run_js("arguments[0].click();", sign_btn)
                    except:
                        return False, f"❌ {self.username} 点击签到按钮失败: {e}"
                
                # 等待响应
                logger.info("⏳ 等待响应...")
                time.sleep(5)
                
                # 检查是否有滑块验证或弹窗
                page_text = self.page.html
                
                # 检查是否有iframe（可能包含滑块）
                try:
                    iframes = self.page.eles('css:iframe', timeout=2)
                    if iframes:
                        logger.info(f"🖼️  检测到 {len(iframes)} 个iframe，尝试获取iframe内容...")
                        # 尝试通过JS获取iframe内容
                        for i, iframe in enumerate(iframes):
                            try:
                                iframe_html = self.page.run_js(
                                    "return document.querySelectorAll('iframe')[arguments[0]].contentDocument.body.innerHTML;", 
                                    i
                                )
                                if iframe_html and any(x in iframe_html for x in ['验证', 'captcha', '滑块']):
                                    logger.info(f"iframe {i} 包含验证内容")
                                    # 在iframe中查找并点击滑块
                                    try:
                                        self.page.run_js(
                                            "document.querySelectorAll('iframe')[arguments[0]].contentDocument.querySelector('.tncode, .captcha, [class*=slider]').click();",
                                            i
                                        )
                                        time.sleep(3)
                                    except:
                                        pass
                                break
                            except:
                                pass
                except Exception as e:
                    logger.debug(f"检查iframe失败: {e}")
                
                # 检查滑块验证
                if any(x in page_text.lower() for x in ['验证', 'captcha', '滑块', 'tncode', '安全验证', '点击进行']):
                    logger.info("🤖 检测到滑块验证，尝试自动处理...")
                    
                    # 尝试多种滑块选择器
                    slider_selectors = [
                        'css:.tncode',
                        'css:.tncode-text',
                        'css:#tncode_div',
                        'css:.captcha',
                        'css:[class*="captcha"]',
                        'css:[class*="slider"]',
                    ]
                    
                    for selector in slider_selectors:
                        try:
                            slider = self.page.ele(selector, timeout=2)
                            if slider and slider.is_displayed():
                                logger.info(f"找到滑块元素: {selector}")
                                slider.click()
                                time.sleep(3)
                                break
                        except:
                            continue
                    
                    # 等待验证完成（最多30秒）
                    logger.info("⏳ 等待验证完成...")
                    for i in range(15):
                        time.sleep(2)
                        page_text = self.page.html
                        if any(x in page_text for x in ['成功', '已签到', '恭喜', '签到成功']):
                            logger.info("✅ 验证完成")
                            break
                        # 检查验证是否失败
                        if any(x in page_text for x in ['失败', '错误', 'error', 'fail']):
                            logger.warning("⚠️ 验证可能失败")
                            break
                
                # 检查结果
                page_text = self.page.html
                logger.info(f"响应页面内容摘要: {page_text[:800]}")
                
                # 成功的各种可能提示
                success_keywords = ['成功', '签到成功', '恭喜', '已签到', '签到完成', 'success', 'qiandao_success']
                already_keywords = ['已经签到', '今日已签', '已领取', 'already', '今天已经']
                fail_keywords = ['失败', '错误', 'fail', 'error', '无法', '不能']
                
                if any(x in page_text for x in success_keywords):
                    return True, f"✅ {self.username} 签到成功"
                elif any(x in page_text for x in already_keywords):
                    return True, f"✅ {self.username} 今日已签到"
                elif any(x in page_text for x in fail_keywords):
                    return False, f"❌ {self.username} 签到失败，请检查日志"
                else:
                    # 尝试刷新页面再检查一次
                    logger.info("🔄 刷新页面再次检查签到状态...")
                    self.page.get(SIGN_PAGE_URL)
                    time.sleep(3)
                    page_text = self.page.html
                    
                    if any(x in page_text for x in ['btnvisted', '已签到', '今日已签']):
                        return True, f"✅ {self.username} 今日已签到"
                    else:
                        return False, f"⚠️ {self.username} 签到结果未知，请手动检查。页面内容: {page_text[:300]}"
                    
            except Exception as e:
                return False, f"❌ {self.username} 签到操作失败: {str(e)[:100]}"
                
        finally:
            # 关闭浏览器
            if self.page:
                try:
                    self.page.quit()
                except:
                    pass


# ============ 主程序 ============
def parse_cookies(cookie_str):
    """解析多账号 Cookie"""
    if not cookie_str:
        return []
    
    # 支持换行或 & 分隔
    cookies = re.split(r'[\n&]', cookie_str.strip())
    return [c.strip() for c in cookies if c.strip()]

def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════╗
║     老王论坛自动签到脚本 v3.0             ║
║     支持 Cookie / DrissionPage 双模式    ║
╚══════════════════════════════════════════╝
""")
    
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 随机延迟
    max_delay = int(os.getenv('MAX_RANDOM_DELAY', '300'))
    use_random = os.getenv('RANDOM_SIGNIN', 'true').lower() == 'true'
    
    if use_random and max_delay > 0:
        delay = random.randint(0, max_delay)
        wait_countdown(delay, "老王论坛签到")
    
    # 获取配置
    cookie_str = os.getenv('LAOWANG_COOKIE', '').strip()
    use_browser = os.getenv('LAOWANG_BROWSER', 'false').lower() == 'true'
    
    if not cookie_str:
        error_msg = """❌ 未配置 LAOWANG_COOKIE 环境变量

🔧 获取 Cookie 方法:
1. 浏览器登录老王论坛: https://laowang.vip
2. 按 F12 → Network → 任意请求 → Request Headers → 复制 Cookie
3. 添加到青龙环境变量 LAOWANG_COOKIE

💡 多账号用 & 或换行分隔:
LAOWANG_COOKIE=cookie1&cookie2

🌐 如需要代理:
LAOWANG_PROXY=http://127.0.0.1:7890

🤖 如需处理滑块验证，启用浏览器模式:
LAOWANG_BROWSER=true
（需安装: pip install DrissionPage）
"""
        print(error_msg)
        push_notify("老王论坛签到失败", error_msg)
        sys.exit(1)
    
    # 解析多账号
    cookies = parse_cookies(cookie_str)
    print(f"✅ 检测到 {len(cookies)} 个账号\n")
    
    # 签到结果
    results = []
    
    for idx, cookie in enumerate(cookies, 1):
        print(f"{'─' * 50}")
        print(f"🙍🏻 账号 {idx}/{len(cookies)}")
        print(f"{'─' * 50}")
        
        # 选择签到模式
        if use_browser:
            try:
                signer = LaowangBrowserSign(cookie, idx)
                success, msg = signer.do_sign()
            except Exception as e:
                success = False
                msg = f"❌ 浏览器模式失败: {str(e)[:100]}，尝试 Cookie 模式..."
                print(msg)
                # 失败时回退到 Cookie 模式
                signer = LaowangCookieSign(cookie, idx)
                success, msg = signer.do_sign()
        else:
            signer = LaowangCookieSign(cookie, idx)
            success, msg = signer.do_sign()
        
        results.append((idx, success, msg))
        print(msg)
        
        # 账号间延迟
        if idx < len(cookies):
            delay = random.uniform(3, 8)
            print(f"\n⏱️ 等待 {delay:.1f} 秒后处理下一个账号...")
            time.sleep(delay)
    
    # 汇总结果
    print(f"\n{'─' * 50}")
    print(f"📊 签到汇总")
    print(f"{'─' * 50}")
    
    success_count = sum(1 for _, success, _ in results if success)
    
    summary = f"成功: {success_count}/{len(cookies)}\n"
    for idx, success, msg in results:
        status = "✅" if success else "❌"
        summary += f"\n{status} 账号{idx}: {msg.split(chr(10))[0]}"
    
    print(summary)
    print(f"\n⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 推送通知
    push_notify("老王论坛签到结果", summary)


if __name__ == "__main__":
    main()
