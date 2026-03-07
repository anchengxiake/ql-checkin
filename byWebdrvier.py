#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
South Plus 论坛自动签到脚本 (Selenium版)
支持青龙面板运行

cron: 0 9 * * *
new Env('SouthPlus签到')

环境变量配置:
- SOUTHPLUS_COOKIE: 论坛Cookie (JSON格式，从浏览器复制)
- MAX_RANDOM_DELAY: 最大随机延迟秒数 (默认3600)
- RANDOM_SIGNIN: 是否启用随机延迟 (默认true)
- PRIVACY_MODE: 隐私保护模式 (默认true)
- CHROMEDRIVER_PATH: ChromeDriver路径 (可选，自动检测)
"""

import json
import time
import os
import random
import subprocess
from datetime import datetime, timedelta

# Selenium 导入
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# ---------------- 统一通知模块加载 ----------------
hadsend = False
try:
    from notify import send
    hadsend = True
    print("✅ 已加载notify.py通知模块")
except ImportError:
    print("⚠️  未加载通知模块，跳过通知功能")

# ---------------- 配置项 ----------------
max_random_delay = int(os.getenv("MAX_RANDOM_DELAY", "3600"))
random_signin = os.getenv("RANDOM_SIGNIN", "true").lower() == "true"
privacy_mode = os.getenv("PRIVACY_MODE", "true").lower() == "true"


def format_time_remaining(seconds):
    """格式化时间显示"""
    if seconds <= 0:
        return "立即执行"
    hours, minutes = divmod(seconds, 3600)
    minutes, secs = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}小时{minutes}分{secs}秒"
    elif minutes > 0:
        return f"{minutes}分{secs}秒"
    else:
        return f"{secs}秒"


def wait_with_countdown(delay_seconds, task_name="SouthPlus签到"):
    """带倒计时的随机延迟等待"""
    if delay_seconds <= 0:
        return
    print(f"{task_name} 需要等待 {format_time_remaining(delay_seconds)}")
    remaining = delay_seconds
    while remaining > 0:
        if remaining <= 10 or remaining % 10 == 0:
            print(f"{task_name} 倒计时: {format_time_remaining(remaining)}")
        sleep_time = 1 if remaining <= 10 else min(10, remaining)
        time.sleep(sleep_time)
        remaining -= sleep_time


def notify_user(title, content):
    """统一通知函数"""
    if hadsend:
        try:
            send(title, content)
            print(f"✅ 通知发送完成: {title}")
        except Exception as e:
            print(f"❌ 通知发送失败: {e}")
    else:
        print(f"📢 {title}\n📄 {content}")


def find_chromedriver():
    """查找 ChromeDriver"""
    # 1. 检查环境变量
    env_path = os.getenv('CHROMEDRIVER_PATH', '')
    if env_path and os.path.exists(env_path):
        return env_path
    
    # 2. 常见路径
    possible_paths = [
        '/usr/bin/chromedriver',
        '/usr/local/bin/chromedriver',
        '/usr/lib/chromedriver',
        '/opt/chromedriver',
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # 3. which 命令查找
    try:
        result = subprocess.run(['which', 'chromedriver'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    
    return None


def init_driver():
    """初始化 WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    chromedriver_path = find_chromedriver()
    
    try:
        if chromedriver_path:
            print(f"✅ 使用 ChromeDriver: {chromedriver_path}")
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            print("⚠️ 未找到 ChromeDriver，尝试自动检测...")
            driver = webdriver.Chrome(options=chrome_options)
        
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        return driver
    except Exception as e:
        print(f"❌ WebDriver 初始化失败: {e}")
        print(f"💡 请确保已安装 ChromeDriver: apk add chromium-chromedriver")
        return None


def parse_cookie_json(cookie_str):
    """解析 JSON 格式 Cookie"""
    if not cookie_str:
        return []
    try:
        cookies = json.loads(cookie_str.strip())
        if isinstance(cookies, list):
            return cookies
    except json.JSONDecodeError:
        print("❌ Cookie JSON 解析失败")
    return []


