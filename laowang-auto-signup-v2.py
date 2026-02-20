#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
老王论坛自动签到脚本
cron: 0 9 * * *
new Env('老王论坛签到')
"""
import os
import sys
import re
import time
import random
import logging
from datetime import datetime, timedelta

# 尝试导入 DrissionPage
try:
    import DrissionPage
except ImportError:
    print("❌ 请先安装 DrissionPage: pip install DrissionPage")
    sys.exit(1)

# 日志格式
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

BASE_URL = "https://laowang.vip/plugin.php?id=k_misign:sign"

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

def pass_slide_verification(browser):
    """暴力破解滑块验证"""
    max_attempts = 100
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        browser.wait.ele_displayed('.slide_block')
        slider = browser.ele('.slide_block')
        time.sleep(0.1)
        print("正在突破...")
        for distance in range(80, 161, 10):
            try:
                # 执行移动
                browser.actions.move_to(slider)
                time.sleep(0.1)
                browser.actions.hold()
                browser.actions.move(distance, 0)
                browser.actions.release()
                time.sleep(0.8)
                try:
                    # 检查验证码弹窗是否隐藏
                    tncode_div = browser.ele('#tncode_div')
                    display_style = browser.run_js('return arguments[0].style.display', tncode_div)
                    if display_style == 'none':
                        print(f"突破成功！")
                        return True
                    time.sleep(1)  # 给验证结果一点时间
                except Exception as e:
                    print(f"检查验证状态失败: {e}")
                    pass
                    
            except Exception as e:
                print(f"滑动失败: {e}")
                continue
    print(f"达到最大尝试次数 {max_attempts}，验证失败")
    return False

class LaowangSignin:
    """老王论坛自动签到类"""
    
    def __init__(self, account, password, index=1):
        self.account = account
        self.password = password
        self.index = index
        self.browser = None
        
    def sign(self):
        """执行签到"""
        try:
            print(f"\n🙍🏻 账号{self.index}: {self.account}")
            
            # 初始化浏览器配置
            co = DrissionPage.ChromiumOptions()
            co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.92 Safari/537.36')
            co.set_pref('credentials_enable_service', False)
            co.set_argument('--hide-crash-restore-bubble')
            co.auto_port()
            co.headless(True)
            
            # 初始化浏览器
            self.browser = DrissionPage.ChromiumPage(co)
            self.browser.get(BASE_URL)
            
            # 登录流程
            self.browser.ele('@class=btn J_chkitot').click()
            self.browser.ele('@name=username').input(self.account)
            self.browser.ele('@name=password').input(self.password)
            self.browser.ele('@class=tncode').click()
            
            if not pass_slide_verification(self.browser):
                return False, "滑块验证失败"
                
            self.browser.ele('@name=loginsubmit').click()
            self.browser.wait.url_change(BASE_URL, timeout=10)
            
            # 签到流程
            self.browser.ele('@class=btn J_chkitot').click()
            self.browser.ele('@class=tncode').click()
            
            if not pass_slide_verification(self.browser):
                return False, "签到滑块验证失败"
                
            self.browser.ele('@id=submit-btn').click()
            self.browser.wait.url_change(BASE_URL, timeout=10)
            
            return True, "签到成功"
            
        except Exception as e:
            error_msg = f"签到异常: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg
        finally:
            if self.browser:
                try:
                    self.browser.quit()
                except:
                    pass

def parse_accounts(account_str):
    """解析账号: user1:pass1&user2:pass2 或 user1:pass1\nuser2:pass2"""
    if not account_str:
        return []
    accounts = re.split(r'[&\n]', account_str.strip())
    result = []
    for account in accounts:
        account = account.strip()
        if ':' in account:
            user, pwd = account.split(':', 1)
            result.append((user.strip(), pwd.strip()))
    return result

if __name__ == "__main__":
    print("""
    ███╗   ███╗ █████╗ ██████╗  █████╗ ███╗   ███╗
    ████╗ ████║██╔══██╗██╔══██╗██╔══██╗████╗ ████║
    ██╔████╔██║███████║██████╔╝███████║██╔████╔██║
    ██║╚██╔╝██║██╔══██║██╔══██╗██╔══██║██║╚██╔╝██║
    ██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██║██║ ╚═╝ ██║
    ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝
    
    Laowang Auto Signup Tool v2.0
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
    
    # 获取账号配置
    accounts = []
    
    # 优先使用 LAOWANG_ACCOUNT（多账号格式: user1:pass1&user2:pass2）
    account_str = os.getenv('LAOWANG_ACCOUNT', '').strip()
    if account_str:
        accounts = parse_accounts(account_str)
    else:
        # 兼容旧配置（单账号）
        account = os.getenv('LAOWANG_USER', '').strip()
        password = os.getenv('LAOWANG_PW', '').strip()
        if account and password:
            accounts.append((account, password))
    
    if not accounts:
        error_msg = """❌ 未配置老王论坛账号，请设置 LAOWANG_ACCOUNT 或 LAOWANG_USER/LAOWANG_PW

🔧 配置方法:
1. 多账号格式（推荐）: LAOWANG_ACCOUNT=user1:pass1&user2:pass2
2. 单账号格式: LAOWANG_USER=your_username, LAOWANG_PW=your_password

💡 提示: 多账号可用 & 分隔，或每行一个账号"""
        print(error_msg)
        if notify:
            notify("老王论坛签到失败", error_msg)
        sys.exit(1)
    
    print(f"✅ 检测到共 {len(accounts)} 个账号\n")
    print("----------老王论坛开始签到----------")
    
    msg = ""
    success_count = 0
    
    for idx, (account, password) in enumerate(accounts, 1):
        log = f"\n🙍🏻 第{idx}个账号 ({account})\n"
        msg += log
        print(log)
        
        signin = LaowangSignin(account, password, idx)
        success, result_msg = signin.sign()
        
        if success:
            result_str = f"✅ {result_msg}\n"
            success_count += 1
        else:
            result_str = f"❌ {result_msg}\n"
        
        msg += result_str
        print(result_str)
        
        # 多账号间随机延迟
        if idx < len(accounts):
            delay = random.uniform(5, 15)
            print(f"⏱️  等待 {delay:.1f} 秒后处理下一个账号...")
            time.sleep(delay)
    
    print("----------老王论坛签到执行完毕----------")
    print(f"\n==== 老王论坛签到完成 - 成功{success_count}/{len(accounts)} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    
    # 推送通知
    if notify:
        try:
            notify("老王论坛签到", msg[:-1])  # 去掉最后的换行符
        except Exception as e:
            logging.error(f"推送失败: {e}")
