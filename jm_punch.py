"""
禁漫天堂自动签到脚本
cron "30 8 * * *" script-path=jm_punch.py,tag=禁漫签到
new Env('禁漫签到')
"""
import logging
import os
import sys
import re
import time
import random
from datetime import datetime, timedelta
from jmcomic import JmOption

# 日志格式
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

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

def wait_with_countdown(delay_seconds):
    """带倒计时的等待"""
    if delay_seconds <= 0:
        return
        
    print(f"禁漫签到需要等待 {format_time_remaining(delay_seconds)}")
    
    remaining = delay_seconds
    while remaining > 0:
        if remaining <= 10 or remaining % 10 == 0:
            print(f"倒计时: {format_time_remaining(remaining)}")
        
        sleep_time = 1 if remaining <= 10 else min(10, remaining)
        time.sleep(sleep_time)
        remaining -= sleep_time


class JmPuncher:
    """禁漫天堂自动登录（基于 jmcomic 库）"""

    def __init__(self, username, password, proxy=None):
        self.username = username
        self.password = password
        self.proxy = proxy

    def run(self):
        try:
            logging.info(f"正在尝试登录禁漫 (用户: {self.username})...")
            
            # 构造禁漫配置
            option = JmOption.construct(
                {
                    "client": {
                        "username": self.username,
                        "password": self.password,
                        "proxies": {"http": self.proxy, "https": self.proxy}
                        if self.proxy
                        else None,
                    }
                }
            )
            client = option.build_jm_client()

            # 登录
            resp = client.login(self.username, self.password)
            user_data = resp.res_data

            logging.info("=" * 30)
            logging.info(f"🎉 禁漫登录成功！")
            logging.info(f"用户名: {user_data.get('username', self.username)}")
            logging.info(f"金币余额: {user_data.get('coin', 'N/A')}")
            logging.info("=" * 30)
            
            return True

        except Exception as e:
            logging.error(f"❌ 禁漫登录失败: {e}")
            return False


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
    print(f"==== 禁漫签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====\n")

    # 随机延迟（可选）
    if random_signin:
        delay_seconds = random.randint(0, max_random_delay)
        if delay_seconds > 0:
            signin_time = datetime.now() + timedelta(seconds=delay_seconds)
            print(f"随机模式: 延迟 {format_time_remaining(delay_seconds)} 后签到")
            print(f"预计签到时间: {signin_time.strftime('%H:%M:%S')}")
            wait_with_countdown(delay_seconds)
    
    print("----------禁漫开始尝试登录----------")
    jm_accounts = []
    
    # 优先使用 JM_ACCOUNT（多账号）
    jm_account_str = os.getenv('JM_ACCOUNT', '').strip()
    if jm_account_str:
        jm_accounts = parse_accounts(jm_account_str)
    else:
        # 兼容旧配置
        jm_user = os.getenv('JM_USER', '').strip()
        jm_pw = os.getenv('JM_PW', '').strip()
        if jm_user and jm_pw:
            jm_accounts.append((jm_user, jm_pw))
    
    proxy = os.getenv('MY_PROXY', '').strip() or None

    if not jm_accounts:
        logging.error("❌ 未配置禁漫账号，请设置 JM_ACCOUNT 或 JM_USER/JM_PW")
        sys.exit(1)

    print(f"✅ 检测到共 {len(jm_accounts)} 个禁漫账号\n")
    print("----------禁漫开始尝试登录----------")

    msg = ""
    for idx, (user, pwd) in enumerate(jm_accounts, 1):
        log = f"\n🙍🏻 第{idx}个账号 ({user})\n"
        msg += log
        
        puncher = JmPuncher(user, pwd, proxy)
        if puncher.run():
            result_msg = f"✅ 登录成功\n"
            msg += result_msg
        else:
            result_msg = f"❌ 登录失败\n"
            msg += result_msg
        
        logging.info(log + result_msg)
        
        # 多账号间随机延迟
        if idx < len(jm_accounts):
            time.sleep(1)

    print("----------禁漫登录执行完毕----------")
    print(f"\n==== 禁漫签到完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    
    # 推送通知
    if notify:
        try:
            notify("禁漫签到", msg[:-1])  # 去掉最后的换行符
        except Exception as e:
            logging.error(f"推送失败: {e}")
