"""
哔咔漫画自动签到脚本
cron "30 8 * * *" script-path=pica_punch.py,tag=哔咔签到
new Env('哔咔签到')
"""
import logging
import os
import sys
import re
import time
import random
import hmac
import hashlib
import requests
from datetime import datetime, timedelta

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
        
    print(f"哔咔签到需要等待 {format_time_remaining(delay_seconds)}")
    
    remaining = delay_seconds
    while remaining > 0:
        if remaining <= 10 or remaining % 10 == 0:
            print(f"倒计时: {format_time_remaining(remaining)}")
        
        sleep_time = 1 if remaining <= 10 else min(10, remaining)
        time.sleep(sleep_time)
        remaining -= sleep_time


class PicaPuncher:
    """哔咔漫画自动签到"""

    API_URL = os.getenv("PICA_API_URL", "https://picaapi.go2778.com").rstrip("/")
    API_URLS = (API_URL, "https://picaapi.picacomic.com")
    SECRET_KEY = r"~d}$Q7$eIni=V)9\RK/P.RM4;9[7|@/CA}b~OW!3?EV`:<>M7pddUBL5n|0/*Cn"
    API_KEY = "C69BAF41DA5ABD1FFEDC6D2FEA56B"

    def __init__(self, username, password, proxy=None):
        self.username = username
        self.password = password
        self.proxies = {"http": proxy, "https": proxy} if proxy else None

    def _get_headers(self, path, method, token=None):
        """构建哔咔加密请求头"""
        nonce = "b1ab87b4800d4d4590a11701b8551afa"
        ts = str(int(time.time()))
        raw = (path + ts + nonce + method + self.API_KEY).lower()
        signature = hmac.new(
            self.SECRET_KEY.encode(), raw.encode(), hashlib.sha256
        ).hexdigest()

        headers = {
            "api-key": self.API_KEY,
            "signature": signature,
            "time": ts,
            "nonce": nonce,
            "app-channel": "2",
            "app-version": "2.2.1.2.3.3",
            "app-uuid": "defaultUuid",
            "app-platform": "android",
            "app-build-version": "44",
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "okhttp/3.8.1",
            "accept": "application/vnd.picacomic.com.v1+json",
        }
        if token:
            headers["authorization"] = token
        return headers

    def run(self):
        login_path = "auth/sign-in"
        punch_path = "users/punch-in"

        for api_url in self.API_URLS:
            try:
                logging.info(f"正在尝试登录哔咔 (用户: {self.username}, 地址: {api_url})...")
                res = requests.post(
                    f"{api_url}/{login_path}",
                    json={"email": self.username, "password": self.password},
                    headers=self._get_headers(login_path, "POST"),
                    proxies=self.proxies,
                    timeout=20,
                )

                login_data = res.json()
                if res.status_code != 200 or login_data.get("message") != "success":
                    logging.warning(f"哔咔登录失败 ({api_url}): {login_data.get('message')}")
                    continue

                token = login_data.get("data", {}).get("token")
                if not token:
                    logging.warning(f"哔咔获取token失败 ({api_url})")
                    continue

                logging.info(f"🎉 哔咔登录成功 ({api_url})")

                res = requests.post(
                    f"{api_url}/{punch_path}",
                    headers=self._get_headers(punch_path, "POST", token),
                    proxies=self.proxies,
                    timeout=20,
                )

                punch_data = res.json()
                if punch_data.get("message") == "success":
                    logging.info("✅ 哔咔签到成功")
                    return True
                elif punch_data.get("message") == "user already punch in":
                    logging.info("⚠️  哔咔今日已签到")
                    return True

                logging.warning(f"⚠️  哔咔签到失败 ({api_url}): {punch_data.get('message')}")
            except Exception as e:
                logging.warning(f"哔咔地址访问异常 ({api_url}): {e}")

        logging.error("❌ 哔咔所有地址均签到失败")
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
    print(f"==== 哔咔签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    
    # 随机延迟（可选）
    if random_signin:
        delay_seconds = random.randint(0, max_random_delay)
        if delay_seconds > 0:
            signin_time = datetime.now() + timedelta(seconds=delay_seconds)
            print(f"随机模式: 延迟 {format_time_remaining(delay_seconds)} 后签到")
            print(f"预计签到时间: {signin_time.strftime('%H:%M:%S')}")
            wait_with_countdown(delay_seconds)
    
    print("----------哔咔开始尝试签到----------")
    
    logging.info("=" * 50)
    logging.info("🚀 哔咔签到脚本启动")
    logging.info("=" * 50)

    # 获取配置
    pica_accounts = []
    
    # 优先使用 PICA_ACCOUNT（多账号）
    pica_account_str = os.getenv('PICA_ACCOUNT', '').strip()
    if pica_account_str:
        pica_accounts = parse_accounts(pica_account_str)
    else:
        # 兼容旧配置
        pica_user = os.getenv('PICA_USER', '').strip()
        pica_pw = os.getenv('PICA_PW', '').strip()
        if pica_user and pica_pw:
            pica_accounts.append((pica_user, pica_pw))
    
    proxy = os.getenv('MY_PROXY', '').strip() or None

    if not pica_accounts:
        logging.error("❌ 未配置哔咔账号，请设置 PICA_ACCOUNT 或 PICA_USER/PICA_PW")
        sys.exit(1)

    results = []
    for idx, (user, pwd) in enumerate(pica_accounts, 1):
        logging.info(f"\n【账号 {idx}/{len(pica_accounts)}】")
        puncher = PicaPuncher(user, pwd, proxy)
        if puncher.run():
            results.append(f"✅ 哔咔账号 {idx} 签到成功")
        else:
            results.append(f"❌ 哔咔账号 {idx} 签到失败")

    summary = "\n".join(results)
    logging.info("\n" + "=" * 50)
    logging.info("📊 签到结果:")
    logging.info(summary)
    logging.info("=" * 50)

    # 推送通知
    if notify:
        try:
            notify("哔咔签到", summary)
        except Exception as e:
            logging.error(f"推送失败: {e}")
    
    print("----------哔咔签到执行完毕----------")
    print(f"==== 哔咔签到完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
