# ql-checkin

青龙面板签到脚本集合，覆盖网盘、漫画、论坛、积分任务等常见自动签到场景。每个脚本都可以独立运行，推荐在青龙面板中按需订阅、配置环境变量并创建定时任务。

> 请只在你拥有账号且服务条款允许的范围内使用本项目。账号、Cookie、Token 都属于敏感信息，不要提交到仓库或公开日志。

## 功能概览

| 类型 | 推荐脚本 | 主要环境变量 | 说明 |
| --- | --- | --- | --- |
| 哔咔漫画 | `pica_punch.py` | `PICA_ACCOUNT` | 支持多账号，兼容 `PICA_USER` / `PICA_PW` |
| 禁漫天堂 | `jm_punch.py` | `JM_ACCOUNT` | 支持多账号，兼容 `JM_USER` / `JM_PW` |
| 夸克网盘 | `quark_punch.py` | `COOKIE_QUARK` | Cookie 签到 |
| 阿里云盘 | `aliyunpan_checkin.py` | `ALIYUN_REFRESH_TOKEN` | 支持自动更新 refresh token |
| 百度网盘 | `baiduwangpan_checkin.py` | `BAIDU_COOKIE` | Cookie 签到 |
| 天翼云盘 | `ty_netdisk_checkin.py` | `TY_USERNAME`, `TY_PASSWORD` | 账号密码签到 |
| 移动云盘 | `mcloud.py` | `ydyp_ck` | Cookie 签到 |
| IKUUU | `ikuuu_checkin.py` | `IKUUU_EMAIL`, `IKUUU_PASSWD` | 多账号用英文逗号分隔 |
| SouthPlus | `south.py` | `COOKIE` 或 `SOUTHPLUS_USERNAME` / `SOUTHPLUS_PASSWORD` | 需要 DrissionPage 和浏览器 |
| 老王论坛 | `laowang_sign_ql.py` | `LAOWANG_ACCOUNT` | 青龙推荐单文件版，自动处理滑块 |
| Microsoft Rewards | `Microsoft_Rewards_v2.1.py` | `bing_ck_1`, `bing_token_1` | Cookie 必填，Token 用于阅读任务 |

`laowang_sign.py` + `slider_solver.py` 是老王论坛的拆分开发版；青龙面板建议优先运行 `laowang_sign_ql.py`。`laowang_checkin*.py`、`debug_*.py`、`test_*.py`、`docs/` 等主要用于历史兼容、调试或开发验证。

## 青龙部署

### 1. 拉取仓库

在青龙面板的「订阅管理」中添加仓库：

```text
https://github.com/anchengxiake/ql-checkin.git
```

也可以只上传需要执行的 `.py` 文件到青龙脚本目录。

### 2. 安装依赖

基础脚本通常只需要 `requests`。老王论坛、SouthPlus 等浏览器自动化脚本需要额外依赖：

```bash
pip3 install requests DrissionPage ddddocr python-dotenv opencv-python
```

老王论坛和 SouthPlus 需要 Chrome/Chromium。青龙容器内没有浏览器时，可按你的系统环境安装 Chromium，例如 Debian/Ubuntu 容器：

```bash
apt-get update
apt-get install -y chromium chromium-driver
```

### 3. 配置环境变量

在青龙面板「环境变量」中添加对应变量。多个账号的分隔方式以各脚本说明为准，推荐使用换行分隔复杂密码或 Cookie。

### 4. 创建定时任务

任务类型选择 `Python3`，命令示例：

```bash
task laowang_sign_ql.py
```

常用定时参考：

```text
30 8 * * *      每天 08:30
0 9 * * *       每天 09:00
3 11 * * *      每天 11:03
1 7-20 * * *    每天 07:01 到 20:01 每小时执行
```

## 环境变量示例

### 通用配置

