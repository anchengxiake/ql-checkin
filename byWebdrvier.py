#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
South Plus 论坛自动签到脚本
支持青龙面板运行

cron: 0 9 * * *
new Env('SouthPlus签到')

环境变量配置:
- SOUTHPLUS_COOKIE: 论坛Cookie (JSON格式，多账号用@或换行分隔)
- SOUTHPLUS_SERVERKEY: Server酱SendKey (可选，用于推送通知)
- MAX_RANDOM_DELAY: 最大随机延迟秒数 (默认3600)
- RANDOM_SIGNIN: 是否启用随机延迟 (默认true)
- PRIVACY_MODE: 隐私保护模式 (默认true)

Cookie获取方法:
1. 登录 https://www.south-plus.net/
2. 按F12打开开发者工具
3. 切换到 Application/Storage 标签
4. 复制Cookie并转换为JSON格式
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import json
import requests
import time
import os
import random
import re
from datetime import datetime, timedelta

# ---------------- 统一通知模块加载 ----------------
hadsend = False
send = None
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
        print(f"💡 请检查ChromeDriver路径: {CHROMEDRIVER_PATH}")
        return None


def parse_cookies(cookie_str):
    """解析Cookie字符串为JSON列表"""
    if not cookie_str:
        return None
    
    try:
        # 尝试直接解析JSON
        return json.loads(cookie_str)
    except json.JSONDecodeError:
        pass
    
    # 如果不是JSON格式，尝试解析为字典格式
    cookies = []
    try:
        # 尝试按分号分隔的cookie字符串解析
        if ';' in cookie_str:
            for item in cookie_str.split(';'):
                item = item.strip()
                if '=' in item:
                    name, value = item.split('=', 1)
                    cookies.append({
                        'name': name.strip(),
                        'value': value.strip(),
                        'domain': '.south-plus.net'
                    })
            return cookies
    except Exception as e:
        print(f"❌ Cookie解析失败: {e}")
    
    return None


def mask_username(username):
    """用户名脱敏"""
    if not privacy_mode or not username:
        return username
    if len(username) <= 2:
        return "*" * len(username)
    return f"{username[0]}{'*' * (len(username) - 2)}{username[-1]}"


class SouthPlusSigner:
    """South Plus 签到类"""
    
    def __init__(self, cookies, account_index=1):
        self.cookies = cookies
        self.account_index = account_index
        self.driver = None
        self.result = {
            'success': False,
            'daily': False,
            'weekly': False,
            'message': ''
        }
    
    def run(self):
        """执行签到流程"""
        print(f"\n======== ▷ 第 {self.account_index} 个账号 ◁ ========")
        
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
                    # 确保cookie包含必要的字段
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


def get_accounts():
    """获取所有账号配置"""
    # 获取Cookie环境变量（支持新的变量名和旧的变量名）
    cookie_env = os.environ.get('SOUTHPLUS_COOKIE') or os.environ.get('COOKIE', '')
    
    if not cookie_env:
        return []
    
    # 支持多账号（用@或换行分隔）
    accounts = []
    raw_accounts = re.split(r'[@\n]', cookie_env)
    
    for raw in raw_accounts:
        raw = raw.strip()
        if not raw:
            continue
        cookies = parse_cookies(raw)
        if cookies:
            accounts.append(cookies)
    
    return accounts


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
    
    # 获取账号列表
    accounts = get_accounts()
    
    if not accounts:
        error_msg = """❌ 未找到有效的Cookie配置

🔧 配置方法:
1. 设置环境变量 SOUTHPLUS_COOKIE (推荐使用)
2. 或设置旧版环境变量 COOKIE
3. Cookie格式: JSON格式 或 分号分隔的字符串
4. 多账号用 @ 或换行分隔

💡 Cookie获取方法:
1. 登录 https://www.south-plus.net/
2. 按F12打开开发者工具
3. 切换到 Application/Storage 标签
4. 复制Cookie值
"""
        print(error_msg)
        notify_user("SouthPlus签到失败", error_msg)
        return
    
    print(f"📝 共发现 {len(accounts)} 个账号")
    
    success_count = 0
    total_count = len(accounts)
    results = []
    
    for index, cookies in enumerate(accounts, 1):
        signer = SouthPlusSigner(cookies, index)
        result = signer.run()
        
        if result['success']:
            success_count += 1
        
        results.append({
            'index': index,
            'success': result['success'],
            'daily': result['daily'],
            'weekly': result['weekly'],
            'message': result['message']
        })
        
        # 账号间随机延迟
        if index < len(accounts):
            delay = random.uniform(5, 15)
            print(f"\n⏱️ 随机等待 {delay:.1f} 秒后处理下一个账号...")
            time.sleep(delay)
    
    # 生成汇总报告
    summary_msg = f"""📊 SouthPlus签到汇总

📈 总计: {total_count}个账号
✅ 成功: {success_count}个
❌ 失败: {total_count - success_count}个
📊 成功率: {success_count/total_count*100:.1f}%
⏰ 完成时间: {datetime.now().strftime('%m-%d %H:%M')}

📋 详细结果:"""
    
    for r in results:
        status_icon = "✅" if r['success'] else "❌"
        daily_icon = "📅" if r['daily'] else ""
        weekly_icon = "📆" if r['weekly'] else ""
        summary_msg += f"\n{status_icon} 账号{r['index']}: {daily_icon}{weekly_icon} {r['message']}"
    
    print(f"\n{'='*50}")
    print(summary_msg)
    print(f"{'='*50}")
    
    # 发送汇总通知
    notify_user("SouthPlus签到完成", summary_msg)
    

    
    print(f"\n==== SouthPlus签到完成 - 成功{success_count}/{total_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")


if __name__ == "__main__":
    main()
