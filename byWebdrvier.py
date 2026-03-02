#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
South Plus 论坛自动签到脚本
支持青龙面板运行

cron: 0 9 * * *
new Env('SouthPlus签到')

环境变量配置:
- SOUTHPLUS_COOKIE: 论坛Cookie (JSON格式)
- MAX_RANDOM_DELAY: 最大随机延迟秒数 (默认3600)
- RANDOM_SIGNIN: 是否启用随机延迟 (默认true)
- PRIVACY_MODE: 隐私保护模式 (默认true)
- CHROMEDRIVER_PATH: ChromeDriver路径 (默认/usr/local/bin/chromedriver)

Cookie获取方法:
1. 登录 https://www.south-plus.net/
2. 按F12打开开发者工具
3. 切换到 Application/Storage 标签 → Cookies
4. 复制所有cookie为JSON格式
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import json
import requests
import time
import os
import random
from datetime import datetime, timedelta

# ---------------- 统一通知模块加载 ----------------
hadsend = False
try:
    from notify import send
    hadsend = True
    print("✅ 已加载notify.py通知模块")
except ImportError:
    print("⚠️  未加载通知模块，跳过通知功能")

# ---------------- 配置项 ----------------
# 随机延迟配置
max_random_delay = int(os.getenv("MAX_RANDOM_DELAY", "3600"))
random_signin = os.getenv("RANDOM_SIGNIN", "true").lower() == "true"
privacy_mode = os.getenv("PRIVACY_MODE", "true").lower() == "true"

# ChromeDriver路径
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver")


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


