#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
cron: 0 21 * * *
new Env('ikuuu签到')

原始脚本来源: https://github.com/bighammer-link/jichang_dailycheckin
本脚本基于原作者的代码进行了适配和优化，以符合本脚本库的统一标准
感谢原作者的贡献！
"""

import os
import requests
import json
import re
import random
import time
import base64
from datetime import datetime, timedelta

# ---------------- 统一通知模块加载 ----------------
hadsend = False
send = None
try:
    from ql_notify import send
    hadsend = True
    print("✅ 已加载notify.py通知模块")
except ImportError:
    print("⚠️  未加载通知模块，跳过通知功能")

# 配置项
IKUUU_EMAIL = os.environ.get('IKUUU_EMAIL', '')
IKUUU_PASSWD = os.environ.get('IKUUU_PASSWD', '')
IKUUU_COOKIE = os.environ.get('IKUUU_COOKIE', '')
max_random_delay = int(os.getenv("MAX_RANDOM_DELAY", "3600"))
random_signin = os.getenv("RANDOM_SIGNIN", "true").lower() == "true"
privacy_mode = os.getenv("PRIVACY_MODE", "true").lower() == "true"

# IKUUU 域名配置
BASE_URL = os.getenv('IKUUU_BASE_URL', 'https://ikuuu.win').rstrip('/')
LOGIN_URL = f'{BASE_URL}/auth/login'
CHECK_URL = f'{BASE_URL}/user/checkin'

HEADER = {
    'origin': BASE_URL,
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'referer': f'{BASE_URL}/user',
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'x-requested-with': 'XMLHttpRequest'
}

def mask_email(email):
    """邮箱脱敏处理"""
    if not email or '@' not in email:
        return email
    
    if privacy_mode:
        local, domain = email.split('@', 1)
        if len(local) <= 2:
            masked_local = '*' * len(local)
        else:
            masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
        return f"{masked_local}@{domain}"
    return email

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

def wait_with_countdown(delay_seconds, task_name):
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

def split_env_values(value, allow_comma=True):
    """拆分多账号变量。Cookie 不建议用逗号，避免误切复杂字段。"""
    if not value:
        return []
    pattern = r'[\n\r]+|&&'
    if allow_comma:
        pattern = r'[,，\n\r]+'
    return [item.strip() for item in re.split(pattern, value) if item.strip()]

def mask_cookie(cookie):
    if not cookie:
        return "空Cookie"
    if not privacy_mode:
        return cookie
    head = cookie[:12]
    tail = cookie[-8:] if len(cookie) > 20 else ''
    return f"{head}***{tail}"

def looks_like_login_required(response):
    text = response.text[:500].lower()
    return (
        response.url.rstrip('/').endswith('/auth/login')
        or '/auth/login' in response.url
        or 'login' in text and 'password' in text
        or '用户登录' in response.text[:500]
    )

class IkuuuSigner:
    name = "ikuuu"

    def __init__(self, email: str = '', passwd: str = '', index: int = 1, cookie: str = ''):
        self.email = email
        self.passwd = passwd
        self.index = index
        self.cookie = cookie.strip()
        self.cookie_mode = bool(self.cookie)
        self.session = requests.Session()
        self.session.headers.update(HEADER)
        if self.cookie_mode:
            self.session.headers.update({'cookie': self.cookie, 'referer': f'{BASE_URL}/user'})

    def login(self):
        """用户登录"""
        if self.cookie_mode:
            print(f"🍪 使用 Cookie 模式: {mask_cookie(self.cookie)}")
            return self.validate_cookie()

        try:
            print(f"🔐 正在登录账号: {mask_email(self.email)}")
            print(f"🌐 使用域名: {BASE_URL}")
            
            data = {
                'email': self.email,
                'passwd': self.passwd
            }
            
            response = self.session.post(
                url=LOGIN_URL, 
                data=data, 
                timeout=15
            )
            
            print(f"🔍 登录响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"🔍 登录响应: {result}")
                    
                    if result.get('ret') == 1:
                        print(f"✅ 登录成功: {result.get('msg', '登录成功')}")
                        return True, "登录成功"
                    else:
                        error_msg = result.get('msg', '登录失败')
                        print(f"❌ 登录失败: {error_msg}")
                        if result.get('phase') == 'reset_login' or '验证结果' in error_msg:
                            error_msg += "；站点要求浏览器验证，建议改用 IKUUU_COOKIE"
                        return False, f"登录失败: {error_msg}"
                        
                except json.JSONDecodeError:
                    print(f"❌ 登录响应格式错误: {response.text[:200]}")
                    return False, "登录响应格式错误"
            else:
                error_msg = f"登录请求失败，状态码: {response.status_code}"
                print(f"❌ {error_msg}")
                return False, error_msg
                
        except requests.exceptions.Timeout:
            error_msg = "登录请求超时"
            print(f"❌ {error_msg}")
            return False, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = "网络连接错误，请检查域名是否正确"
            print(f"❌ {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"登录异常: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg

    def validate_cookie(self):
        """检查 Cookie 是否仍能访问用户页。"""
        try:
            response = self.session.get(f'{BASE_URL}/user', timeout=15)
            print(f"🔍 Cookie验证状态码: {response.status_code}")
            if response.status_code != 200:
                return False, f"Cookie验证失败，状态码: {response.status_code}"
            if looks_like_login_required(response):
                return False, "Cookie已失效或未包含登录态，请重新从浏览器复制完整Cookie"
            print("✅ Cookie 登录态有效")
            return True, "Cookie登录成功"
        except requests.exceptions.Timeout:
            return False, "Cookie验证超时"
        except requests.exceptions.ConnectionError:
            return False, "网络连接错误，请检查域名是否正确"
        except Exception as e:
            return False, f"Cookie验证异常: {str(e)}"

    def checkin(self):
        """执行签到"""
        try:
            print("📝 正在执行签到...")
            
            response = self.session.post(
                url=CHECK_URL, 
                timeout=15
            )
            
            print(f"🔍 签到响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"🔍 签到响应: {result}")
                    
                    msg = result.get('msg', '签到完成')
                    
                    # 从签到响应中提取流量奖励信息
                    traffic_reward = self.extract_traffic_reward(msg, result)
                    
                    # 判断签到结果
                    if result.get('ret') == 1:
                        success_msg = f"签到成功"
                        if traffic_reward:
                            success_msg += f"，获得流量: {traffic_reward}"
                        else:
                            success_msg += f"，{msg}"
                        print(f"✅ {success_msg}")
                        return True, success_msg
                    elif self.is_already_checked_in(msg):
                        already_msg = f"今日已签到"
                        if "已经签到" not in msg:
                            already_msg += f": {msg}"
                        print(f"📅 {already_msg}")
                        return True, already_msg
                    else:
                        print(f"❌ 签到失败: {msg}")
                        return False, f"签到失败: {msg}"
                        
                except json.JSONDecodeError:
                    print(f"❌ 签到响应格式错误: {response.text[:200]}")
                    return False, "签到响应格式错误"
            else:
                error_msg = f"签到请求失败，状态码: {response.status_code}"
                print(f"❌ {error_msg}")
                return False, error_msg
                
        except requests.exceptions.Timeout:
            error_msg = "签到请求超时"
            print(f"❌ {error_msg}")
            return False, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = "网络连接错误"
            print(f"❌ {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"签到异常: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg

    def extract_traffic_reward(self, msg, result):
        """从签到响应中提取流量奖励信息"""
        try:
            # 常见的流量奖励格式
            traffic_patterns = [
                r'获得[了]?\s*(\d+(?:\.\d+)?)\s*([KMGT]?B)',  # 获得 100MB
                r'奖励[了]?\s*(\d+(?:\.\d+)?)\s*([KMGT]?B)',  # 奖励 100MB
                r'增加[了]?\s*(\d+(?:\.\d+)?)\s*([KMGT]?B)',  # 增加 100MB
                r'签到成功.*?(\d+(?:\.\d+)?)\s*([KMGT]?B)',  # 签到成功，获得100MB
                r'(\d+(?:\.\d+)?)\s*([KMGT]?B).*?流量',     # 100MB 流量
                r'流量.*?(\d+(?:\.\d+)?)\s*([KMGT]?B)',     # 流量 100MB
                r'(\d+(?:\.\d+)?)\s*([KMGT]?B)',           # 直接的数字+单位
            ]
            
            # 尝试从msg中提取
            for pattern in traffic_patterns:
                match = re.search(pattern, msg, re.I)
                if match:
                    traffic = f"{match.group(1)}{match.group(2)}"
                    print(f"🎁 从消息中提取到流量奖励: {traffic}")
                    return traffic
            
            # 尝试从result的其他字段中提取
            if isinstance(result, dict):
                for key, value in result.items():
                    if isinstance(value, str):
                        for pattern in traffic_patterns:
                            match = re.search(pattern, value, re.I)
                            if match:
                                traffic = f"{match.group(1)}{match.group(2)}"
                                print(f"🎁 从{key}字段提取到流量奖励: {traffic}")
                                return traffic
            
            return None
            
        except Exception as e:
            print(f"⚠️ 提取流量奖励异常: {e}")
            return None

    def is_already_checked_in(self, msg):
        msg = msg or ''
        lower_msg = msg.lower()
        markers = ['已经签到', '今日已签到', '已签到', 'already', 'has been checked']
        return any(marker in lower_msg or marker in msg for marker in markers)

    def get_user_traffic(self):
        """从用户页尽量解析剩余流量，解析不到不影响签到结果。"""
        try:
            response = self.session.get(f'{BASE_URL}/user', timeout=15)
            if response.status_code != 200 or looks_like_login_required(response):
                return ''

            html = response.text
            match = re.search(r'originBody\s*=\s*"([^"]+)"', html)
            if match:
                try:
                    decoded = base64.b64decode(match.group(1)).decode('utf-8', errors='ignore')
                    html += decoded
                except Exception:
                    pass

            patterns = [
                r'剩余流量[^0-9A-Za-z]*([0-9.]+\s*[KMGT]?B)',
                r'可用流量[^0-9A-Za-z]*([0-9.]+\s*[KMGT]?B)',
                r'class="[^"]*counter[^"]*"[^>]*>\s*([0-9.]+)\s*</[^>]+>\s*([KMGT]?B)',
            ]
            for pattern in patterns:
                found = re.search(pattern, html, re.I | re.S)
                if found:
                    if len(found.groups()) >= 2:
                        return f"{found.group(1)}{found.group(2)}".replace(' ', '')
                    return found.group(1).replace(' ', '')
        except Exception as e:
            print(f"⚠️ 获取流量信息失败: {e}")
        return ''

    def main(self):
        """主执行函数"""
        print(f"\n==== ikuuu账号{self.index} 开始签到 ====")
        
        if not self.cookie_mode and (not self.email.strip() or not self.passwd.strip()):
            error_msg = """账号配置错误