class SouthPlusSigner:
    """South Plus 签到类"""
    
    def __init__(self, cookies_list):
        self.cookies = cookies_list
        self.driver = None
        self.result = {
            'success': False,
            'daily': False,
            'weekly': False,
            'message': ''
        }
    
    def run(self):
        """执行签到流程"""
        self.driver = init_driver()
        if not self.driver:
            self.result['message'] = '浏览器初始化失败'
            return self.result
        
        try:
            # 访问网站并添加 Cookie
            print(f"🌐 正在初始化...")
            self.driver.get('https://www.south-plus.net')
            time.sleep(2)
            
            # 添加 Cookie
            print(f"🍪 正在添加 Cookie...")
            for cookie in self.cookies:
                try:
                    # 确保必要的字段
                    if 'domain' not in cookie:
                        cookie['domain'] = '.south-plus.net'
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    print(f"   ⚠️ Cookie {cookie.get('name', 'unknown')}: {e}")
            
            # 刷新页面应用 Cookie
            self.driver.refresh()
            time.sleep(3)
            
            # 访问任务页面
            print(f"🌐 正在访问任务页面...")
            self.driver.get('https://www.south-plus.net/plugin.php?H_name-tasks.html.html')
            time.sleep(3)
            
            # 检查登录状态
            page_source = self.driver.page_source
            if 'member.php?mod=logging&action=logout' not in page_source:
                self.result['message'] = 'Cookie 已失效，请重新获取'
                print(f"❌ {self.result['message']}")
                return self.result
            
            print("✅ 登录状态正常")
            
            # 检查任务状态
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
            
            daily_task = soup.find('span', id='p_15')
            weekly_task = soup.find('span', id='p_14')
            
            print(f"📋 日常任务: {'可领取' if daily_task else '暂无'}")
            print(f"📋 周常任务: {'可领取' if weekly_task else '暂无'}")
            
            # 领取任务
            if daily_task or weekly_task:
                if weekly_task:
                    try:
                        self.driver.find_element(By.XPATH, '//*[@id="p_14"]/a/img').click()
                        time.sleep(1)
                        print("✅ 周常任务已领取")
                    except Exception as e:
                        print(f"⚠️ 周常领取失败: {e}")
                
                if daily_task:
                    try:
                        self.driver.find_element(By.XPATH, '//*[@id="p_15"]/a/img').click()
                        time.sleep(1)
                        print("✅ 日常任务已领取")
                    except Exception as e:
                        print(f"⚠️ 日常领取失败: {e}")
                
                # 完成任务
                self.complete_tasks()
            else:
                self.result['message'] = '任务暂未刷新或已领取'
                print(f"ℹ️ {self.result['message']}")
                self.check_ongoing_tasks()
            
            self.result['success'] = True
            
        except Exception as e:
            self.result['message'] = f'执行异常: {str(e)}'
            print(f"❌ {self.result['message']}")
        
        finally:
            if self.driver:
                self.driver.quit()
        
        return self.result
    
    def complete_tasks(self):
        """完成任务领取"""
        try:
            # 切换到进行中的任务
            self.driver.find_element(By.XPATH, '//*[@id="main"]/table/tbody/tr/td[1]/div[2]/table/tbody/tr[3]/td').click()
            time.sleep(2)
            
            # 完成日常
            try:
                self.driver.find_element(By.XPATH, '//*[@id="both_15"]/a/img').click()
                self.result['daily'] = True
                self.result['message'] += '日常完成; '
                print("✅ 日常任务完成")
                time.sleep(1)
            except:
                print("ℹ️ 日常已完成或无需操作")
            
            # 完成周常
            try:
                self.driver.find_element(By.XPATH, '//*[@id="both_14"]/a/img').click()
                self.result['weekly'] = True
                self.result['message'] += '周常完成; '
                print("✅ 周常任务完成")
            except:
                print("ℹ️ 周常已完成或无需操作")
                
        except Exception as e:
            print(f"⚠️ 任务完成流程: {e}")
    
    def check_ongoing_tasks(self):
        """检查进行中的任务"""
        try:
            self.driver.find_element(By.XPATH, '//*[@id="main"]/table/tbody/tr/td[1]/div[2]/table/tbody/tr[3]/td').click()
            time.sleep(2)
            
            page_source = self.driver.page_source
            if 'both_15' in page_source or 'both_14' in page_source:
                print("🔍 检测到有进行中的任务...")
                self.complete_tasks()
        except:
            pass


def main():
    """主程序入口"""
    print(f"==== SouthPlus签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    print(f"🔒 隐私保护模式: {'已启用' if privacy_mode else '已禁用'}")
    
    if random_signin:
        delay_seconds = random.randint(0, max_random_delay)
        if delay_seconds > 0:
            print(f"🎲 随机延迟: {format_time_remaining(delay_seconds)}")
            wait_with_countdown(delay_seconds, "SouthPlus签到")
    
    cookie_str = os.environ.get('SOUTHPLUS_COOKIE', '')
    
    if not cookie_str:
        error_msg = """❌ 未找到 Cookie 配置

🔧 配置方法:
设置环境变量 SOUTHPLUS_COOKIE

💡 Cookie 获取方法:
1. 登录 https://www.south-plus.net/
2. 按F12打开开发者工具
3. 切换到 Application/Storage → Cookies
4. 复制为 JSON 格式

示例格式:
[
  {"name": "eb9e6_winduser", "value": "xxx", "domain": ".south-plus.net"},
  {"name": "eb9e6_cknum", "value": "xxx", "domain": ".south-plus.net"}
]"""
        print(error_msg)
        notify_user("SouthPlus签到失败", error_msg)
        return
    
    cookies = parse_cookie_json(cookie_str)
    if not cookies:
        error_msg = "❌ Cookie 解析失败，请检查 JSON 格式"
        print(error_msg)
        notify_user("SouthPlus签到失败", error_msg)
        return
    
    print(f"📝 成功解析 Cookie，包含 {len(cookies)} 项")
    
    signer = SouthPlusSigner(cookies)
    result = signer.run()
    
    if result['success']:
        daily_icon = "📅" if result['daily'] else ""
        weekly_icon = "📆" if result['weekly'] else ""
        summary_msg = f"""📊 SouthPlus签到结果

✅ 签到成功
{daily_icon}{weekly_icon} {result['message']}
⏰ 完成时间: {datetime.now().strftime('%m-%d %H:%M')}"""
        
        print(f"\n{'='*50}")
        print(summary_msg)
        print(f"{'='*50}")
        notify_user("SouthPlus签到完成", summary_msg)
    else:
        error_msg = f"""❌ SouthPlus签到失败

错误信息: {result['message']}
⏰ 时间: {datetime.now().strftime('%m-%d %H:%M')}"""
        
        print(f"\n{'='*50}")
        print(error_msg)
        print(f"{'='*50}")
        notify_user("SouthPlus签到失败", error_msg)
    
    print(f"\n==== SouthPlus签到结束 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")


if __name__ == "__main__":
    main()
