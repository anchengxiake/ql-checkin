#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
South Plus 论坛自动签到脚本
支持青龙面板运行

cron: 0 9 * * *
new Env('SouthPlus签到')

环境变量配置:
- SOUTHPLUS_COOKIE: 论坛Cookie (直接复制浏览器中的cookie字符串)
- MAX_RANDOM_DELAY: 最大随机延迟秒数 (默认3600)
- RANDOM_SIGNIN: 是否启用随机延迟 (默认true)
- PRIVACY_MODE: 隐私保护模式 (默认true)

Cookie获取方法:
1. 登录 https://www.south-plus.net/
2. 按F12打开开发者工具
3. 切换到 Network 标签
4. 刷新页面，点击第一个请求
5. 在 Request Headers 中找到 Cookie，复制全部内容
"""

import time
import os
import random
import subprocess
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


def find_chrome():
    """查找系统已安装的 Chrome/Chromium"""
    possible_paths = [
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/usr/bin/chrome',
        '/usr/bin/google-chrome',
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    try:
        result = subprocess.run(['which', 'chromium'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    
    return None


def init_browser():
    """初始化浏览器"""
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
        
        chrome_path = find_chrome()
        if chrome_path:
            print(f"✅ 找到系统浏览器: {chrome_path}")
        
        co = ChromiumOptions()
        if chrome_path:
            co.set_browser_path(chrome_path)
        
        co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        co.set_argument('--disable-dev-shm-usage')
        co.headless(True)
        co.auto_port()
        
        browser = ChromiumPage(co)
        return browser
    except Exception as e:
        print(f"❌ 浏览器初始化失败: {e}")
        return None


def parse_cookie_string(cookie_str):
    """解析Cookie字符串"""
    if not cookie_str:
        return {}
    
    cookies = {}
    cookie_str = cookie_str.replace('\n', '; ').strip()
    items = cookie_str.split(';')
    
    for item in items:
        item = item.strip()
        if not item or '=' not in item:
            continue
        name, value = item.split('=', 1)
        name = name.strip()
        value = value.strip()
        if name:
            cookies[name] = value
    
    return cookies


class SouthPlusSigner:
    """South Plus 签到类"""
    
    def __init__(self, cookies_dict):
        self.cookies = cookies_dict
        self.browser = None
        self.result = {
            'success': False,
            'daily': False,
            'weekly': False,
            'message': ''
        }
    
    def run(self):
        """执行签到流程"""
        self.browser = init_browser()
        if not self.browser:
            self.result['message'] = '浏览器初始化失败'
            return self.result
        
        try:
            # 访问网站
            print(f"🌐 正在访问网站...")
            self.browser.get('https://www.south-plus.net')
            time.sleep(2)
            
            # 使用JavaScript设置Cookie
            print(f"🍪 正在添加 {len(self.cookies)} 个Cookie...")
            cookie_js = ""
            for name, value in self.cookies.items():
                # 对value中的特殊字符进行处理
                safe_value = value.replace('"', '\\"')
                cookie_js += f'document.cookie = "{name}={safe_value}; domain=.south-plus.net; path=/"; '
            
            self.browser.run_js(cookie_js)
            time.sleep(2)
            
            # 验证Cookie
            current_cookie = self.browser.run_js('return document.cookie')
            print(f"🔍 当前Cookie数量: {len(current_cookie.split(';'))}")
            
            # 检查关键cookie是否存在
            has_winduser = 'eb9e6_winduser' in current_cookie
            has_cknum = 'eb9e6_cknum' in current_cookie
            print(f"🔍 winduser cookie: {has_winduser}")
            print(f"🔍 cknum cookie: {has_cknum}")
            
            # 访问任务页面
            print(f"🌐 正在访问任务页面...")
            self.browser.get('https://www.south-plus.net/plugin.php?H_name-tasks.html.html')
            time.sleep(3)
            
            # 检查登录状态
            page_html = self.browser.html
            
            # 判断登录状态的更可靠方法
            is_logged_in = (
                'member.php?mod=logging&amp;action=logout' in page_html or
                'action=logout' in page_html or
                'eb9e6_winduser' in self.browser.run_js('return document.cookie')
            )
            
            is_not_logged_in = (
                '立即登录' in page_html and '忘记密码' in page_html and
                'member.php?mod=logging&amp;action=logout' not in page_html
            )
            
            print(f"🔍 已登录标志: {is_logged_in}")
            print(f"🔍 未登录标志: {is_not_logged_in}")
            
            if is_not_logged_in and not is_logged_in:
                self.result['message'] = 'Cookie已失效或设置失败，请重新获取'
                print(f"❌ {self.result['message']}")
                # 输出页面部分内容帮助调试
                if '_cf_chl' in page_html or 'cf-browser-verification' in page_html:
                    print(f"⚠️ 检测到Cloudflare验证页面，Cookie可能无效")
                return self.result
            
            # 解析任务状态
            daily_task = 'id="p_15"' in page_html
            weekly_task = 'id="p_14"' in page_html
            
            print(f"📋 日常任务: {'可领取' if daily_task else '暂无/已领取'}")
            print(f"📋 周常任务: {'可领取' if weekly_task else '暂无/已领取'}")
            
            # 领取任务
            if daily_task or weekly_task:
                if weekly_task:
                    try:
                        self.browser.ele('xpath://*[@id="p_14"]/a/img').click()
                        time.sleep(1)
                        print("✅ 周常任务已领取")
                    except Exception as e:
                        print(f"⚠️ 周常任务领取失败: {e}")
                
                if daily_task:
                    try:
                        self.browser.ele('xpath://*[@id="p_15"]/a/img').click()
                        time.sleep(1)
                        print("✅ 日常任务已领取")
                    except Exception as e:
                        print(f"⚠️ 日常任务领取失败: {e}")
                
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
            if self.browser:
                try:
                    self.browser.quit()
                except:
                    pass
        
        return self.result
    
    def complete_tasks(self):
        """完成任务领取"""
        try:
            ongoing_tab = self.browser.ele('xpath://*[@id="main"]/table/tbody/tr/td[1]/div[2]/table/tbody/tr[3]/td')
            ongoing_tab.click()
            time.sleep(2)
            
            try:
                self.browser.ele('xpath://*[@id="both_15"]/a/img').click()
                self.result['daily'] = True
                self.result['message'] += '日常领取成功; '
                print("✅ 日常任务完成")
            except:
                print("ℹ️ 日常任务未完成或已领取")
            
            time.sleep(1)
            
            try:
                self.browser.ele('xpath://*[@id="both_14"]/a/img').click()
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
            ongoing_tab = self.browser.ele('xpath://*[@id="main"]/table/tbody/tr/td[1]/div[2]/table/tbody/tr[3]/td')
            ongoing_tab.click()
            time.sleep(2)
            
            page_html = self.browser.html
            if 'both_15' in page_html or 'both_14' in page_html:
                print("🔍 检测到有进行中的任务，尝试完成...")
                self.complete_tasks()
        except Exception as e:
            print(f"ℹ️ 没有进行中的任务或检查失败: {e}")


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
        error_msg = """❌ 未找到Cookie配置

🔧 配置方法:
设置环境变量 SOUTHPLUS_COOKIE

💡 Cookie获取方法:
1. 登录 https://www.south-plus.net/
2. 按F12打开开发者工具
3. 切换到 Network 标签
4. 刷新页面，点击第一个请求
5. 在 Request Headers 中找到 Cookie，复制全部内容
"""
        print(error_msg)
        notify_user("SouthPlus签到失败", error_msg)
        return
    
    cookies = parse_cookie_string(cookie_str)
    if not cookies:
        error_msg = "❌ Cookie解析失败，请检查格式"
        print(error_msg)
        notify_user("SouthPlus签到失败", error_msg)
        return
    
    print(f"📝 成功解析Cookie，包含 {len(cookies)} 个cookie项")
    
    signer = SouthPlusSigner(cookies)
    result = signer.run()
    
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