```bash
# 是否启用随机延迟，默认 true
RANDOM_SIGNIN=true

# 最大随机延迟秒数，默认大多为 3600；老王论坛默认 300
MAX_RANDOM_DELAY=300

# 关闭随机延迟：二选一即可
RANDOM_SIGNIN=false
MAX_RANDOM_DELAY=0

# 日志中隐藏账号敏感信息，支持的脚本默认开启
PRIVACY_MODE=true

# 通用代理，部分脚本会读取
MY_PROXY=http://127.0.0.1:7890
```

### 漫画类

```bash
# 哔咔漫画，多账号可用 & 或换行分隔
PICA_ACCOUNT=user1@example.com:password1
user2@example.com:password2

# 禁漫天堂，多账号可用 & 或换行分隔
JM_ACCOUNT=username1:password1
username2:password2
```

兼容旧变量：

```bash
PICA_USER=user@example.com
PICA_PW=password

JM_USER=username
JM_PW=password
```

### 网盘类

```bash
# 夸克网盘，多账号用换行或 && 分隔
COOKIE_QUARK=kps=xxx; sign=xxx; vcode=xxx; user=xxx

# 阿里云盘，多账号可用换行或 & 分隔
ALIYUN_REFRESH_TOKEN=refresh_token_1
refresh_token_2

# 百度网盘，多账号用换行分隔
BAIDU_COOKIE=BAIDUID=xxx; BDUSS=xxx; ...

# 天翼云盘，账号和密码数量需要一致
TY_USERNAME=username1&username2
TY_PASSWORD=password1&password2

# 移动云盘，多账号用 @ 或换行分隔
ydyp_ck=cookie1
cookie2
```

### IKUUU

```bash
IKUUU_EMAIL=user1@example.com,user2@example.com
IKUUU_PASSWD=password1,password2
```

### SouthPlus

Cookie 模式：

```bash
COOKIE=your_cookie
```

账号密码模式：

```bash
SOUTHPLUS_USERNAME=username
SOUTHPLUS_PASSWORD=password
SOUTHPLUS_SITE=https://south-plus.net
```

浏览器相关：

```bash
DRISSIONPAGE_HEADLESS=true
DRISSIONPAGE_CHROME_PATH=/usr/bin/chromium
```

### Microsoft Rewards

```bash
bing_ck_1=your_cookie
bing_token_1=optional_refresh_token

bing_ck_2=your_second_cookie
bing_token_2=optional_refresh_token
```

`bing_ck_1`、`bing_ck_2` 依次递增即可；`bing_token_*` 为可选项，主要用于阅读任务。

## 老王论坛说明

青龙面板推荐使用单文件脚本：

```bash
task laowang_sign_ql.py
```

必填变量：

```bash
LAOWANG_ACCOUNT=username:password
```

多账号推荐换行分隔。如果密码中包含 `&`，也建议换行分隔，避免和账号分隔符混淆：

```bash
LAOWANG_ACCOUNT=user1:password&with-symbol
user2:password2
```

可选变量：

```bash
# 调试日志
LAOWANG_DEBUG=true

# DNS 被污染或解析异常时指定 laowang.vip 的可用 IP
LAOWANG_CUSTOM_HOST=104.21.14.105

# 最大随机延迟秒数
MAX_RANDOM_DELAY=300

# 关闭随机延迟
RANDOM_SIGNIN=false
# 或
MAX_RANDOM_DELAY=0

# 极少数情况下回退到 ddddocr.slide_match
LAOWANG_USE_SLIDE_MATCH_FALLBACK=true
```

脚本特性：

- 使用 DrissionPage 启动浏览器登录。
- 使用 ddddocr `slide_comparison` 和 Canvas 候选点检测处理滑块。
- 针对页面出现两个缺口的情况，会尝试多个候选距离。
- 青龙/Linux 下会自动查找 `/usr/bin/chromium`、`/usr/bin/chromium-browser`、`/usr/bin/google-chrome` 等浏览器路径。

本地调试可以使用拆分版：

```bash
python laowang_sign.py
```