❌ 错误原因: 邮箱或密码为空

🔧 解决方法:
1. 在青龙面板中添加环境变量IKUUU_EMAIL（邮箱地址）
2. 在青龙面板中添加环境变量IKUUU_PASSWD（对应密码）
3. 多账号用英文逗号分隔: email1,email2
4. 密码顺序要与邮箱顺序对应

💡 提示: 请确保邮箱和密码正确且一一对应
🌐 当前域名: ikuuu.de"""
            
            print(f"❌ {error_msg}")
            return error_msg, False

        # 1. 登录
        login_success, login_msg = self.login()
        if not login_success:
            return f"登录失败: {login_msg}", False
        
        # 2. 随机等待
        time.sleep(random.uniform(1, 3))
        
        # 3. 执行签到
        checkin_success, checkin_msg = self.checkin()
        
        # 4. 组合结果消息
        final_msg = f"""🌟 ikuuu签到结果

👤 账号: {mask_email(self.email) if not self.cookie_mode else f'Cookie账号{self.index}'}
🌐 域名: {BASE_URL}

📝 签到: {checkin_msg}
📦 剩余流量: {self.get_user_traffic() or '未获取到'}
⏰ 时间: {datetime.now().strftime('%m-%d %H:%M')}"""
        
        print(f"{'✅ 任务完成' if checkin_success else '❌ 任务失败'}")
        return final_msg, checkin_success

def main():
    """主程序入口"""
    print(f"==== ikuuu签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    print(f"🌐 当前域名: {BASE_URL}")
    
    # 显示配置状态
    print(f"🔒 隐私保护模式: {'已启用' if privacy_mode else '已禁用'}")
    
    # 随机延迟（整体延迟）
    if random_signin:
        delay_seconds = random.randint(0, max_random_delay)
        if delay_seconds > 0:
            print(f"🎲 随机延迟: {format_time_remaining(delay_seconds)}")
            wait_with_countdown(delay_seconds, "ikuuu签到")

    cookies = split_env_values(IKUUU_COOKIE, allow_comma=False)
    emails = split_env_values(IKUUU_EMAIL)
    passwords = split_env_values(IKUUU_PASSWD)
    use_cookie_mode = bool(cookies)

    if use_cookie_mode:
        accounts = [{'cookie': cookie, 'email': '', 'passwd': ''} for cookie in cookies]
        print(f"🍪 检测到 IKUUU_COOKIE，共 {len(accounts)} 个账号")
    elif emails and passwords:
        if len(emails) != len(passwords):
            error_msg = f"""❌ 邮箱和密码数量不匹配

