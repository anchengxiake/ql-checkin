# ql-checkin

> 个人青龙面板签到脚本集合，覆盖网盘、漫画、论坛、机场、积分任务等常见自动化场景。

[![GitHub stars](https://img.shields.io/github/stars/anchengxiake/ql-checkin?style=flat-square)](https://github.com/anchengxiake/ql-checkin/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/anchengxiake/ql-checkin?style=flat-square)](https://github.com/anchengxiake/ql-checkin/network)
[![GitHub issues](https://img.shields.io/github/issues/anchengxiake/ql-checkin?style=flat-square)](https://github.com/anchengxiake/ql-checkin/issues)

## 项目简介

`ql-checkin` 是一个面向青龙面板的 Python 签到脚本库。每个脚本都可以独立运行，适合按需订阅、配置环境变量并创建定时任务。

请只在你拥有账号且服务条款允许的范围内使用本项目。账号、密码、Cookie、Token 都属于敏感信息，不要提交到仓库或公开日志。

## 功能特性

- 多场景覆盖：网盘、漫画、论坛、机场等。
- 青龙友好：脚本优先适配 `notify.py` 推送模块。
- 多账号支持：大部分脚本支持换行、`&`、`&&`、`@` 或编号变量。
- 随机延迟：多数脚本支持 `RANDOM_SIGNIN` 和 `MAX_RANDOM_DELAY`。
- 隐私保护：部分脚本支持账号、Cookie、Token 脱敏输出。

## 目录结构

```text
ql-checkin/
├── README.md                    # 项目说明
├── baiduwangpan_checkin.py       # 百度网盘签到
├── jm_punch.py                   # 禁漫天堂签到
├── laowang_sign_ql.py            # 老王论坛青龙单文件版
├── mcloud.py                     # 移动云盘签到
├── pica_punch.py                 # 哔咔漫画签到
├── quark_punch.py                # 夸克网盘签到
├── rainyun_checkin.py             # 雨云签到及可选自动续费
├── south.py                      # SouthPlus 任务
├── ty_netdisk_checkin.py         # 天翼云盘签到
└── ql_notify.py                  # 按脚本分流并调用青龙 notify.py
```

## 快速开始

### 1. 拉取仓库

推荐在青龙面板「订阅管理」中添加订阅：

```text
https://github.com/anchengxiake/ql-checkin.git
```

订阅配置建议如下：

| 配置项 | 建议值 |
| --- | --- |
| 仓库地址 | `https://github.com/anchengxiake/ql-checkin.git` |
| 分支 | `main` |
| 文件后缀 | `py` |
| 依赖文件 | `ql_notify.py` |

`ql_notify.py` 是仓库内置的通知适配器。订阅时把它填写到青龙的「依赖文件」字段，青龙会将它一并复制到脚本目录；各签到脚本就能直接调用它。整个过程不会修改青龙自带的 `/ql/data/scripts/notify.py`，也不需要新人手动复制或编辑通知文件。

如果你的青龙版本没有「依赖文件」字段，请把仓库中的 `ql_notify.py` 与需要运行的签到脚本一起上传到同一个脚本目录。不要把它重命名为 `notify.py`，也不要覆盖青龙原生通知文件。

### 2. 安装依赖

本仓库没有发布由青龙官方维护的固定依赖清单。青龙的「依赖管理」只是按类型调用对应的包管理器；依赖名称和是否需要安装，仍以脚本源码中的导入为准。青龙官方支持 Python3、JavaScript、Shell、TypeScript，并提供环境变量和依赖管理功能；Docker 版的 `debian` 镜像适合安装 Alpine 不支持的系统依赖。

#### 安装顺序

如果要运行本仓库的全部脚本，请严格按以下顺序安装：

1. **先安装 Linux 依赖**：`chromium`、`chromium-driver`。这一步准备浏览器和系统组件。
2. **再安装 Python3 依赖**：`requests`、`rsa`、`pycryptodome` 等 Python 包。
3. **最后配置环境变量并运行测试任务**。

本仓库当前没有需要额外安装的 NodeJs 依赖。Linux 依赖安装完成并显示「已安装」后，再开始安装 Python3 依赖；如果 Linux 依赖安装失败，应先处理浏览器安装问题，不要直接跳过。

#### 第 1 步：青龙面板中选择 Linux

需要浏览器自动化的脚本还需要系统级浏览器。对于 `whyour/qinglong:debian` 容器，可安装：

```text
chromium
chromium-driver
```

二者必须使用兼容的主版本。安装完成后再继续 Python3 依赖。雨云脚本可通过环境变量指定路径：

```text
RAINYUN_CHROME_PATH=/usr/bin/chromium
RAINYUN_DRIVER_PATH=/usr/bin/chromedriver
```

SouthPlus 和老王论坛使用 DrissionPage，也需要容器内存在可启动的 Chromium/Chrome；可按需设置：

```text
DRISSIONPAGE_CHROME_PATH=/usr/bin/chromium
```

在 Docker 中建议给 Chromium 分配更大的共享内存，例如 Compose：

```yaml
shm_size: "1gb"
```

#### 第 2 步：青龙面板中选择 Python3

按需运行本仓库全部脚本时，建议安装：

```text
requests
rsa
pycryptodome
jmcomic
DrissionPage
ddddocr
python-dotenv
selenium
opencv-python-headless
Pillow
numpy
```

其中：

- `requests`、`rsa`、`pycryptodome`、`jmcomic`、`DrissionPage`、`ddddocr`、`python-dotenv`、`selenium` 是对应脚本的第三方依赖。
- `Pillow` 只在 SouthPlus 的图片验证码处理路径使用。
- `numpy` 与 OpenCV 图像识别路径配合使用；通常会作为 OpenCV 的依赖被安装。
- 无桌面服务器优先使用 `opencv-python-headless`，不要同时安装 `opencv-python` 和 `opencv-python-headless`。
- Python 标准库（例如 `os`、`json`、`re`、`datetime`、`urllib`）不需要在青龙中创建依赖。

如果只运行某个脚本，可以按下表最小安装：

| 脚本 | Python3 依赖 |
| --- | --- |
| `baiduwangpan_checkin.py`、`pica_punch.py`、`quark_punch.py` | `requests` |
| `jm_punch.py` | `jmcomic` |
| `mcloud.py` | `requests`、`pycryptodome` |
| `ty_netdisk_checkin.py` | `requests`、`rsa` |
| `rainyun_checkin.py` | `requests`、`selenium`；验证码路径还需要 `opencv-python-headless`、`numpy`、`ddddocr` |
| `south.py` | `DrissionPage`；验证码图片处理还需要 `ddddocr`、`Pillow` |
| `laowang_sign_ql.py` | `DrissionPage`、`ddddocr`；OpenCV 路径还需要 `opencv-python-headless`、`numpy`；`.env` 文件需要 `python-dotenv` |

#### 第 3 步：青龙面板中选择 NodeJs

本仓库当前列出的签到脚本均为 Python，不需要额外的 NodeJs 依赖。只有运行其他 JavaScript/TypeScript 脚本并且源码导入了第三方模块时，才在 NodeJs 分类中添加对应的 npm 包。

#### 使用命令行安装

面板安装失败时，可以进入青龙容器后使用与面板分类对应的包管理器：

```bash
# Python3 依赖
pip3 install requests rsa pycryptodome jmcomic DrissionPage ddddocr python-dotenv selenium opencv-python-headless Pillow numpy

# Debian 容器中的 Linux 依赖
apt-get update
apt-get install -y chromium chromium-driver
```

上面的 `pip3` 命令适合一次启用全部脚本；只运行部分脚本时可以按表格缩减依赖。

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
| 哔咔漫画 | `pica_punch.py` | `PICA_ACCOUNT` | `30 8 * * *` | 支持自定义 API 地址和国内地址失败自动切换 |
| 禁漫天堂 | `jm_punch.py` | `JM_ACCOUNT` | `35 8 * * *` | 依赖 `jmcomic` |
| 夸克网盘 | `quark_punch.py` | `COOKIE_QUARK` | `13 8 * * *` | Cookie 签到 |
| 百度网盘 | `baiduwangpan_checkin.py` | `BAIDU_COOKIE` | `0 9 * * *` | Cookie 签到、成长任务 |
| 天翼云盘 | `ty_netdisk_checkin.py` | `TY_USERNAME`, `TY_PASSWORD` | `1 16 * * *` | 账号密码签到 |
| 移动云盘 | `mcloud.py` | `ydyp_ck` | `5 12 * * *` | Cookie 签到 |
| 雨云 | `rainyun_checkin.py` | `RAINYUN_ACCOUNT` | `0 9 * * *` | 单文件，支持验证码和可选自动续费 |
| SouthPlus | `south.py` | `SOUTHPLUS_COOKIE` | `0 9 * * *` | 推荐 Cookie 模式 |
| 老王论坛 | `laowang_sign_ql.py` | `LAOWANG_ACCOUNT` | `0 9 * * *` | 青龙推荐单文件版 |

## 环境变量配置

### 通用配置

| 变量名 | 说明 | 默认值 | 支持脚本 |
| --- | --- | --- | --- |
| `RANDOM_SIGNIN` | 是否启用随机延迟 | `true` | 百度、禁漫、哔咔、夸克、移动云盘、SouthPlus、老王论坛、天翼云盘 |
| `MAX_RANDOM_DELAY` | 最大随机延迟秒数 | `3600` | 老王论坛默认 `300`；雨云使用 `RAINYUN_CONFIG.max_delay`，单位为分钟 |
| `PRIVACY_MODE` | 隐私保护模式 | `true` | 百度网盘 |
| `MY_PROXY` | HTTP/HTTPS 代理 | 空 | 禁漫、哔咔 |

关闭随机延迟：

```bash
RANDOM_SIGNIN=false
# 或
MAX_RANDOM_DELAY=0
```

### 推送通知

仓库内置 `ql_notify.py`，但不替换青龙自带的 `notify.py`。各签到脚本通过适配器调用青龙原生通知函数，因此青龙升级不会覆盖本仓库的分流逻辑。通过 GitHub 订阅更新时，`ql_notify.py` 会随仓库一起更新，通知逻辑由本仓库统一维护；青龙原生通知文件保持不变，降低新人配置和后期维护风险。

如果只选择部分脚本运行，也必须同时拉取或上传 `ql_notify.py`；否则脚本会回退到无法分流的状态，无法使用脚本专属通知配置。

默认行为是继续使用青龙全局通知变量：

| 变量名 | 说明 |
| --- | --- |
| `PUSH_KEY` | Server 酱 |
| `PUSH_PLUS_TOKEN` | PushPlus |
| `TG_BOT_TOKEN` | Telegram Bot Token |
| `TG_USER_ID` | Telegram 用户 ID |
| `DD_BOT_TOKEN` | 钉钉机器人 Token |
| `DD_BOT_SECRET` | 钉钉机器人密钥 |
| `BARK_PUSH` | Bark 推送地址 |

如需给单个脚本指定通知渠道，在变量名前加脚本前缀。脚本专属变量存在时，只使用该脚本专属配置；没有专属变量时自动回退到青龙全局配置。

支持的前缀：

```text
PICA、JM、QUARK、BAIDU、TY、MCLOUD、RAINYUN、SOUTHPLUS、LAOWANG
```

例如，只让雨云签到发送 Telegram，只让 SouthPlus 发送 PushPlus：

```text
RAINYUN_TG_BOT_TOKEN=你的雨云专属TG机器人Token
RAINYUN_TG_USER_ID=你的雨云专属TG用户ID

SOUTHPLUS_PUSH_PLUS_TOKEN=你的SouthPlus专属PushPlus Token
```

脚本专属变量名就是青龙原生变量名前加前缀，例如：

```text
RAINYUN_BARK_PUSH
BAIDU_PUSH_PLUS_TOKEN
JM_TG_BOT_TOKEN
LAOWANG_DD_BOT_TOKEN
```

注意：脚本专属配置是“覆盖式”的。配置了 `RAINYUN_TG_BOT_TOKEN` 后，雨云不会再使用全局的 `TG_BOT_TOKEN`；同一脚本前缀下配置多个渠道时，会同时发送到这些专属渠道。

### 漫画类

| 脚本 | 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- | --- |
| `pica_punch.py` | `PICA_ACCOUNT` | 推荐 | `user@example.com:password` | 多账号用换行或 `&` |
| `pica_punch.py` | `PICA_USER`, `PICA_PW` | 兼容 | `user@example.com` / `password` | 单账号旧变量 |
| `pica_punch.py` | `PICA_API_URL` | 可选 | `https://picaapi.go2778.com` | 首选 API 地址；登录或签到失败时自动尝试原地址 `https://picaapi.picacomic.com` |
| `pica_punch.py` | `RANDOM_SIGNIN` | 可选 | `true` | 是否启用随机延迟 |
| `pica_punch.py` | `MAX_RANDOM_DELAY` | 可选 | `3600` | 随机延迟最大秒数 |
| `pica_punch.py` | `MY_PROXY` | 可选 | `http://127.0.0.1:7890` | HTTP/HTTPS 代理 |
| `jm_punch.py` | `JM_ACCOUNT` | 推荐 | `username:password` | 多账号用换行或 `&` |
| `jm_punch.py` | `JM_USER`, `JM_PW` | 兼容 | `username` / `password` | 单账号旧变量 |
| `jm_punch.py` | `RANDOM_SIGNIN` | 可选 | `true` | 是否启用随机延迟 |
| `jm_punch.py` | `MAX_RANDOM_DELAY` | 可选 | `3600` | 随机延迟最大秒数 |
| `jm_punch.py` | `MY_PROXY` | 可选 | `http://127.0.0.1:7890` | HTTP/HTTPS 代理 |

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
| `quark_punch.py` | `RANDOM_SIGNIN` | 可选 | `true` | 是否启用随机延迟 |
| `quark_punch.py` | `MAX_RANDOM_DELAY` | 可选 | `3600` | 随机延迟最大秒数 |
| `baiduwangpan_checkin.py` | `BAIDU_COOKIE` | 必需 | `BDUSS=xxx; STOKEN=xxx` | 多账号换行 |
| `baiduwangpan_checkin.py` | `RANDOM_SIGNIN` | 可选 | `true` | 是否启用随机延迟 |
| `baiduwangpan_checkin.py` | `MAX_RANDOM_DELAY` | 可选 | `3600` | 随机延迟最大秒数 |
| `baiduwangpan_checkin.py` | `PRIVACY_MODE` | 可选 | `true` | 是否对账号信息脱敏 |
| `ty_netdisk_checkin.py` | `TY_USERNAME` | 必需 | `13812345678` | 多账号用换行或 `&` |
| `ty_netdisk_checkin.py` | `TY_PASSWORD` | 必需 | `password` | 与账号顺序一致 |
| `ty_netdisk_checkin.py` | `TY_PASSWD` | 兼容 | `password` | 兼容部分上游文档写法 |
| `ty_netdisk_checkin.py` | `RANDOM_SIGNIN` | 可选 | `true` | 是否启用随机延迟 |
| `ty_netdisk_checkin.py` | `MAX_RANDOM_DELAY` | 可选 | `3600` | 随机延迟最大秒数 |
| `mcloud.py` | `ydyp_ck` | 必需 | `Authorization#手机号` | 多账号用换行、`@` 或 `&`，兼容上游变量 `ydyp` |
| `mcloud.py` | `ydyp` | 兼容 | `Authorization#手机号` | `ydyp_ck` 未设置时读取；多账号用换行、`@` 或 `&` |
| `mcloud.py` | `RANDOM_SIGNIN` | 可选 | `true` | 是否启用随机延迟 |
| `mcloud.py` | `MAX_RANDOM_DELAY` | 可选 | `3600` | 随机延迟最大秒数 |

示例：

```bash
COOKIE_QUARK=cookie1&&cookie2

BAIDU_COOKIE=BDUSS=xxx; STOKEN=xxx

TY_USERNAME=13812345678&13987654321
TY_PASSWORD=password1&password2

ydyp_ck=Basic xxxxx#13812345678
Basic yyyyy#13987654321
```

### 雨云

`rainyun_checkin.py` 已将上游的账号解析、配置、API、服务器续费、验证码和主流程合并为一个文件，不需要额外上传 `captcha.py`、`api_client.py` 或 `stealth.min.js`。

| 变量名 | 是否必需 | 示例 | 备注 |
| --- | --- | --- | --- |
| `RAINYUN_ACCOUNT` | 必需 | `[["user@example.com","password","false",""]]` | JSON 数组，多账号添加多个子数组 |
| `RAINYUN_CONFIG` | 可选 | `{"captcha_retry_limit":10}` | 高级 JSON 配置 |
| `RAINYUN_HEADLESS` | 可选 | `true` | 是否使用无头浏览器 |
| `RAINYUN_USER_AGENT` | 可选 | Chrome UA | 自定义浏览器 User-Agent |
| `RAINYUN_CHROME_PATH` | 可选 | `/usr/bin/chromium` | 自定义浏览器路径 |
| `RAINYUN_DRIVER_PATH` | 可选 | `/usr/bin/chromedriver` | 自定义 ChromeDriver 路径 |
| `RAINYUN_CAPTCHA_RETRY_LIMIT` | 可选 | `10` | 覆盖验证码重试次数，`-1` 为无限重试 |
| `RAINYUN_TIMEOUT` | 可选 | `20` | 页面等待超时秒数 |
| `RAINYUN_KEEP_DEBUG_FILES` | 可选 | `false` | 保留验证码临时图片 |
| `RANDOM_SIGNIN` | 可选 | `true` | 是否启用随机延迟 |
| `MAX_RANDOM_DELAY` | 可选 | `RAINYUN_CONFIG.max_delay * 60` | 覆盖随机延迟最大秒数，单位为秒 |
| `RAINYUN_DEBUG` | 可选 | `false` | 输出调试日志 |

账号数组参数：

| 位置 | 说明 | 是否必需 |
| --- | --- | --- |
| 1 | 雨云登录账号 | 必需 |
| 2 | 雨云登录密码 | 必需 |
| 3 | 是否启用服务器自动续费 | 可选，默认 `false` |
| 4 | 雨云 API Key | 自动续费时必需 |

示例：

```bash
# 仅签到
RAINYUN_ACCOUNT=[["user@example.com","password"]]

# 多账号，其中第一个账号启用自动续费
RAINYUN_ACCOUNT=[["user1@example.com","password1","true","api_key_1"],["user2@example.com","password2","false",""]]

# 关闭随机延迟
RANDOM_SIGNIN=false
MAX_RANDOM_DELAY=0

# 验证码无限重试，并在服务器剩余 5 天时检查续费
RAINYUN_CONFIG={"captcha_retry_limit":-1,"renew_threshold_days":5}
```

`RAINYUN_CONFIG` 支持的完整配置项：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `timeout` | `20` | 页面等待超时秒数 |
| `captcha_wait` | `6` | 验证码识别后的等待秒数 |
| `max_delay` | `5` | 随机延迟最大分钟数 |
| `captcha_retry_limit` | `10` | 验证码重试次数，`-1` 为无限重试 |
| `similarity_threshold` | `0.4` | 图案匹配相似度阈值 |
| `download_max_retries` | `3` | 验证码图片下载最大重试次数 |
| `download_retry_delay` | `2` | 验证码图片下载重试间隔秒数 |
| `download_timeout` | `10` | 验证码图片下载超时秒数 |
| `api_base_url` | `https://api.v2.rainyun.com` | 雨云 API 地址 |
| `api_request_timeout` | `10` | API 请求超时秒数 |
| `api_max_retries` | `3` | API 请求最大重试次数 |
| `api_retry_delay` | `2` | API 请求重试间隔秒数 |
| `renew_days` | `7` | 自动续费时长 |
| `renew_threshold_days` | `3` | 剩余天数小于等于该值时触发续费 |
| `min_points_reserve` | `5000` | 续费后至少保留的积分 |
| `points_to_cny_rate` | `2000` | 积分兑换金额的换算比例 |
| `account_interval_min` | `3` | 多账号执行间隔最小分钟数 |
| `account_interval_max` | `6` | 多账号执行间隔最大分钟数 |
| `headless` | `true` | 是否使用无头浏览器 |
| `keep_debug_files` | `false` | 是否保留验证码临时文件 |

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
| `RANDOM_SIGNIN` | 可选 | `true` | 是否启用随机延迟 |
| `MAX_RANDOM_DELAY` | 可选 | `3600` | 随机延迟最大秒数 |

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
| `RANDOM_SIGNIN` | 可选 | `true` | 是否启用随机延迟 |
| `MAX_RANDOM_DELAY` | 可选 | `300` | 随机延迟最大秒数 |

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

## Cookie 与 Token 获取

### 夸克网盘 Cookie

1. 浏览器访问 [夸克网盘](https://pan.quark.cn/) 并登录。
2. 打开开发者工具 `F12`，进入 `Network`。
3. 刷新页面，复制请求头里的完整 `Cookie`。

### 百度网盘 Cookie

1. 浏览器访问 [百度网盘](https://pan.baidu.com/) 并登录。
2. 打开开发者工具 `F12`，进入 `Network`。
3. 复制包含 `BDUSS`、`STOKEN` 等字段的完整 `Cookie`。

### 移动云盘 Cookie

登录 [移动云盘](https://yun.139.com/) 后，从浏览器或抓包工具复制 Authorization，按 `Authorization#手机号` 填入 `ydyp_ck`。多账号用换行、`@` 或 `&` 分隔；脚本也兼容上游变量名 `ydyp`。

### SouthPlus Cookie

浏览器登录 SouthPlus 后，从开发者工具复制完整 Cookie。Cookie 可能和浏览器 User-Agent 绑定，必要时同步填写 `SOUTHPLUS_USER_AGENT`。

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
python -m py_compile laowang_sign_ql.py rainyun_checkin.py
```

## 致谢

本项目整理和维护过程中参考了多个优秀上游项目：

- 天翼云盘、百度网盘脚本来源和维护参考：[agluo/ql-script-hub](https://github.com/agluo/ql-script-hub)
- 哔咔漫画、禁漫天堂脚本来源和维护参考：[forchannot/comic-auto-punch-in](https://github.com/forchannot/comic-auto-punch-in)
- 夸克网盘脚本来源和维护参考：[anchengxiake/Quark_Auot_Check_In](https://github.com/anchengxiake/Quark_Auot_Check_In)
- 移动云盘脚本来源和维护参考：[hlt1995/qlScripts](https://github.com/hlt1995/qlScripts)
- 移动云盘任务协议（taskListV3 / 领取与抢兑）参考：[3238614968/caiyun](https://github.com/3238614968/caiyun)
- 雨云签到、验证码识别和自动续费来源及维护参考：[LMTXQ/Rainyun-QingLong](https://github.com/LMTXQ/Rainyun-QingLong)

## 免责声明

- 本项目仅供学习交流使用，请勿用于商业用途。
- 使用本项目所产生的任何问题，作者不承担责任。
- 请遵守相关网站的使用条款和法律法规。

## License

请根据仓库实际许可证文件使用本项目。若重新发布或二次分发，请保留原作者和来源说明。