青龙执行时优先使用 `laowang_sign_ql.py`，因为它已经内置 `SliderSolver`，不依赖额外的本地模块文件。

## 推送通知

脚本会优先尝试加载青龙常见的 `notify.py`。如果青龙环境中已经配置了通知渠道，脚本执行结果会跟随 `notify.py` 推送。

常见通知变量由你的 `notify.py` 决定，例如：

```bash
PUSH_KEY=ServerChanKey
PUSH_PLUS_TOKEN=PushPlusToken
TG_BOT_TOKEN=TelegramBotToken
TG_USER_ID=TelegramUserId
DD_BOT_TOKEN=DingTalkToken
DD_BOT_SECRET=DingTalkSecret
BARK_PUSH=BarkUrl
```

## 定时任务建议

| 任务名称 | 命令 | Cron |
| --- | --- | --- |
| 哔咔签到 | `task pica_punch.py` | `30 8 * * *` |
| 禁漫签到 | `task jm_punch.py` | `35 8 * * *` |
| 夸克网盘签到 | `task quark_punch.py` | `13 8 * * *` |
| 阿里云盘签到 | `task aliyunpan_checkin.py` | `3 11 * * *` |
| 百度网盘签到 | `task baiduwangpan_checkin.py` | `0 9 * * *` |
| 天翼云盘签到 | `task ty_netdisk_checkin.py` | `1 16 * * *` |
| 移动云盘签到 | `task mcloud.py` | `5 12 * * *` |
| IKUUU 签到 | `task ikuuu_checkin.py` | `0 21 * * *` |
| SouthPlus 签到 | `task south.py` | `0 9 * * *` |
| 老王论坛签到 | `task laowang_sign_ql.py` | `0 9 * * *` |
| Microsoft Rewards | `task Microsoft_Rewards_v2.1.py` | `1 7-20 * * *` |

## 常见问题

### 依赖安装失败

先升级 pip：

```bash
python3 -m pip install -U pip setuptools wheel
```

如果 `opencv-python` 在容器中安装困难，可以先不装；老王论坛脚本仍会使用 ddddocr 和 Canvas 候选点检测。

### 浏览器启动失败

确认容器中有 Chrome/Chromium：

```bash
which chromium
which chromium-browser
which google-chrome
```

如果浏览器安装在自定义路径，SouthPlus 可设置：

```bash
DRISSIONPAGE_CHROME_PATH=/path/to/chrome
```

老王论坛脚本会自动搜索常见路径。

### 账号密码里有特殊字符

优先使用换行分隔多账号，不要把复杂密码和 `&` 分隔符混在同一行：

```bash
LAOWANG_ACCOUNT=user1:p@ss&word
user2:p@ss:word2
```

脚本会按第一个英文冒号切分用户名和密码，因此密码中可以包含冒号。

### 老王论坛 DNS 或网络异常

如果日志中出现 DNS 解析异常、连接超时或站点被解析到异常 IP，可以设置：

```bash
LAOWANG_CUSTOM_HOST=104.21.14.105
```

如果你的服务器访问站点需要代理，请优先在系统或青龙容器层面配置代理。

### Cookie 失效

Cookie 类脚本失败时，先在浏览器重新登录对应网站，再复制新的 Cookie/Token 到青龙环境变量。复制时保留完整字符串，不要额外添加引号。

## 开发说明

仓库中包含一些调试和历史文件：

- `tests/`：滑块识别等测试用例。
- `docs/`：开发设计记录。
- `debug_*.py`、`diagnose_*.py`、`test_*.py`：本地排查用脚本。
- `laowang_checkin*.py`：老版本或实验版本老王论坛脚本。
- `laowang_sign.py`、`slider_solver.py`：老王论坛拆分开发版。
- `laowang_sign_ql.py`：青龙单文件运行版。

提交前建议至少做一次语法检查：

```bash
python -m py_compile laowang_sign_ql.py
```

## License

请根据仓库实际许可证文件使用本项目。若重新发布或二次分发，请保留原作者和来源说明。
