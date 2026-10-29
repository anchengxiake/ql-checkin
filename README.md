# ql-checkin

> 个人青龙面板签到脚本集合，覆盖网盘、漫画、论坛、积分任务等场景。

[![GitHub stars](https://img.shields.io/github/stars/anchengxiake/ql-checkin?style=flat-square)](https://github.com/anchengxiake/ql-checkin/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/anchengxiake/ql-checkin/network?style=flat-square)](https://github.com/anchengxiake/ql-checkin/network)
[![GitHub issues](https://img.shields.io/github/issues/anchengxiake/ql-checkin?style=flat-square)](https://github.com/anchengxiake/ql-checkin/issues)

每个脚本都可以独立运行，按需订阅、配置环境变量、创建定时任务即可。账号、密码、Cookie、Token 都属于敏感信息，不要提交到仓库或贴到公开日志里。

## 脚本清单

| 脚本 | 功能 | 主要变量 | Python 依赖 | 建议 Cron |
| --- | --- | --- | --- | --- |
| `baiduwangpan_checkin.py` | 百度网盘签到、成长任务 | `BAIDU_COOKIE` | `requests` | `0 9 * * *` |
| `ty_netdisk_checkin.py` | 天翼云盘签到 | `TY_USERNAME`、`TY_PASSWORD` | `requests`、`rsa` | `1 16 * * *` |
| `mcloud.py` | 移动云盘签到、云朵任务 | `ydyp_ck` | `requests`、`pycryptodome` | `5 12 * * *` |
| `quark_punch.py` | 夸克网盘签到 | `COOKIE_QUARK` | `requests` | `13 8 * * *` |
| `pica_punch.py` | 哔咔漫画签到 | `PICA_ACCOUNT` | `requests` | `30 8 * * *` |
| `jm_punch.py` | 禁漫天堂签到 | `JM_ACCOUNT` | `jmcomic` | `35 8 * * *` |
| `south.py` | SouthPlus 每日任务 | `SOUTHPLUS_COOKIE` | `DrissionPage`；账号密码模式还需 `ddddocr`、`Pillow` | `0 9 * * *` |
| `laowang_sign_ql.py` | 老王论坛签到 | `LAOWANG_ACCOUNT` | `DrissionPage`、`ddddocr`、`python-dotenv`，滑块增强识别另需 `opencv-python-headless`、`numpy` | `0 9 * * *` |
| `rainyun_checkin.py` | 雨云签到、可选自动续费 | `RAINYUN_ACCOUNT` | `requests`、`selenium`、`ddddocr`、`opencv-python-headless` | `0 9 * * *` |

仓库根目录只有上表脚本，外加 `ql_notify.py`（通知适配器）、`README.md`、`LICENSE`、`.gitignore`。

其中 `south.py`、`laowang_sign_ql.py`、`rainyun_checkin.py` 需要真实浏览器：容器里必须有 Chromium/Chrome。只有走 selenium 的雨云还需要 `chromedriver`，DrissionPage 不需要。

## 快速开始

### 1. 订阅仓库

在青龙面板「订阅管理」中新增：

```text
https://github.com/anchengxiake/ql-checkin.git
```

| 配置项 | 建议值 |
| --- | --- |
| 分支 | `main` |
| 文件后缀 | `py` |
| 依赖文件 | `ql_notify.py` |

`ql_notify.py` 是本仓库的通知适配器。填到「依赖文件」后青龙会把它一起拉进脚本目录，各脚本据此调用青龙原生 `notify.py` 完成推送。它不会覆盖 `/ql/data/scripts/notify.py`，也不需要你手动改通知文件。

老版本青龙没有「依赖文件」字段时，把 `ql_notify.py` 和要运行的脚本上传到同一个脚本目录即可。**不要**把它重命名为 `notify.py`。

### 2. 安装依赖

按上表「Python 依赖」一列，在青龙「依赖管理 → Python3」里逐个添加即可，标准库不用管。想一次装全：

```bash
pip3 install requests rsa pycryptodome jmcomic DrissionPage ddddocr python-dotenv selenium opencv-python-headless Pillow numpy
```

浏览器相关的系统依赖，在 `whyour/qinglong:debian` 容器里：

```bash
apt-get update
apt-get install -y chromium chromium-driver
```

只有走 selenium 的雨云需要 `chromedriver`，DrissionPage（SouthPlus、老王论坛）只要有 Chromium 即可。`chromium` 和 `chromium-driver` 的版本要一致。Docker 里建议给浏览器加大共享内存：

```yaml
shm_size: "1gb"
```

无桌面服务器装 `opencv-python-headless`，不要同时装 `opencv-python`。`opencv-python` 装不上时可以先跳过，老王论坛脚本会退回 ddddocr 默认识别路径。

### 3. 配置环境变量

在青龙「环境变量」中添加，具体变量见下方按脚本分类的表格。

### 4. 创建定时任务

任务类型选 `Python3`，命令写脚本名即可：

```bash
task quark_punch.py
task laowang_sign_ql.py
```

## 环境变量

### 通用

| 变量名 | 说明 | 默认值 | 生效脚本 |
| --- | --- | --- | --- |
| `RANDOM_SIGNIN` | 是否在任务开始时随机延迟 | `true` | 全部脚本 |
| `MAX_RANDOM_DELAY` | 随机延迟上限（秒） | `3600` | 老王论坛默认 `300`；雨云默认取 `RAINYUN_CONFIG.max_delay × 60` |
| `PRIVACY_MODE` | 日志中对账号信息脱敏 | `true` | 百度网盘 |
| `MY_PROXY` | HTTP/HTTPS 代理 | 空 | 禁漫、哔咔 |

关闭随机延迟：

```bash
RANDOM_SIGNIN=false
# 或
MAX_RANDOM_DELAY=0
```

### 漫画类

| 脚本 | 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- | --- |
| `pica_punch.py` | `PICA_ACCOUNT` | 推荐 | `user@example.com:password` | 多账号用换行或 `&` |
| `pica_punch.py` | `PICA_USER`、`PICA_PW` | 兼容 | 单账号 | 旧变量，`PICA_ACCOUNT` 为空时读取 |
| `pica_punch.py` | `PICA_API_URL` | 可选 | `https://picaapi.go2778.com` | 首选地址，失败后自动尝试 `https://picaapi.picacomic.com` |
| `jm_punch.py` | `JM_ACCOUNT` | 推荐 | `username:password` | 多账号用换行或 `&` |
| `jm_punch.py` | `JM_USER`、`JM_PW` | 兼容 | 单账号 | 旧变量，`JM_ACCOUNT` 为空时读取 |

```bash
PICA_ACCOUNT=user1@example.com:password1
user2@example.com:password2

JM_ACCOUNT=username1:password1
username2:password2
```

### 网盘类

| 脚本 | 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- | --- |
| `quark_punch.py` | `COOKIE_QUARK` | 必需 | `user=张三; url=https://drive-m.quark.cn/...` | 抓包 URL 或参数两种格式，多账号用换行或 `&&` |
| `quark_punch.py` | `QUARK_DRY_RUN` | 可选 | `false` | 设为 `true` 只校验凭证与签到状态，不提交签到 |
| `baiduwangpan_checkin.py` | `BAIDU_COOKIE` | 必需 | `BDUSS=xxx; STOKEN=xxx` | 多账号用换行 |
| `ty_netdisk_checkin.py` | `TY_USERNAME` | 必需 | `13812345678` | 多账号用换行或 `&` |
| `ty_netdisk_checkin.py` | `TY_PASSWORD` | 必需 | `password` | 与账号顺序一一对应 |
| `ty_netdisk_checkin.py` | `TY_PASSWD` | 兼容 | `password` | `TY_PASSWORD` 为空时读取 |
| `mcloud.py` | `ydyp_ck` | 必需 | `Authorization#手机号` | 多账号用换行、`@` 或 `&` |
| `mcloud.py` | `ydyp` | 兼容 | 同上 | `ydyp_ck` 为空时读取 |

```bash
# 夸克：直接粘贴抓包 URL，多账号用换行或 && 分隔
COOKIE_QUARK=user=张三; url=https://drive-m.quark.cn/1/clouddrive/act/growth/reward?...;

# 夸克：也可以手动抄出三个参数
COOKIE_QUARK=user=张三; kps=xxx; sign=xxx; vcode=xxx;

BAIDU_COOKIE=BDUSS=xxx; STOKEN=xxx

TY_USERNAME=13812345678&13987654321
TY_PASSWORD=password1&password2

ydyp_ck=Basic xxxxx#13812345678
Basic yyyyy#13987654321
```

### 雨云

`rainyun_checkin.py` 把账号解析、API、续费、验证码识别和主流程都合在了一个文件里，不需要另外上传 `captcha.py`、`api_client.py` 或 `stealth.min.js`。

| 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- |
| `RAINYUN_ACCOUNT` | 必需 | `[["user@example.com","password"]]` | JSON 数组，多账号加子数组 |
| `RAINYUN_CONFIG` | 可选 | `{"captcha_retry_limit":10}` | 高级 JSON 配置，见下表 |
| `RAINYUN_HEADLESS` | 可选 | `true` | 是否无头运行 |
| `RAINYUN_USER_AGENT` | 可选 | Chrome UA | 自定义浏览器 User-Agent |
| `RAINYUN_CHROME_PATH` | 可选 | `/usr/bin/chromium` | 自定义浏览器路径 |
| `RAINYUN_DRIVER_PATH` | 可选 | `/usr/bin/chromedriver` | 自定义 chromedriver 路径 |
| `RAINYUN_TIMEOUT` | 可选 | `20` | 页面等待秒数，实际页面加载上限为该值 +10 |
| `RAINYUN_CAPTCHA_RETRY_LIMIT` | 可选 | `10` | 验证码重试次数，`-1` 为无限重试 |
| `RAINYUN_KEEP_DEBUG_FILES` | 可选 | `false` | 保留验证码临时图片 |
| `RAINYUN_DEBUG` | 可选 | `false` | 输出调试日志 |

`RAINYUN_ACCOUNT` 每个子数组四位：`[账号, 密码, 是否自动续费, API Key]`。前两位必填，第三位默认 `false`，启用续费时第四位必填。

```bash
# 仅签到
RAINYUN_ACCOUNT=[["user@example.com","password"]]

# 多账号，第一个启用自动续费
RAINYUN_ACCOUNT=[["user1@example.com","password1","true","api_key_1"],["user2@example.com","password2","false",""]]

# 验证码无限重试，服务器剩余 5 天时检查续费
RAINYUN_CONFIG={"captcha_retry_limit":-1,"renew_threshold_days":5}
```

`RAINYUN_CONFIG` 支持的键：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `timeout` | `20` | 页面等待超时秒数 |
| `captcha_wait` | `6` | 验证码识别后的等待秒数 |
| `max_delay` | `5` | 随机延迟上限（分钟），`MAX_RANDOM_DELAY` 会覆盖它 |
| `captcha_retry_limit` | `10` | 验证码重试次数，`-1` 为无限 |
| `similarity_threshold` | `0.4` | 图案匹配相似度阈值 |
| `download_max_retries` | `3` | 验证码图片下载重试次数 |
| `download_retry_delay` | `2` | 图片下载重试间隔秒数 |
| `download_timeout` | `10` | 图片下载超时秒数 |
| `api_base_url` | `https://api.v2.rainyun.com` | 雨云 API 地址 |
| `api_request_timeout` | `10` | API 请求超时秒数 |
| `api_max_retries` | `3` | API 请求重试次数 |
| `api_retry_delay` | `2` | API 重试间隔秒数 |
| `renew_days` | `7` | 自动续费时长 |
| `renew_threshold_days` | `3` | 剩余天数小于等于该值时触发续费 |
| `min_points_reserve` | `5000` | 续费后至少保留的积分 |
| `points_to_cny_rate` | `2000` | 积分换算金额的比例 |
| `account_interval_min` | `3` | 多账号间隔分钟数下限 |
| `account_interval_max` | `6` | 多账号间隔分钟数上限 |
| `headless` | `true` | 是否无头运行 |
| `keep_debug_files` | `false` | 是否保留验证码临时文件 |

日志出现 `timeout: Timed out receiving message from renderer` 说明登录页没在时限内加载完。把 `RAINYUN_TIMEOUT` 调到 `60`，同时避免把多个浏览器脚本排在同一个时间点。

### SouthPlus

推荐 Cookie 模式，账号密码模式容易触发图形验证码。

| 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- |
| `SOUTHPLUS_COOKIE` | 推荐 | `your_cookie` | 专用变量，多账号用换行或 `&&` |
| `COOKIE` | 兼容 | `your_cookie` | 旧变量，易与其他脚本冲突 |
| `SOUTHPLUS_USERNAME`、`SOUTHPLUS_PASSWORD` | 可选 | 账号密码 | 账号密码模式 |
| `SOUTHPLUS_SITE` | 可选 | `https://www.south-plus.net` | 默认站点 |
| `SOUTHPLUS_USER_AGENT` | 可选 | 浏览器 UA | Cookie 绑定 UA 时填写 |
| `SOUTHPLUS_CF_WAIT` | 可选 | `60` | Cloudflare 等待秒数 |
| `SOUTHPLUS_CAPTCHA_RETRY_LIMIT` | 可选 | `3` | 验证码重试次数，`-1` 为无限 |
| `SOUTHPLUS_CAPTCHA_RETRY_BACKOFF` | 可选 | `2` | 验证码失败退避秒数基数 |
| `SOUTHPLUS_CAPTCHA_DEBUG_DIR` | 可选 | 空 | 默认写到系统临时目录下的 `southplus-captcha` |
| `SOUTHPLUS_DEBUG` | 可选 | `false` | 调试日志 |
| `DRISSIONPAGE_HEADLESS` | 可选 | `true` | 是否无头运行 |
| `DRISSIONPAGE_CHROME_PATH` | 可选 | `/usr/bin/chromium` | 自定义浏览器路径 |

### 老王论坛

青龙面板用单文件版即可：

```bash
task laowang_sign_ql.py
```

| 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- |
| `LAOWANG_ACCOUNT` | 必需 | `username:password` | 多账号用换行；密码含 `&` 时不要用 `&` 分隔 |
| `LAOWANG_CUSTOM_HOST` | 可选 | `104.21.14.105` | DNS 异常时指定 IP |
| `LAOWANG_CF_WAIT` | 可选 | `60` | Cloudflare 等待秒数 |
| `LAOWANG_SLIDER_RETRY_LIMIT` | 可选 | `8` | 滑块最大尝试次数 |
| `LAOWANG_SLIDER_RETRY_BACKOFF` | 可选 | `2` | 滑块刷新后的退避基数 |
| `LAOWANG_USE_SLIDE_MATCH_FALLBACK` | 可选 | `true` | 是否回退到 ddddocr 的 `slide_match` |
| `LAOWANG_DEBUG` | 可选 | `false` | 调试日志 |

```bash
LAOWANG_ACCOUNT=user1:p@ss&word
user2:p@ss:word2
```

这个脚本会自动在 `/usr/bin/chromium`、`/usr/bin/chromium-browser`、`/usr/bin/google-chrome` 及常见 Windows 路径里找浏览器，**没有**单独指定浏览器路径的变量。找不到时请装好 chromium 或调整软链接。

## 凭证获取

### 夸克网盘

`COOKIE_QUARK` 里放的其实是签到接口的 `kps`、`sign`、`vcode` 三个 query 参数，**不是**浏览器里的整套 Cookie。新版夸克 App 对证书校验较严，普通"用户 CA"解不开 HTTPS，推荐 **MuMu 模拟器（开 Root）+ ProxyPin** 把证书装成 Android 系统证书。

1. 模拟器里装夸克 App 和 ProxyPin，开启 HTTPS 抓包。
2. 打开夸克网盘的签到/领空间页面。
3. 在 ProxyPin 里筛选域名 `drive-m.quark.cn`，找到 `https://drive-m.quark.cn/1/clouddrive/act/growth/reward?...` 这类请求。
4. **原样复制完整 URL**，按 `user=昵称; url=完整URL;` 填入即可，脚本自己解析三个参数。

URL 里可能含字面量 `+`，脚本按原样保留，不要手动改成空格或 `%2B`。参数有效期大约两个月，提示「缺少必要参数」或「凭证失效」时重新抓一次。

### 百度网盘

浏览器登录 [百度网盘](https://pan.baidu.com/)，F12 → Network，复制含 `BDUSS`、`STOKEN` 的完整 Cookie。

### 移动云盘

登录 [移动云盘](https://yun.139.com/) 后从浏览器或抓包工具复制 Authorization，按 `Authorization#手机号` 填入 `ydyp_ck`。

### SouthPlus

浏览器登录后复制完整 Cookie。Cookie 可能和 UA 绑定，必要时同步填 `SOUTHPLUS_USER_AGENT`。

## 推送通知

本仓库不替换青龙自带的 `notify.py`，而是通过 `ql_notify.py` 调用它。默认行为就是青龙全局通知，变量与官方一致：

```text
PUSH_KEY（Server 酱）、PUSH_PLUS_TOKEN、TG_BOT_TOKEN / TG_USER_ID、
DD_BOT_TOKEN / DD_BOT_SECRET、BARK_PUSH 等
```

需要给单个脚本指定渠道时，在变量名前加脚本前缀：

```text
PICA、JM、QUARK、BAIDU、TY、MCLOUD、RAINYUN、SOUTHPLUS、LAOWANG
```

例如只让雨云走 Telegram、只让 SouthPlus 走 PushPlus：

```text
RAINYUN_TG_BOT_TOKEN=xxx
RAINYUN_TG_USER_ID=xxx
SOUTHPLUS_PUSH_PLUS_TOKEN=xxx
```

规则是**覆盖式**：某个前缀下只要存在任何一个渠道变量，该脚本就只使用这些专属渠道，不再回退到全局配置。确认脚本前缀识别有误时，可以用 `QL_NOTIFY_PREFIX` 手动指定。

## 常见问题

**多账号怎么分隔？** 优先用换行。各脚本对 `&`、`&&`、`@` 的支持不一致，见上文各表格备注。

**账号密码里含特殊字符？** 换行分隔多账号最稳。脚本按第一个英文冒号切分用户名和密码，所以密码里可以有冒号。

**依赖装不上？** 先升级 pip：

```bash
python3 -m pip install -U pip setuptools wheel
```

**浏览器起不来？** 确认容器里有浏览器：

```bash
which chromium
which chromium-browser
which google-chrome
```

**Cookie 失效怎么办？** 重新登录对应网站，复制新的凭证。保留完整字符串，前后不要加引号。

**老王论坛出现 Just a moment？** 这是 Cloudflare 前置校验拦住了，还没进到登录页，不是变量格式问题。可以换青龙的运行网络、取消 `LAOWANG_CUSTOM_HOST`，或换一个能正常过验证的环境。脚本不内置绕过逻辑。

**夸克任务显示失败但我看已经签到了？** 接口返回「已经签到」时脚本按成功处理。若任务真的失败，退出码为 `1`（配置错误为 `2`），可以据此判断。

## 致谢

- 天翼云盘、百度网盘：[agluo/ql-script-hub](https://github.com/agluo/ql-script-hub)
- 哔咔漫画、禁漫天堂：[forchannot/comic-auto-punch-in](https://github.com/forchannot/comic-auto-punch-in)
- 夸克网盘：[anchengxiake/Quark_Auot_Check_In](https://github.com/anchengxiake/Quark_Auot_Check_In)（上游为 [Liu8Can/Quark_Auto_Check_In](https://github.com/Liu8Can/Quark_Auto_Check_In)）
- 移动云盘：[hlt1995/qlScripts](https://github.com/hlt1995/qlScripts)、任务协议参考 [3238614968/caiyun](https://github.com/3238614968/caiyun)
- 雨云：[LMTXQ/Rainyun-QingLong](https://github.com/LMTXQ/Rainyun-QingLong)

## 免责声明

本项目仅供学习交流，请勿用于商业用途。使用产生的问题由使用者自行承担，请遵守相关网站的服务条款和当地法律法规。

## License

[MIT License](LICENSE)。二次分发请保留原作者与来源说明。