📊 当前配置:
- 邮箱数量: {len(emails)}
- 密码数量: {len(passwords)}

🔧 解决方法:
请确保IKUUU_EMAIL和IKUUU_PASSWD环境变量中的账号数量一致
🌐 当前域名: {BASE_URL}"""

            print(error_msg)
            notify_user("ikuuu签到失败", error_msg)
            return
        accounts = [
            {'cookie': '', 'email': email, 'passwd': passwd}
            for email, passwd in zip(emails, passwords)
        ]
    else:
        error_msg = f"""❌ 未找到IKUUU_COOKIE，或 IKUUU_EMAIL/IKUUU_PASSWD 环境变量

🔧 配置方法:
1. 推荐使用 IKUUU_COOKIE: 浏览器登录后复制完整 Cookie，多账号用换行或 && 分隔
2. 备用方式 IKUUU_EMAIL / IKUUU_PASSWD: 多账号用英文逗号分隔
3. 账号密码登录可能触发站点验证，出现 reset_login 时请改用 Cookie

示例:
IKUUU_COOKIE=uid=xxx; email=xxx; key=xxx; ip=xxx; expire_in=xxx

IKUUU_EMAIL=user1@example.com,user2@example.com
IKUUU_PASSWD=password1,password2

🌐 当前域名: {BASE_URL}"""
        
        print(error_msg)
        notify_user("ikuuu签到失败", error_msg)
        return

    print(f"📝 共发现 {len(accounts)} 个账号")
    
    success_count = 0
    total_count = len(accounts)
    results = []
    
    for index, account in enumerate(accounts):
        try:
            # 账号间随机等待
            if index > 0:
                delay = random.uniform(5, 15)
                print(f"⏱️  随机等待 {delay:.1f} 秒后处理下一个账号...")
                time.sleep(delay)
            
            # 执行签到
            signer = IkuuuSigner(
                email=account.get('email', ''),
                passwd=account.get('passwd', ''),
                index=index + 1,
                cookie=account.get('cookie', ''),
            )
            result_msg, is_success = signer.main()
            
            if is_success:
                success_count += 1
            
            results.append({
                'index': index + 1,
                'success': is_success,
                'message': result_msg,
                'email': mask_email(account.get('email', '')) if not use_cookie_mode else f"Cookie账号{index + 1}"
            })
            
            # 发送单个账号通知
            status = "成功" if is_success else "失败"
            title = f"ikuuu账号{index + 1}签到{status}"
            notify_user(title, result_msg)
            
        except Exception as e:
            account_name = mask_email(account.get('email', '')) if not use_cookie_mode else f"Cookie账号{index + 1}"
            error_msg = f"账号{index + 1}({account_name}): 执行异常 - {str(e)}"
            print(f"❌ {error_msg}")
            notify_user(f"ikuuu账号{index + 1}签到失败", error_msg)
    
    # 发送汇总通知
    if total_count > 1:
        summary_msg = f"""📊 ikuuu签到汇总

📈 总计: {total_count}个账号
✅ 成功: {success_count}个
❌ 失败: {total_count - success_count}个
📊 成功率: {success_count/total_count*100:.1f}%
🌐 域名: {BASE_URL}
⏰ 完成时间: {datetime.now().strftime('%m-%d %H:%M')}"""
        
        # 添加详细结果（最多显示5个账号的详情）
        if len(results) <= 5:
            summary_msg += "\n\n📋 详细结果:"
            for result in results:
                status_icon = "✅" if result['success'] else "❌"
                summary_msg += f"\n{status_icon} {result['email']}"
        
        notify_user("ikuuu签到汇总", summary_msg)
    
    print(f"\n==== ikuuu签到完成 - 成功{success_count}/{total_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")

def handler(event, context):
    """云函数入口"""
    main()

if __name__ == "__main__":
    main()
