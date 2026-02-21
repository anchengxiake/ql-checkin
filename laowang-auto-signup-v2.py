import DrissionPage
import time

BASE_URL = "https://laowang.vip/plugin.php?id=k_misign:sign"

ACCOUNT = "xxx"
PASSWORD = "xxx"

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

if __name__ == "__main__":

    # 初始化浏览器配置
    co = DrissionPage.ChromiumOptions()
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.92 Safari/537.36')
    co.set_pref('credentials_enable_service', False)
    co.set_argument('--hide-crash-restore-bubble')
    co.auto_port()
    co.headless(True)
    # 初始化浏览器
    browser = DrissionPage.ChromiumPage(co)
    browser.get(BASE_URL)
    browser.ele('@class=btn J_chkitot').click()
    browser.ele('@name=username').input(ACCOUNT)
    browser.ele('@name=password').input(PASSWORD)
    browser.ele('@class=tncode').click()
    pass_slide_verification(browser)
    browser.ele('@name=loginsubmit').click()
    browser.wait.url_change(BASE_URL, timeout=10)
    browser.ele('@class=btn J_chkitot').click()
    browser.ele('@class=tncode').click()
    pass_slide_verification(browser)
    browser.ele('@id=submit-btn').click()
    browser.wait.url_change(BASE_URL, timeout=10)
    print('签到完成')
    # 关闭浏览器
    browser.quit()


