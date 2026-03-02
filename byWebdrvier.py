#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
South Plus 论坛自动签到脚本
支持青龙面板运行

cron: 0 9 * * *
new Env('SouthPlus签到')

环境变量配置:
- SOUTHPLUS_COOKIE: 论坛Cookie (直接复制浏览器中的cookie字符串，格式如: name=value; name2=value2)
- MAX_RANDOM_DELAY: 最大随机延迟秒数 (默认3600)
- RANDOM_SIGNIN: 是否启用随机延迟 (默认true)
- PRIVACY_MODE: 隐私保护模式 (默认true)

Cookie获取方法:
1. 登录 https://www.south-plus.net/
2. 按F12打开开发者工具
3. 切换到 Application/Storage 标签 → Cookies
4. 复制所有cookie（右键→Copy all），直接粘贴到环境变量
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
# 随机延迟配置
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
    """查找系统已安装的 Chrome/Chromium 路径"""
    possible_paths = [
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/usr/bin/chrome',
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # 尝试 which 命令
    try:
        result = subprocess.run(['which', 'chromium'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    
    return None


def init_browser():
    """初始化浏览器（使用系统已安装的 Chromium）"""
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
        
        # 查找系统 chromium
        chrome_path = find_chrome()
        if chrome_path:
            print(f"✅ 找到系统浏览器: {chrome_path}")
        else:
            print("⚠️ 未找到系统浏览器，使用默认配置")
        
        co = ChromiumOptions()
        
        # 设置浏览器路径
        if chrome_path:
            co.set_browser_path(chrome_path)
        
        co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        co.set_pref('credentials_enable_service', False)
        co.set_argument('--hide-crash-restore-bubble')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.headless(True)
        co.auto_port()
        
        browser = ChromiumPage(co)
        return browser
    except ImportError:
        print("❌ 未安装 DrissionPage，请运行: pip install DrissionPage")
        return None
    except Exception as e:
        print(f"❌ 浏览器初始化失败: {e}")
        return None


def parse_cookie_string(cookie_str):
    """解析Cookie字符串 (name=value; name2=value2 格式)"""
    if not cookie_str:
        return {}
    
    cookies = {}
    # 处理多行cookie，合并为一行
    cookie_str = cookie_str.replace('\n', '; ').strip()
    
    # 按分号分割
    items = cookie_str.split(';')
    
    for item in items:
        item = item.strip()
        if not item or '=' not in item:
            continue
        # 只分割第一个等号
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
        # 初始化浏览器
        self.browser = init_browser()
        if not self.browser:
            self.result['message'] = '浏览器初始化失败'
            return self.result
        
        try:
            # 先访问主页设置Cookie（必须在同域名下才能设置cookie）
            print(f"🌐 正在访问网站...")
            self.browser.get('https://www.south-plus.net')
            time.sleep(2)
            
            # 添加Cookie (通过DrissionPage API)
            print(f"🍪 正在添加Cookie...")
            try:
                # 转换为DrissionPage需要的格式
                cookie_list = []
                for name, value in self.cookies.items():
                    cookie_list.append({
                        'name': name,
                        'value': value,
                        'domain': '.south-plus.net',
                        'path': '/'
                    })
                
                # 使用set.cookies()方法
                if hasattr(self.browser, 'set') and hasattr(self.browser.set, 'cookies'):
                    self.browser.set.cookies(cookie_list)
                else:
                    # 备选：通过JavaScript逐个设置
                    for name, value in self.cookies.items():
                        try:
                            # 如果value包含特殊字符，保持原样
                            cookie_js = f'document.cookie = "{name}={value}; domain=.south-plus.net; path=/"'
                            self.browser.run_js(cookie_js)
                        except Exception as e:
                            print(f"⚠️ 添加Cookie [{name}] 失败: {e}")
            except Exception as e:
                print(f"⚠️ 设置Cookie失败: {e}")
            
            # 验证cookie是否设置成功
            time.sleep(1)
            current_cookies = self.browser.run_js('return document.cookie')
            print(f"🔍 当前页面Cookie: {current_cookies[:100]}...")
            
            # 访问任务页面
            url = 'https://www.south-plus.net/plugin.php?H_name-tasks.html.html'
            print(f"🌐 正在访问任务页面...")
            self.browser.get(url)
            time.sleep(3)
            
            # 检查登录状态
            page_html = self.browser.html
            current_url = self.browser.url
            print(f"🔍 当前页面URL: {current_url}")
            print(f"🔍 页面长度: {len(page_html)} 字符")
            
            # 检查页面内容判断是否登录
            has_login = 'login' in page_html.lower() or '登录' in page_html
            has_logout = 'logout' in page_html.lower() or '退出' in page_html
            has_userinfo = 'eb9e6_winduser' in page_html or '访问我的空间' in page_html
            
            print(f"🔍 页面包含'登录': {has_login}")
            print(f"🔍 页面包含'退出': {has_logout}")
            print(f"🔍 页面包含用户信息: {has_userinfo}")
            
            if has_login and not has_logout:
                self.result['message'] = 'Cookie已失效，请重新获取'
                print(f"❌ {self.result['message']}")
                # 打印页面部分内容帮助调试
                print(f"🔍 页面内容预览: {page_html[:500]}...")
                return self.result
            
            # 解析页面获取任务状态
            daily_task = 'id="p_15"' in page_html
            weekly_task = 'id="p_14"' in page_html
            
            print(f"📋 日常任务状态: {'可领取' if daily_task else '暂无'}")
            print(f"📋 周常任务状态: {'可领取' if weekly_task else '暂无'}")
            
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
            if self.browser:
                try:
                    self.browser.quit()
                except:
                    pass
        
        return self.result
    
    def complete_tasks(self):
        """完成任务领取"""
        try:
            # 切换到进行中的任务
            ongoing_tab = self.browser.ele('xpath://*[@id="main"]/table/tbody/tr/td[1]/div[2]/table/tbody/tr[3]/td')
            ongoing_tab.click()
            time.sleep(2)
            
            # 尝试完成日常任务
            try:
                self.browser.ele('xpath://*[@id="both_15"]/a/img').click()
                self.result['daily'] = True
                self.result['message'] += '日常领取成功; '
                print("✅ 日常任务完成")
            except:
                print("ℹ️ 日常任务未完成或已领取")
            
            time.sleep(1)
            
            # 尝试完成周常任务
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

💡 Cookie获取方法:
1. 登录 https://www.south-plus.net/
2. 按F12打开开发者工具
3. 切换到 Application/Storage 标签 → Cookies
4. 右键点击 Cookie 列表 → Copy all
5. 直接粘贴到环境变量值中

Cookie格式示例:
eb9e6_winduser=xxx; eb9e6_cknum=xxx; other_cookie=value
"""
        print(error_msg)
        notify_user("SouthPlus签到失败", error_msg)
        return
    
    # 解析Cookie
    cookies = parse_cookie_string(cookie_str)
    if not cookies:
        error_msg = "❌ Cookie解析失败，请检查格式"
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
