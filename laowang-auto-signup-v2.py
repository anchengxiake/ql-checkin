#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
老王论坛自动签到脚本（轻量版 - Cookie模式）
cron: 0 9 * * *
new Env('老王论坛签到')
"""
import os
import sys
import re
import time
import random
import logging
import requests
from datetime import datetime, timedelta

# 日志格式
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

BASE_URL = "https://laowang.vip"
SIGN_URL = "https://laowang.vip/plugin.php?id=k_misign:sign&operation=qiandao&format=empty"

# 随机延迟配置
max_random_delay = int(os.getenv("MAX_RANDOM_DELAY", "3600"))
random_signin = os.getenv("RANDOM_SIGNIN", "true").lower() == "true"

# 尝试加载通知模块
notify = None
try:
    from notify import send
    notify = send
    logging.info("✅ 已加载 notify 通知模块")
except ImportError:
    logging.warning("⚠️ 未加载通知模块")

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

def wait_with_countdown(delay_seconds, task_name="签到"):
    """带倒计时的等待"""
    if delay_seconds <= 0:
        return
        
    print(f"{task_name}需要等待 {format_time_remaining(delay_seconds)}")
    
    remaining = delay_seconds
    while remaining > 0:
        if remaining <= 10 or remaining % 10 == 0:
            print(f"倒计时: {format_time_remaining(remaining)}")
        
        sleep_time = 1 if remaining <= 10 else min(10, remaining)
        time.sleep(sleep_time)
        remaining -= sleep_time

class LaowangSignin:
    """老王论坛自动签到类（轻量版）"""
    
    def __init__(self, cookie, index=1):
        self.cookie = cookie
        self.index = index
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.92 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://laowang.vip/plugin.php?id=k_misign:sign',
        })
        # 解析 cookie
        self._parse_cookie()
        
    def _parse_cookie(self):
        """解析 cookie 字符串到字典"""
        if not self.cookie:
            return
        
        # 支持多种格式
        cookie_parts = self.cookie.replace('; ', ';').split(';')
        for part in cookie_parts:
            if '=' in part:
                key, value = part.split('=', 1)
                self.session.cookies.set(key.strip(), value.strip())
    
    def get_sign_status(self):
        """获取签到状态"""
        try:
            url = f"{BASE_URL}/plugin.php?id=k_misign:sign"
            response = self.session.get(url, timeout=15)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                return None, f"获取状态失败，HTTP {response.status_code}"
            
            html = response.text
            
            # 检查是否已登录
            if '登录' in html and '立即注册' in html:
                return None, "Cookie 已失效，请重新获取"
            
            # 尝试提取用户名
            username_match = re.search(r'title="访问我的空间">(.+?)</a>', html)
            username = username_match.group(1) if username_match else f"账号{self.index}"
            
            # 检查今日是否已签到
            if '已签到' in html or '今日已签' in html:
                return username, "already_signed"
            
            # 检查是否有签到按钮
            if '签到' in html or 'qiandao' in html:
                return username, "can_sign"
            
            return username, "unknown"
            
        except requests.exceptions.Timeout:
            return None, "请求超时"
        except Exception as e:
            return None, f"获取状态异常: {str(e)}"
    
    def sign(self):
        """执行签到"""
        try:
            print(f"\n🙍🏻 账号{self.index}: 正在检查签到状态...")
            
            if not self.cookie:
                return False, "Cookie 为空"
            
            # 获取签到状态
            username, status = self.get_sign_status()
            
            if status == "Cookie 已失效，请重新获取":
                return False, status
            
            if not username:
                return False, status
            
            print(f"👤 用户名: {username}")
            
            # 已签到
            if status == "already_signed":
                return True, "今日已签到"
            
            # 可以签到
            if status == "can_sign":
                print("📝 正在执行签到...")
                
                # 发送签到请求
                response = self.session.get(SIGN_URL, timeout=15)
                response.encoding = 'utf-8'
                
                print(f"🔍 响应状态: {response.status_code}")
                
                # 检查响应
                if response.status_code == 200:
                    # 签到成功通常返回空或特定消息
                    if '签到' in response.text or response.text.strip() == '':
                        return True, "签到成功"
                    elif '已经' in response.text or '已签' in response.text:
                        return True, "今日已签到"
                    else:
                        # 可能需要滑块验证
                        if '验证' in response.text or 'captcha' in response.text.lower():
                            return False, "需要滑块验证，请使用浏览器模式或在网页上手动签到一次"
                        return False, f"签到响应异常: {response.text[:100]}"
                else:
                    return False, f"签到请求失败: HTTP {response.status_code}"
            
            return False, f"未知状态: {status}"
            
        except requests.exceptions.Timeout:
            return False, "签到请求超时"
        except Exception as e:
            error_msg = f"签到异常: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg

def parse_cookies(cookie_str):
    """解析多账号 Cookie: cookie1&cookie2 或 cookie1\ncookie2"""
    if not cookie_str:
        return []
    # 支持 & 或换行分隔
    cookies = re.split(r'[&\n]', cookie_str.strip())
    return [c.strip() for c in cookies if c.strip()]

if __name__ == "__main__":
    print("""
    ███╗   ███╗ █████╗ ██████╗  █████╗ ███╗   ███╗
    ████╗ ████║██╔══██╗██╔══██╗██╔══██╗████╗ ████║
    ██╔████╔██║███████║██████╔╝███████║██╔████╔██║
    ██║╚██╔╝██║██╔══██║██╔══██╗██╔══██║██║╚██╔╝██║
    ██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██║██║ ╚═╝ ██║
    ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝
    
    Laowang Auto Signup Tool v3.0 (轻量版)
    Powered by Maram
