# ql-checkin

> 个人青龙面板签到脚本集合，覆盖网盘、漫画、论坛、机场、积分任务等常见自动化场景。

[![GitHub stars](https://img.shields.io/github/stars/anchengxiake/ql-checkin?style=flat-square)](https://github.com/anchengxiake/ql-checkin/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/anchengxiake/ql-checkin?style=flat-square)](https://github.com/anchengxiake/ql-checkin/network)
[![GitHub issues](https://img.shields.io/github/issues/anchengxiake/ql-checkin?style=flat-square)](https://github.com/anchengxiake/ql-checkin/issues)

## 项目简介

`ql-checkin` 是一个面向青龙面板的 Python 签到脚本库。每个脚本都可以独立运行，适合按需订阅、配置环境变量并创建定时任务。

请只在你拥有账号且服务条款允许的范围内使用本项目。账号、密码、Cookie、Token 都属于敏感信息，不要提交到仓库或公开日志。

## 功能特性

- 多场景覆盖：网盘、漫画、论坛、机场、Microsoft Rewards 等。
- 青龙友好：脚本优先适配 `notify.py` 推送模块。
- 多账号支持：大部分脚本支持换行、`&`、`&&`、`@` 或编号变量。
- 随机延迟：多数脚本支持 `RANDOM_SIGNIN` 和 `MAX_RANDOM_DELAY`。
- 隐私保护：部分脚本支持账号、Cookie、Token 脱敏输出。

## 目录结构

```text
ql-checkin/
├── README.md                    # 项目说明
├── aliyunpan_checkin.py          # 阿里云盘签到
├── baiduwangpan_checkin.py       # 百度网盘签到
├── ikuuu_checkin.py              # IKUUU 签到
├── jm_punch.py                   # 禁漫天堂签到
├── laowang_sign_ql.py            # 老王论坛青龙单文件版
├── mcloud.py                     # 移动云盘签到
├── Microsoft_Rewards_v2.1.py     # Microsoft Rewards 任务
├── pica_punch.py                 # 哔咔漫画签到
├── quark_punch.py                # 夸克网盘签到
├── south.py                      # SouthPlus 任务
└── ty_netdisk_checkin.py         # 天翼云盘签到
```

## 快速开始

### 1. 拉取仓库

在青龙面板「订阅管理」中添加订阅：

```text
https://github.com/anchengxiake/ql-checkin.git
```

也可以只上传需要执行的 `.py` 文件到青龙脚本目录。

### 2. 安装依赖

基础脚本通常只需要：

```bash
pip3 install requests rsa
```

漫画、浏览器自动化等脚本需要额外依赖：

```bash
pip3 install jmcomic DrissionPage ddddocr python-dotenv opencv-python
```

老王论坛和 SouthPlus 需要 Chrome/Chromium。青龙容器内没有浏览器时，可按系统环境安装，例如 Debian/Ubuntu 容器：

```bash
apt-get update
apt-get install -y chromium chromium-driver
```

### 3. 配置环境变量

在青龙面板「环境变量」中添加对应变量。复杂密码和 Cookie 推荐使用换行分隔，避免和 `&`、`:` 等分隔符冲突。

### 4. 创建定时任务

任务类型选择 `Python3`，命令示例：

```bash
task quark_punch.py
task laowang_sign_ql.py
```

## 脚本清单

| 类型 | 脚本 | 主要变量 | Cron 建议 | 说明 |
| --- | --- | --- | --- | --- |
| 哔咔漫画 | `pica_punch.py` | `PICA_ACCOUNT` | `30 8 * * *` | 支持 `PICA_USER` / `PICA_PW` |
| 禁漫天堂 | `jm_punch.py` | `JM_ACCOUNT` | `35 8 * * *` | 依赖 `jmcomic` |
| 夸克网盘 | `quark_punch.py` | `COOKIE_QUARK` | `13 8 * * *` | Cookie 签到 |
| 阿里云盘 | `aliyunpan_checkin.py` | `ALIYUN_REFRESH_TOKEN` | `3 11 * * *` | 支持自动更新 refresh token |
| 百度网盘 | `baiduwangpan_checkin.py` | `BAIDU_COOKIE` | `0 9 * * *` | Cookie 签到、成长任务 |
| 天翼云盘 | `ty_netdisk_checkin.py` | `TY_USERNAME`, `TY_PASSWORD` | `1 16 * * *` | 账号密码签到 |
| 移动云盘 | `mcloud.py` | `ydyp_ck` | `5 12 * * *` | Cookie 签到 |
| IKUUU | `ikuuu_checkin.py` | `IKUUU_EMAIL`, `IKUUU_PASSWD` | `0 21 * * *` | 多账号逗号分隔 |
| SouthPlus | `south.py` | `SOUTHPLUS_COOKIE` | `0 9 * * *` | 推荐 Cookie 模式 |
| 老王论坛 | `laowang_sign_ql.py` | `LAOWANG_ACCOUNT` | `0 9 * * *` | 青龙推荐单文件版 |
| Microsoft Rewards | `Microsoft_Rewards_v2.1.py` | `bing_ck_1` | `1 7-20 * * *` | Cookie 必填，Token 可选 |

## 环境变量配置

### 通用配置

| 变量名 | 说明 | 默认值 | 备注 |
| --- | --- | --- | --- |
| `RANDOM_SIGNIN` | 是否启用随机延迟 | `true` | 设为 `false` 可关闭 |
| `MAX_RANDOM_DELAY` | 最大随机延迟秒数 | `3600` | 老王论坛默认 `300` |
| `PRIVACY_MODE` | 隐私保护模式 | `true` | 部分脚本支持 |
| `MY_PROXY` | 通用代理 | 空 | 漫画类脚本会读取 |

关闭随机延迟：

```bash
RANDOM_SIGNIN=false
# 或
MAX_RANDOM_DELAY=0
```

### 推送通知

脚本会优先尝试加载青龙常见的 `notify.py`。通知变量由你的 `notify.py` 决定，常见变量如下：

| 变量名 | 说明 |
| --- | --- |
| `PUSH_KEY` | Server 酱 |
| `PUSH_PLUS_TOKEN` | PushPlus |
| `TG_BOT_TOKEN` | Telegram Bot Token |
| `TG_USER_ID` | Telegram 用户 ID |
| `DD_BOT_TOKEN` | 钉钉机器人 Token |
| `DD_BOT_SECRET` | 钉钉机器人密钥 |
| `BARK_PUSH` | Bark 推送地址 |

### 漫画类

| 脚本 | 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- | --- |
| `pica_punch.py` | `PICA_ACCOUNT` | 推荐 | `user@example.com:password` | 多账号用换行或 `&` |
| `pica_punch.py` | `PICA_USER`, `PICA_PW` | 兼容 | `user@example.com` / `password` | 单账号旧变量 |
| `jm_punch.py` | `JM_ACCOUNT` | 推荐 | `username:password` | 多账号用换行或 `&` |
| `jm_punch.py` | `JM_USER`, `JM_PW` | 兼容 | `username` / `password` | 单账号旧变量 |
| 通用 | `MY_PROXY` | 可选 | `http://127.0.0.1:7890` | 代理 |

示例：

```bash
PICA_ACCOUNT=user1@example.com:password1
user2@example.com:password2

JM_ACCOUNT=username1:password1
username2:password2
```

### 网盘类

| 脚本 | 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- | --- |
| `quark_punch.py` | `COOKIE_QUARK` | 必需 | `kps=xxx; sign=xxx; vcode=xxx; user=xxx` | 多账号用换行或 `&&` |
| `aliyunpan_checkin.py` | `ALIYUN_REFRESH_TOKEN` | 必需 | `refresh_token_1` | 多账号用换行或 `&` |
| `aliyunpan_checkin.py` | `AUTO_UPDATE_TOKEN` | 可选 | `true` | 自动更新青龙变量 |
| `aliyunpan_checkin.py` | `SHOW_TOKEN_IN_NOTIFICATION` | 可选 | `false` | 不建议开启 |
| `baiduwangpan_checkin.py` | `BAIDU_COOKIE` | 必需 | `BDUSS=xxx; STOKEN=xxx` | 多账号换行 |
| `ty_netdisk_checkin.py` | `TY_USERNAME` | 必需 | `13812345678` | 多账号用换行或 `&` |
| `ty_netdisk_checkin.py` | `TY_PASSWORD` | 必需 | `password` | 与账号顺序一致 |
| `ty_netdisk_checkin.py` | `TY_PASSWD` | 兼容 | `password` | 兼容部分上游文档写法 |
| `mcloud.py` | `ydyp_ck` | 必需 | `cookie1` | 多账号用换行或 `@` |

示例：

```bash
COOKIE_QUARK=cookie1&&cookie2

ALIYUN_REFRESH_TOKEN=refresh_token_1
refresh_token_2

BAIDU_COOKIE=BDUSS=xxx; STOKEN=xxx

TY_USERNAME=13812345678&13987654321
TY_PASSWORD=password1&password2

ydyp_ck=cookie1
cookie2
```

### IKUUU

| 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- |
| `IKUUU_EMAIL` | 必需 | `user1@example.com,user2@example.com` | 多账号英文逗号分隔 |
| `IKUUU_PASSWD` | 必需 | `password1,password2` | 与邮箱顺序一致 |

### SouthPlus

推荐使用 Cookie 模式，账号密码模式可能触发图形验证码。

| 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- |
| `SOUTHPLUS_COOKIE` | 推荐 | `your_cookie` | 专用 Cookie 变量 |
| `COOKIE` | 兼容 | `your_cookie` | 旧变量，可能和其它脚本冲突 |
| `SOUTHPLUS_USERNAME` | 可选 | `username` | 账号密码模式 |
| `SOUTHPLUS_PASSWORD` | 可选 | `password` | 账号密码模式 |
| `SOUTHPLUS_SITE` | 可选 | `https://www.south-plus.net` | 默认站点 |
| `SOUTHPLUS_USER_AGENT` | 可选 | 浏览器 UA | Cookie 绑定 UA 时填写 |
| `SOUTHPLUS_CF_WAIT` | 可选 | `60` | Cloudflare 等待秒数 |
| `SOUTHPLUS_DEBUG` | 可选 | `false` | 调试日志 |
| `SOUTHPLUS_CAPTCHA_RETRY_LIMIT` | 可选 | `3` | 登录验证码重试次数，`-1` 为无限重试 |
| `SOUTHPLUS_CAPTCHA_RETRY_BACKOFF` | 可选 | `2` | 验证码失败后的退避秒数基数 |
| `SOUTHPLUS_CAPTCHA_DEBUG_DIR` | 可选 | 系统临时目录 | 调试图片输出目录 |
| `DRISSIONPAGE_HEADLESS` | 可选 | `true` | 是否无头浏览器 |
| `DRISSIONPAGE_CHROME_PATH` | 可选 | `/usr/bin/chromium` | 自定义浏览器路径 |

### 老王论坛

青龙面板推荐使用单文件脚本：

```bash
task laowang_sign_ql.py
```

| 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- |
| `LAOWANG_ACCOUNT` | 必需 | `username:password` | 多账号用换行；密码含 `&` 时不要用 `&` 分隔 |
| `LAOWANG_CUSTOM_HOST` | 可选 | `104.21.14.105` | DNS 异常时指定 IP |
| `LAOWANG_DEBUG` | 可选 | `false` | 调试日志 |
| `LAOWANG_CF_WAIT` | 可选 | `60` | Cloudflare 等待秒数 |
| `LAOWANG_USE_SLIDE_MATCH_FALLBACK` | 可选 | `true` | 极少数情况下回退到 `ddddocr.slide_match` |
| `LAOWANG_SLIDER_RETRY_LIMIT` | 可选 | `8` | 滑块最大尝试次数 |
| `LAOWANG_SLIDER_RETRY_BACKOFF` | 可选 | `2` | 滑块刷新后的退避秒数基数 |

示例：

```bash
LAOWANG_ACCOUNT=user1:p@ss&word
user2:p@ss:word2
```

脚本特性：

- 使用 DrissionPage 启动浏览器登录。
- 使用 ddddocr `slide_comparison` 和 Canvas 候选点检测处理滑块。
- 针对页面出现两个缺口的情况，会尝试多个候选距离。
- 青龙/Linux 下会自动查找 `/usr/bin/chromium`、`/usr/bin/chromium-browser`、`/usr/bin/google-chrome` 等路径。

### Microsoft Rewards

| 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- |
| `bing_ck_1` | 必需 | `完整 Cookie` | 多账号按编号递增 |
| `bing_token_1` | 可选 | `refresh_token` | 主要用于阅读任务 |
| `MR_COOKIE_1` / `BING_COOKIE_1` / `ACCOUNT_1_COOKIE` | 兼容 | `完整 Cookie` | Cookie 兼容变量 |
| `MR_TOKEN_1` / `BING_TOKEN_1` / `ACCOUNT_1_REFRESH_TOKEN` | 兼容 | `refresh_token` | Token 兼容变量 |

国内青龙环境推荐：

```bash
MR_GEO_LOCALE=cn
MR_LANG_CODE=zh
MR_BING_HOST=https://cn.bing.com
MR_QUERY_ENGINES=china,local
RANDOM_SIGNIN=false
MAX_RANDOM_DELAY=0
```

常用调节项：

```bash
MR_SEARCH_DELAY_MIN=60
MR_SEARCH_DELAY_MAX=80
MR_REQUEST_TIMEOUT=15
MR_HOT_WORDS_MAX_COUNT=30
MR_PC_USER_AGENT=固定桌面端User-Agent
MR_MOBILE_USER_AGENT=固定移动端User-Agent
```

## Cookie 与 Token 获取

### 夸克网盘 Cookie

1. 浏览器访问 [夸克网盘](https://pan.quark.cn/) 并登录。
2. 打开开发者工具 `F12`，进入 `Network`。
3. 刷新页面，复制请求头里的完整 `Cookie`。

### 百度网盘 Cookie

1. 浏览器访问 [百度网盘](https://pan.baidu.com/) 并登录。
2. 打开开发者工具 `F12`，进入 `Network`。
3. 复制包含 `BDUSS`、`STOKEN` 等字段的完整 `Cookie`。

### 阿里云盘 refresh_token

1. 浏览器访问 [阿里云盘网页版](https://www.aliyundrive.com/) 并登录。
2. 打开开发者工具 `F12`，进入 `Application`。
3. 在 `Local Storage` 中找到 `https://www.aliyundrive.com`。
4. 找到 `token` 项，复制其中的 `refresh_token`。

### 移动云盘 Cookie

登录 [移动云盘](https://yun.139.com/) 后，从浏览器或抓包工具复制脚本需要的 Cookie，填入 `ydyp_ck`。多账号用换行或 `@` 分隔。

### SouthPlus Cookie

浏览器登录 SouthPlus 后，从开发者工具复制完整 Cookie。Cookie 可能和浏览器 User-Agent 绑定，必要时同步填写 `SOUTHPLUS_USER_AGENT`。

### Microsoft Rewards Cookie

使用同一个浏览器登录 Microsoft Rewards / Bing 后，复制 Bing 请求中的完整 Cookie。脚本会检查必要字段，Cookie 失效时需要重新抓取。

## 常见问题

### 依赖安装失败

先升级 pip：

```bash
python3 -m pip install -U pip setuptools wheel
```

如果 `opencv-python` 在青龙容器中安装困难，可以先不装；老王论坛脚本仍会使用 ddddocr 和 Canvas 候选点检测。

### 浏览器启动失败

确认容器中有 Chrome/Chromium：

```bash
which chromium
which chromium-browser
which google-chrome
```

如果浏览器安装在自定义路径，设置：

```bash
DRISSIONPAGE_CHROME_PATH=/path/to/chrome
```

### 账号密码中有特殊字符

优先使用换行分隔多账号，不要把复杂密码和 `&` 分隔符混在同一行。脚本通常按第一个英文冒号切分用户名和密码，因此密码中可以包含冒号。

### 老王论坛出现 Just a moment

日志里如果出现 `Just a moment...`、`Performing security verification`、`Cloudflare 安全验证未通过`，说明请求被 Cloudflare 前置安全验证拦住，脚本还没有进入论坛登录页。这不是账号变量格式错误。

可以尝试更换青龙运行网络、取消或更换 `LAOWANG_CUSTOM_HOST`，或使用能正常通过 Cloudflare 的浏览器环境。脚本只会等待站点正常放行，不内置绕过 Cloudflare 安全验证的逻辑。

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

## 致谢

本项目整理和维护过程中参考了多个优秀上游项目：

- 天翼云盘、百度网盘、阿里云盘、IKUUU 脚本来源和维护参考：[agluo/ql-script-hub](https://github.com/agluo/ql-script-hub)
- 哔咔漫画、禁漫天堂脚本来源和维护参考：[forchannot/comic-auto-punch-in](https://github.com/forchannot/comic-auto-punch-in)
- 夸克网盘脚本来源和维护参考：[anchengxiake/Quark_Auot_Check_In](https://github.com/anchengxiake/Quark_Auot_Check_In)
- 移动云盘脚本来源和维护参考：[hlt1995/qlScripts](https://github.com/hlt1995/qlScripts)
- Microsoft Rewards 脚本来源和维护参考：[chiihero/Microsoft-Rewards-Script](https://github.com/chiihero/Microsoft-Rewards-Script)
- 验证码重试、退避和调试文件管理思路参考：[LMTXQ/Rainyun-QingLong](https://github.com/LMTXQ/Rainyun-QingLong)

## 免责声明

- 本项目仅供学习交流使用，请勿用于商业用途。
- 使用本项目所产生的任何问题，作者不承担责任。
- 请遵守相关网站的使用条款和法律法规。

## License

请根据仓库实际许可证文件使用本项目。若重新发布或二次分发，请保留原作者和来源说明。
