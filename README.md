#  综合签到脚本集合

多平台自动签到脚本集合，完全支持[青龙面板](https://github.com/whyour/qinglong)，包含漫画、网盘、宽带、论坛等多种服务的自动签到。

## 📋 支持平台

- 🎭 **漫画平台**：哔咔漫画、禁漫天堂
- 💾 **网盘平台**：夸克网盘、阿里云盘、百度网盘、天翼云盘
- 🌐 **宽带服务**：IKUAI 宽带签到
- 📝 **论坛社区**：老王论坛
- 🔄 **持续更新**：更多平台支持中...

## 🌟 特性

- ✅ **漫画平台**
  - 哔咔漫画自动签到（pica_punch.py）
  - 禁漫天堂自动登录（jm_punch.py）
- ✅ **网盘平台**
  - 夸克网盘自动签到（quark_punch.py）
  - 阿里云盘签到（aliyunpan_checkin.py）
  - 百度网盘签到（baiduwangpan_checkin.py）
  - 天翼云盘签到（ty_netdisk_checkin.py）
- ✅ **宽带服务**
  - IKUAI 签到（ikuuu_checkin.py）
- ✅ **论坛社区**
  - 老王论坛自动签到（laowang-auto-signup-v2.py）
- ✅ 支持多账号管理
- ✅ 支持随机延迟执行
- ✅ 支持推送通知（Server酱、PushPlus、Telegram、钉钉）
- ✅ 青龙面板原生支持

## 📦 文件说明

| 文件 | 说明 | 平台 | 环境变量 |
|-----|-----|-----|---------|
| `pica_punch.py` | 哔咔漫画签到脚本 | 漫画 | `PICA_ACCOUNT` |
| `jm_punch.py` | 禁漫天堂签到脚本 | 漫画 | `JM_ACCOUNT` |
| `quark_punch.py` | 夸克网盘签到脚本 | 网盘 | `COOKIE_QUARK` |
| `aliyunpan_checkin.py` | 阿里云盘签到脚本 | 网盘 | `ALIYUN_REFRESH_TOKEN` |
| `baiduwangpan_checkin.py` | 百度网盘签到脚本 | 网盘 | `BAIDU_COOKIE` |
| `ty_netdisk_checkin.py` | 天翼云盘签到脚本 | 网盘 | `TY_USERNAME` + `TY_PASSWORD` |
| `ikuuu_checkin.py` | IKUAI 签到脚本 | 其他 | `IKUUU_EMAIL` + `IKUUU_PASSWD` |
| `laowang-auto-signup-v2.py` | 老王论坛签到脚本（旧版） | 论坛 | `LAOWANG_COOKIE` |
| `laowang_checkin.py` | 老王论坛签到脚本（新版，推荐） | 论坛 | `LAOWANG_COOKIE` |

所有脚本都可以独立在青龙面板中运行，支持环境变量配置和推送通知。

## 🚀 快速开始

### 1. 选择需要的脚本

根据您的需求选择对应的签到脚本：

| 需求 | 推荐脚本 | 环境变量 |
|-----|---------|---------|
| 漫画签到 | `pica_punch.py` + `jm_punch.py` | `PICA_ACCOUNT`, `JM_ACCOUNT` |
| 网盘签到 | `quark_punch.py` + `aliyunpan_checkin.py` + `baiduwangpan_checkin.py` + `ty_netdisk_checkin.py` | `COOKIE_QUARK`, `ALIYUN_REFRESH_TOKEN`, `BAIDU_COOKIE`, `TY_USERNAME`+`TY_PASSWORD` |
| 宽带签到 | `ikuuu_checkin.py` | `IKUUU_EMAIL` + `IKUUU_PASSWD` |
| 论坛签到 | `laowang_checkin.py` | `LAOWANG_COOKIE` |
| 全平台签到 | 全部脚本 | 对应环境变量 |

### 2. 部署到青龙面板

#### 方法一：订阅部署（推荐）

在青龙面板 **订阅管理** 中添加：

```
https://github.com/anchengxiake/ql-checkin.git
```

#### 方法二：手动上传

下载需要的脚本文件，上传到青龙面板 `/ql/scripts/` 目录。

### 3. 配置环境变量

在青龙面板 **环境变量** 中添加相应配置（见下文详细配置）。

### 4. 创建定时任务

为每个脚本创建对应的定时任务（见下文定时任务配置）。

## 🔧 详细配置

### 环境变量配置

#### 哔咔漫画

```bash
# 推荐：多账号格式（用 & 或换行分隔）
PICA_ACCOUNT=user1@example.com:pass1&user2@example.com:pass2

# 或单账号
PICA_ACCOUNT=user@example.com:password

# 兼容：旧格式（单账号）
PICA_USER=user@example.com
PICA_PW=password
```

#### 禁漫天堂

```bash
# 推荐：多账号格式（用 & 或换行分隔）
JM_ACCOUNT=user1:pass1&user2:pass2

# 或单账号
JM_ACCOUNT=username:password

# 兼容：旧格式（单账号）
JM_USER=username
JM_PW=password
```

#### 夸克网盘

```bash
# Cookie格式（从浏览器开发者工具获取）
COOKIE_QUARK=kps=xxx;sign=xxx;vcode=xxx;user=用户名

# 多账号（用换行或 && 分隔）
COOKIE_QUARK=cookie1
cookie2
```

#### 阿里云盘

```bash
# 单账号（refresh_token）
ALIYUN_REFRESH_TOKEN=your_refresh_token

# 多账号（用换行或 & 分隔）
ALIYUN_REFRESH_TOKEN=token1
token2
token3
```

#### 百度网盘

```bash
# Cookie格式
BAIDU_COOKIE=your_baidu_cookie

# 多账号（用换行分隔）
BAIDU_COOKIE=cookie1
cookie2
```

#### 天翼云盘

```bash
# 账号密码格式（用 & 分隔多账号）
TY_USERNAME=username1&username2
TY_PASSWORD=password1&password2

# 或单账号
TY_USERNAME=username
TY_PASSWORD=password
```

#### IKUAI 宽带

```bash
# 邮箱密码格式（用逗号分隔多账号）
IKUUU_EMAIL=user1@example.com,user2@example.com
IKUUU_PASSWD=password1,password2

# 或单账号
IKUUU_EMAIL=user@example.com
IKUUU_PASSWD=password
```

#### 老王论坛

```bash
# 方式1: 账号密码 + 浏览器模式（自动处理滑块验证）⭐推荐
LAOWANG_ACCOUNT=用户名:密码
LAOWANG_BROWSER_MODE=true

# 方式2: Cookie（从浏览器获取，最稳定）
LAOWANG_COOKIE=your_cookie_here

# 方式3: 账号密码（HTTP模式，可能遇到滑块验证）
LAOWANG_ACCOUNT=用户名:密码

# 多账号用 & 或换行分隔
LAOWANG_ACCOUNT=user1:pass1&user2:pass2

# 代理配置（国内需要，香港/海外不需要）
LAOWANG_PROXY=http://127.0.0.1:7890
# 或使用全局代理
MY_PROXY=http://127.0.0.1:7890
```

**浏览器模式安装依赖：**
```bash
pip install DrissionPage
```

> 💡 **推荐使用账号密码模式**：
> - 自动登录获取最新 Cookie
> - 无需手动获取 Cookie
> - 避免 Cookie 过期问题
>
> **账号密码格式：**
> ```
> LAOWANG_ACCOUNT=用户名:密码
> ```
> - 用户名和密码用 `:` 分隔
> - 多账号用 `&` 或换行分隔
>
> **青龙面板注意事项：**
> - 脚本会自动重试失败的请求（最多3次）
> - 国内服务器需要配置代理 `LAOWANG_PROXY`，香港/海外服务器不需要
> - 截图功能默认关闭，如需调试可开启（见下方高级配置）
>
> **Cookie 模式备用：**
> 如果账号密码登录失败，可手动获取 Cookie：
> 1. 浏览器登录老王论坛
> 2. F12 → Network → 任意请求 → Request Headers → 复制 Cookie
> 3. 添加到环境变量 `LAOWANG_COOKIE`
>
> ⚠️ **注意**：老王论坛国内访问需要代理，香港/海外服务器可直接访问

**高级配置（可选）：**
```bash
# DNS 被污染时使用自定义 IP
LAOWANG_CUSTOM_HOST=104.21.x.x  # laowang.vip 的真实 IP

# SSL证书验证（默认开启，遇到证书错误时设为false）
LAOWANG_VERIFY_SSL=true

# 调试模式（开启后显示网络诊断信息）
LAOWANG_DEBUG=true

# 随机延迟（默认开启）
RANDOM_SIGNIN=true
MAX_RANDOM_DELAY=300
```

**完整配置示例（DNS 被污染时）：**
```bash
# 基础配置
LAOWANG_ACCOUNT=用户名:密码
LAOWANG_CUSTOM_HOST=104.21.47.182  # 获取方式：ping laowang.vip
LAOWANG_VERIFY_SSL=false
LAOWANG_DEBUG=true
```

**自动寻找可用 IP：**
如果不知道真实 IP，开启调试模式后脚本会自动尝试多个候选 IP：
```bash
LAOWANG_DEBUG=true
# 脚本会自动测试并提示可用的 IP
```

#### 可选配置

```bash
# 代理（国内需要）
MY_PROXY=http://127.0.0.1:7890

# 随机延迟（避免同时执行）
RANDOM_SIGNIN=true                    # 是否启用随机延迟，默认true
MAX_RANDOM_DELAY=3600                 # 最大随机延迟时间（秒），默认3600秒（1小时）

# 隐私模式
PRIVACY_MODE=true                     # 是否启用隐私保护（脱敏显示账号信息），默认true

# 阿里云盘专用
AUTO_UPDATE_TOKEN=true                # 是否自动更新refresh_token，默认true
SHOW_TOKEN_IN_NOTIFICATION=false      # 通知中是否显示token，默认false

# 推送通知
PUSH_KEY=SCT开头的key              # Server酱
PUSH_PLUS_TOKEN=token            # PushPlus
TG_BOT_TOKEN=token               # Telegram
TG_USER_ID=user_id
DD_BOT_TOKEN=token               # 钉钉
DD_BOT_SECRET=secret
```

### 定时任务配置

在青龙面板 **定时任务** 中创建：

| 任务名称 | 脚本路径 | Cron表达式 | 任务类型 |
|---------|---------|-----------|---------|
| 哔咔签到 | `/ql/scripts/pica_punch.py` | `30 8 * * *` | Python |
| 禁漫签到 | `/ql/scripts/jm_punch.py` | `30 8 * * *` | Python |
| 夸克网盘签到 | `/ql/scripts/quark_punch.py` | `13 8 * * *` | Python |
| 阿里云盘签到 | `/ql/scripts/aliyunpan_checkin.py` | `3 11 * * *` | Python |
| 百度网盘签到 | `/ql/scripts/baiduwangpan_checkin.py` | `0 9 * * *` | Python |
| 天翼云盘签到 | `/ql/scripts/ty_netdisk_checkin.py` | `1 16 * * *` | Python |
| IKUAI签到 | `/ql/scripts/ikuuu_checkin.py` | `0 21 * * *` | Python |
| 老王论坛签到 | `/ql/scripts/laowang_checkin.py` | `0 9 * * *` | Python |

### Cron 表达式参考

```
30 8 * * *     # 每天8:30
0 0 * * *      # 每天0:00
0 9 * * 1-5    # 工作日9:00
0 */4 * * *    # 每4小时
```

## 🔄 多账号配置

脚本支持同时管理多个账号：

```bash
# 方式1：使用 & 分隔（推荐）
PICA_ACCOUNT=user1:pass1&user2:pass2&user3:pass3
JM_ACCOUNT=user1:pass1&user2:pass2&user3:pass3
LAOWANG_ACCOUNT=user1:pass1&user2:pass2

# 方式2：使用换行分隔
PICA_ACCOUNT=user1:pass1
user2:pass2
user3:pass3

# 网盘类Cookie多账号（换行分隔）
COOKIE_QUARK=cookie1
cookie2
cookie3

# 天翼云盘（&分隔）
TY_USERNAME=username1&username2
TY_PASSWORD=password1&password2

# IKUAI（逗号分隔）
IKUUU_EMAIL=user1@example.com,user2@example.com
IKUUU_PASSWD=password1,password2

# 兼容旧格式（单账号）
PICA_USER=user@example.com
PICA_PW=password
JM_USER=username
JM_PW=password
```

脚本会依次对每个账号执行，并汇总结果。

## 📢 推送通知

脚本支持集成多个推送渠道，同时配置时会全部发送：

- **Server酱**：`PUSH_KEY=SCT...`
- **PushPlus**：`PUSH_PLUS_TOKEN=...`  
- **Telegram**：`TG_BOT_TOKEN=...` + `TG_USER_ID=...`
- **钉钉**：`DD_BOT_TOKEN=...` + `DD_BOT_SECRET=...`

## ❓ FAQ

### Q: 如何配置随机延迟？

A: 脚本支持随机延迟执行，避免大量任务同时运行：

```bash
# 启用随机延迟（默认）
RANDOM_SIGNIN=true

# 设置最大延迟时间（秒）
MAX_RANDOM_DELAY=3600  # 1小时内随机延迟
```

启用后，脚本会在 0 到 MAX_RANDOM_DELAY 秒之间随机选择一个延迟时间，显示倒计时后执行。

### Q: 如何获取各种服务的认证信息？

A: 不同平台获取认证信息的方法：

**哔咔漫画（PICA_ACCOUNT）**：
- 访问哔咔漫画官网注册账号
- 格式：`邮箱:密码` 或 `邮箱:密码&邮箱2:密码2`
- 兼容格式：`PICA_USER=邮箱` + `PICA_PW=密码`

**禁漫天堂（JM_ACCOUNT）**：
- 访问禁漫天堂官网注册账号  
- 格式：`用户名:密码` 或 `用户名:密码&用户名2:密码2`
- 兼容格式：`JM_USER=用户名` + `JM_PW=密码`

**夸克网盘（COOKIE_QUARK）**：
- 访问夸克网盘网页版（quark.cn）
- 按F12打开开发者工具 → Application → Cookies
- 复制相关cookie参数，格式：`kps=xxx;sign=xxx;vcode=xxx;user=用户名`
- 多个账号用换行或 `&&` 分隔

**阿里云盘（ALIYUN_REFRESH_TOKEN）**：
- 访问阿里云盘网页版（aliyundrive.com）
- 按F12打开开发者工具 → Application → Local Storage
- 找到token项，复制refresh_token的值
- 多个账号用换行或 `&` 分隔

**百度网盘（BAIDU_COOKIE）**：
- 访问百度网盘网页版（pan.baidu.com）
- 按F12打开开发者工具 → Application → Cookies  
- 复制完整的Cookie值
- 多个账号用换行分隔

**天翼云盘（TY_USERNAME + TY_PASSWORD）**：
- 访问天翼云盘网页版（cloud.189.cn）
- 使用注册的账号密码
- 多个账号用 `&` 分隔：`用户名1&用户名2` 和 `密码1&密码2`

**IKUAI宽带（IKUUU_EMAIL + IKUUU_PASSWD）**：
- 访问IKUAI官网注册账号
- 使用邮箱和密码登录
- 多个账号用逗号分隔：`邮箱1,邮箱2` 和 `密码1,密码2`

**老王论坛（LAOWANG_ACCOUNT）**：
- 访问老王论坛（laowang.vip）注册账号
- **推荐**：使用账号密码格式 `用户名:密码`
- **备用**：从浏览器复制 Cookie 字符串
- 多账号用 `&` 或换行分隔

### Q: 账号登录失败？

A: 
1. 确认账号密码正确
2. 国内用户需要配置代理：`MY_PROXY=http://127.0.0.1:7890`
3. 检查账号是否被锁定
4. 查看青龙面板的任务日志了解具体错误信息

### Q: 老王论坛签到失败？

A:
1. 检查 Cookie 是否失效（Cookie 通常有效期较长，失效后重新获取）
2. 确认 Cookie 格式正确（完整的 Cookie 字符串）
3. 如果提示需要滑块验证，先在网页上手动签到一次后再试
4. 检查网络连接是否正常
5. **如果提示 "Connection refused"，说明网站需要代理才能访问**

### Q: 老王论坛提示 "Connection refused" 或 "连接被拒绝"？

A: 这通常表示网站无法访问，国内服务器需要配置代理。

**解决方法（国内服务器）：**

1. **配置代理：**
```bash
# 方法1：单独配置老王论坛代理
LAOWANG_PROXY=http://127.0.0.1:7890

# 方法2：使用全局代理（所有脚本通用）
MY_PROXY=http://127.0.0.1:7890
```

2. **验证代理是否可用：**
```bash
# 在服务器上测试
curl -x http://127.0.0.1:7890 -I https://laowang.vip
```

3. **常见代理端口参考：**
- Clash: `http://127.0.0.1:7890`
- V2RayN: `http://127.0.0.1:10809`
- SS/SSR: `socks5://127.0.0.1:1080`

**注意**：香港/海外服务器通常可以直接访问，无需代理。

### Q: 如何获取老王论坛 Cookie？

A:

1. **登录论坛：** 用浏览器访问 https://laowang.vip 并登录

2. **打开开发者工具：** 按 F12 → 切换到 **Network（网络）** 标签页

3. **刷新页面：** 按 F5 刷新，找到任意请求（如 `sign` 或 `index`）

4. **复制 Cookie：** 点击请求 → Headers → Request Headers → 复制 Cookie 的值

5. **添加到青龙：** 创建环境变量 `LAOWANG_COOKIE`，粘贴 Cookie 值

> 💡 **提示**：Cookie 通常很长，包含 `__cfduid`、`auth` 等字段，确保完整复制

### Q: 多账号只有一个生效？

A: 检查账号分隔符是否正确：
```bash
# ✅ 正确的新格式
PICA_ACCOUNT=user1:pass1&user2:pass2
JM_ACCOUNT=user1:pass1&user2:pass2
LAOWANG_ACCOUNT=user1:pass1&user2:pass2

# ✅ 正确的换行格式
PICA_ACCOUNT=user1:pass1
user2:pass2

# ❌ 错误（不支持逗号）
PICA_ACCOUNT=user1:pass1,user2:pass2

# 💡 兼容旧格式（单账号）
PICA_USER=user@example.com
PICA_PW=password
```

### Q: 密码中包含特殊字符？

A: 使用换行分隔：
```bash
PICA_ACCOUNT=user1:pass@123
user2:pass&456
```

### Q: DNS 解析错误（DNS 被污染）？

A: 如果看到 `DNS解析: laowang.vip -> 0.0.0.0` 或 `TCP连接失败`，说明 DNS 被污染。

**快速解决 - 使用已验证的 IP：**
```bash
LAOWANG_ACCOUNT=用户名:密码
LAOWANG_CUSTOM_HOST=172.67.158.164  # 或 104.21.14.105, 172.64.35.25
LAOWANG_VERIFY_SSL=false
```

**已验证可用的 IP（2025-02-21）：**
- `172.67.158.164`
- `104.21.14.105`
- `172.64.35.25`

**如果 IP 直连仍然 SSL 错误，建议使用代理：**
```bash
# 使用代理服务器（代理服务器需要能正常解析 DNS）
LAOWANG_ACCOUNT=用户名:密码
LAOWANG_PROXY=http://你的代理服务器:端口
```

**或者修改容器 hosts（不需要代理）：**
```bash
# 进入青龙容器
docker exec -it qinglong bash

# 添加 hosts 解析
echo "172.67.158.164 laowang.vip" >> /etc/hosts

# 测试连接
ping laowang.vip  # 应该显示 172.67.158.164
```

**故障排除：SSL 握手失败**
如果看到 `SSLV3_ALERT_HANDSHAKE_FAILURE` 错误，说明：
1. DNS 被污染 → 使用 `LAOWANG_CUSTOM_HOST` 指定 IP
2. 但 Cloudflare CDN 的 SSL 证书与 IP 不匹配

**解决方案（按推荐顺序）：**
1. **使用代理服务器**（最简单，代理服务器处理 DNS 和 SSL）
2. **修改容器 hosts**（让 DNS 解析到正确 IP，SSL 证书就能匹配）
3. **使用本地 DNS**（在路由器或宿主机上设置正确的 DNS）

**其他解决方法：**

1. **自动寻找可用 IP：**
```bash
LAOWANG_DEBUG=true
# 脚本会自动测试多个候选 IP
```

2. **更换 DNS 服务器：**
```bash
# 修改容器 DNS
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 1.1.1.1" >> /etc/resolv.conf
```

3. **添加 hosts 解析：**
```bash
# 在青龙容器中执行
echo "172.67.158.164 laowang.vip" >> /etc/hosts
```

### Q: SSL/TLS 或 HTTPS 连接错误？

A: 如果遇到 `Max retries exceeded`、`SSL` 或 `HTTPSConnectionPool` 错误：

**解决方法：**

1. **跳过证书验证（快速解决）：**
```bash
LAOWANG_VERIFY_SSL=false
```

2. **开启调试模式查看详情：**
```bash
LAOWANG_DEBUG=true
```

3. **更新系统证书：**
```bash
# Debian/Ubuntu
apt-get update && apt-get install -y ca-certificates

# CentOS/RHEL
yum install -y ca-certificates
```

4. **检查系统时间（SSL证书验证需要正确时间）：**
```bash
date
# 如果时间不对，同步时间
ntpdate -u pool.ntp.org
```

### Q: 执行报错 KeyError？

A: 这通常表示 API 返回的数据结构与脚本预期不符，可能原因：
1. 哔咔/禁漫 API 有更新
2. 账号登录异常（被限流、IP被封禁等）
3. 网络连接问题或代理失效

建议：
- 检查账号是否能正常登录官方网站
- 检查代理是否有效
- 查看完整的任务日志
- 到项目 Issues 页面报告问题

##  更新日志

### v2.4.4 (2025-02-21)
- 🐛 修复 formhash 提取逻辑，支持更多页面格式
- 🔍 添加登录页面调试输出
- ✅ 网络连接问题解决，登录功能正常工作

### v2.4.4 (2025-02-21)
- 🤖 **重新添加浏览器模式**，自动处理滑块验证
- 🔧 支持 `LAOWANG_BROWSER_MODE=true` 启用浏览器
- 📝 三种模式可选：浏览器模式 / HTTP模式 / Cookie模式

### v2.4.3 (2025-02-21)
- 🔒 改进 SSL 禁用方式（使用 NoVerifyHTTPAdapter）
- 📝 添加代理服务器解决方案

### v2.4.2 (2025-02-21)
- 🔧 新增自定义域名解析 (`LAOWANG_CUSTOM_HOST`)
- 🛠️ 解决 DNS 污染导致的连接问题
- 🔍 优化网络诊断功能
- 📝 更新已验证 IP 列表（172.67.158.164, 104.21.14.105, 172.64.35.25）
- 🔒 修复 SSL/TLS 握手失败问题（使用自定义 SSL Adapter）

### v2.4.1 (2025-02-21)
- 🔧 修复 SSL/TLS 连接问题
- 🔍 新增网络诊断功能 (`LAOWANG_DEBUG=true`)
- 🔒 支持跳过证书验证 (`LAOWANG_VERIFY_SSL=false`)
- 📝 更详细的错误提示和解决方案

### v2.4.0 (2025-02-21)
- ✨ 老王论坛签到脚本 v4.0 大更新
- 🔐 **新增账号密码登录模式**，自动获取 Cookie
- 🔄 请求失败自动重试（最多3次）
- 🌐 改进代理支持，修复连接错误
- 📊 更详细的签到统计信息

### v2.3.0 (2025-02-21)
- ✨ 重写老王论坛签到脚本 `laowang_checkin.py`
- 🔧 支持 Cookie / DrissionPage 双模式
- 🤖 浏览器模式自动处理滑块验证
- 📊 改进签到状态检测和统计信息提取
- 📝 更好的错误处理和日志输出

### v2.2.1 (2024-02-XX)
- 🚀 老王论坛改为轻量版（Cookie模式），无需浏览器
- 💾 大幅降低资源占用，适合低配设备
- 📖 更新 Cookie 获取教程

### v2.2.0 (2024-02-XX)
- ✨ 新增老王论坛自动签到脚本
- 🐛 修复多账号分隔符兼容问题
- 📱 优化通知格式

### v2.1.0 (2024-02-XX)
- ✨ 新增夸克网盘签到脚本
- 🔄 完善所有脚本的随机延迟功能
- 📱 优化输出格式和错误处理
- 🔔 统一推送通知格式
- 📚 重构README文档结构
- 🐛 修复环境变量配置说明

### v2.0.0 (2024-01-XX)
- ✨ 新增阿里云盘、百度网盘、天翼云盘、IKUAI签到脚本
- 🔄 为所有脚本添加随机延迟功能
- 📱 优化移动端适配和错误处理
- 🔔 统一推送通知格式
- 📚 重构README文档结构

### v1.0.0 (2024-01-XX)  
- 🎯 初始版本发布
- ✅ 哔咔漫画签到脚本
- ✅ 禁漫天堂签到脚本
- ✅ 青龙面板支持

## 🙏 致谢

感谢以下开源项目和贡献者：

### 🛠️ 核心依赖
- **[青龙面板](https://github.com/whyour/qinglong)** - 强大的定时任务管理平台
- **[JMComic-Python](https://github.com/hect0x7/JMComic-Python)** - 禁漫天堂Python库
- **[ql-script-hub](https://github.com/sansui233/ql-script-hub)** - 丰富的签到脚本合集

### 📚 参考项目
- **[pica-go](https://github.com/niuhuan/pica-go)** - 哔咔漫画API参考
- **[Quark_Auot_CheckIn](https://github.com/Quark_Auot_Check_In)** - 夸克网盘签到脚本
- **[aliyunpan](https://github.com/liupan1890/aliyunpan)** - 阿里云盘相关项目
- **[baiduwp-php](https://github.com/yuantuo666/baiduwp-php)** - 百度网盘相关项目

### 🔔 推送服务
- **Server酱** - 微信推送服务
- **PushPlus** - 多渠道推送平台
- **Telegram Bot API** - Telegram机器人API
- **钉钉机器人** - 企业微信推送

### 👥 贡献者
感谢所有为开源社区贡献代码的开发者们！

### 📄 许可证
本项目采用 [MIT License](LICENSE) 许可证。