""")
    
    print(f"==== 老王论坛签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====\n")
    
    # 随机延迟（可选）
    if random_signin:
        delay_seconds = random.randint(0, max_random_delay)
        if delay_seconds > 0:
            signin_time = datetime.now() + timedelta(seconds=delay_seconds)
            print(f"随机模式: 延迟 {format_time_remaining(delay_seconds)} 后签到")
            print(f"预计签到时间: {signin_time.strftime('%H:%M:%S')}")
            wait_with_countdown(delay_seconds, "老王论坛签到")
    
    # 获取 Cookie 配置
    cookies = []
    cookie_str = os.getenv('LAOWANG_COOKIE', '').strip()
    
    if cookie_str:
        cookies = parse_cookies(cookie_str)
    
    if not cookies:
        error_msg = """❌ 未配置老王论坛 Cookie，请设置 LAOWANG_COOKIE

🔧 获取 Cookie 的方法:
1. 用浏览器登录老王论坛: https://laowang.vip
2. 按 F12 打开开发者工具
3. 切换到 Network（网络）标签页
4. 刷新页面，找到任意请求
5. 在 Request Headers 中复制 Cookie 的值
6. 在青龙面板添加环境变量 LAOWANG_COOKIE

💡 Cookie 格式示例:
LAOWANG_COOKIE= cookie1_value

💡 多账号用 & 分隔:
LAOWANG_COOKIE=cookie1&cookie2

⚠️ 注意: Cookie 通常包含敏感信息，请妥善保管
"""
        print(error_msg)
        if notify:
            notify("老王论坛签到失败", error_msg)
        sys.exit(1)
    
    print(f"✅ 检测到共 {len(cookies)} 个账号\n")
    print("----------老王论坛开始签到----------")
    
    msg = ""
    success_count = 0
    
    for idx, cookie in enumerate(cookies, 1):
        log = f"\n🙍🏻 第{idx}个账号\n"
        msg += log
        print(log)
        
        signin = LaowangSignin(cookie, idx)
        success, result_msg = signin.sign()
        
        if success:
            result_str = f"✅ {result_msg}\n"
            success_count += 1
        else:
            result_str = f"❌ {result_msg}\n"
        
        msg += result_str
        print(result_str)
        
        # 多账号间随机延迟
        if idx < len(cookies):
            delay = random.uniform(5, 15)
            print(f"⏱️  等待 {delay:.1f} 秒后处理下一个账号...")
            time.sleep(delay)
    
    print("----------老王论坛签到执行完毕----------")
    print(f"\n==== 老王论坛签到完成 - 成功{success_count}/{len(cookies)} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    
    # 推送通知
    if notify:
        try:
            notify("老王论坛签到", msg[:-1])  # 去掉最后的换行符
        except Exception as e:
            logging.error(f"推送失败: {e}")