def init_driver():
    """初始化WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    try:
        service = Service(CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        print(f"❌ WebDriver初始化失败: {e}")
        return None


def parse_cookie(cookie_str):
    """解析Cookie JSON字符串"""
    if not cookie_str:
        return None
    
    try:
        cookies = json.loads(cookie_str.strip())
        if isinstance(cookies, list) and len(cookies) > 0:
            return cookies
    except json.JSONDecodeError as e:
        print(f"❌ Cookie JSON解析失败: {e}")
    
    return None


class SouthPlusSigner:
    """South Plus 签到类"""
    
    def __init__(self, cookies):
        self.cookies = cookies
        self.driver = None
        self.result = {
            'success': False,
            'daily': False,
            'weekly': False,
            'message': ''
        }
    
    def run(self):
        """执行签到流程"""
        # 初始化WebDriver
        self.driver = init_driver()
        if not self.driver:
            self.result['message'] = 'WebDriver初始化失败'
            return self.result
        
        try:
            # 访问任务页面
            url = 'https://www.south-plus.net/plugin.php?H_name-tasks.html.html'
            print(f"🌐 正在访问任务页面...")
            self.driver.get(url)
            time.sleep(2)
            
            # 添加Cookie
            for cookie in self.cookies:
                try:
                    if 'domain' not in cookie:
                        cookie['domain'] = '.south-plus.net'
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    print(f"⚠️ 添加Cookie失败: {e}")
            
            # 重新加载页面
            self.driver.get(url)
            time.sleep(3)
            
            # 检查登录状态
            page_source = self.driver.page_source
            if 'login' in page_source.lower() or '登录' in page_source:
                self.result['message'] = 'Cookie已失效，请重新获取'
                print(f"❌ {self.result['message']}")
                return self.result
            
            # 解析页面获取任务状态
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            daily_task = soup.find('span', id='p_15')
            weekly_task = soup.find('span', id='p_14')
            
            print(f"📋 日常任务状态: {'可领取' if daily_task else '暂无'}")
            print(f"📋 周常任务状态: {'可领取' if weekly_task else '暂无'}")
            
            # 领取任务
            if daily_task or weekly_task:
                if weekly_task:
                    try:
                        self.driver.find_element(By.XPATH, '//*[@id="p_14"]/a/img').click()
                        time.sleep(1)
                        print("✅ 周常任务已领取")
                    except Exception as e:
                        print(f"⚠️ 周常任务领取失败: {e}")
                
                if daily_task:
                    try:
                        self.driver.find_element(By.XPATH, '//*[@id="p_15"]/a/img').click()
                        time.sleep(1)
                        print("✅ 日常任务已领取")
                    except Exception as e:
                        print(f"⚠️ 日常任务领取失败: {e}")
                
                # 执行任务完成流程
                self.complete_tasks()
            else:
                self.result['message'] = '任务暂未刷新或已领取'
                print(f"ℹ️ {self.result['message']}")
                # 尝试检查进行中的任务
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
            ongoing_tab = self.driver.find_element(By.XPATH, '//*[@id="main"]/table/tbody/tr/td[1]/div[2]/table/tbody/tr[3]/td')
            ongoing_tab.click()
            time.sleep(2)
            
            # 尝试完成日常任务
            try:
                self.driver.find_element(By.XPATH, '//*[@id="both_15"]/a/img').click()
                self.result['daily'] = True
                self.result['message'] += '日常领取成功; '
                print("✅ 日常任务完成")
            except:
                print("ℹ️ 日常任务未完成或已领取")
            
            time.sleep(1)
            
            # 尝试完成周常任务
            try:
                self.driver.find_element(By.XPATH, '//*[@id="both_14"]/a/img').click()
                self.result['weekly'] = True
                self.result['message'] += '周常领取成功; '
                print("✅ 周常任务完成")
            except:
                print("ℹ️ 周常任务未完成或已领取")
                
        except Exception as e:
            self.result['message'] = f'任务完成流程异常: {str(e)}'
            print(f"❌ {self.result['message']}")
    
    def check_ongoing_tasks(self):
        """检查进行中的任务状态"""
        try:
            ongoing_tab = self.driver.find_element(By.XPATH, '//*[@id="main"]/table/tbody/tr/td[1]/div[2]/table/tbody/tr[3]/td')
            ongoing_tab.click()
            time.sleep(2)
            
            page_source = self.driver.page_source
            if 'both_15' in page_source or 'both_14' in page_source:
                print("🔍 检测到有进行中的任务，尝试完成...")
                self.complete_tasks()
        except Exception as e:
            print(f"ℹ️ 没有进行中的任务或检查失败: {e}")


def main():
    """主程序入口"""
    print(f"==== SouthPlus签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    
    # 显示配置状态
    print(f"🔒 隐私保护模式: {'已启用' if privacy_mode else '已禁用'}")
    
    # 随机延迟（整体延迟）
    if random_signin:
        delay_seconds = random.randint(0, max_random_delay)
        if delay_seconds > 0:
            print(f"🎲 随机延迟: {format_time_remaining(delay_seconds)}")
            wait_with_countdown(delay_seconds, "SouthPlus签到")
    
    # 获取Cookie
    cookie_str = os.environ.get('SOUTHPLUS_COOKIE', '')
    
    if not cookie_str:
        error_msg = """❌ 未找到Cookie配置

🔧 配置方法:
设置环境变量 SOUTHPLUS_COOKIE
Cookie格式: JSON数组格式

💡 Cookie获取方法:
1. 登录 https://www.south-plus.net/
2. 按F12打开开发者工具
3. 切换到 Application/Storage 标签 → Cookies
4. 复制所有cookie为JSON格式
"""
        print(error_msg)
        notify_user("SouthPlus签到失败", error_msg)
        return
    
    # 解析Cookie
    cookies = parse_cookie(cookie_str)
    if not cookies:
        error_msg = "❌ Cookie解析失败，请检查JSON格式是否正确"
        print(error_msg)
        print(f"   Cookie内容预览: {cookie_str[:100]}...")
        notify_user("SouthPlus签到失败", error_msg)
        return
    
    print(f"📝 成功解析Cookie，包含 {len(cookies)} 个cookie项")
    
    # 执行签到
    signer = SouthPlusSigner(cookies)
    result = signer.run()
    
    # 生成报告
    if result['success']:
        status_icon = "✅"
        daily_icon = "📅" if result['daily'] else ""
        weekly_icon = "📆" if result['weekly'] else ""
        summary_msg = f"""📊 SouthPlus签到结果

{status_icon} 签到成功
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
