#  综合签到脚本集合

多平台自动签到脚本集合，完全支持[青龙面板](https://github.com/whyour/qinglong)，包含漫画、网盘、宽带等多种服务的自动签到。

## 📋 支持平台

- 🎭 **漫画平台**：哔咔漫画、禁漫天堂
- 💾 **网盘平台**：夸克网盘、阿里云盘、百度网盘、天翼云盘
- 🌐 **宽带服务**：IKUAI 宽带签到
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
- ✅ **其他服务**
  - IKUAI 签到（ikuuu_checkin.py）
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

所有脚本都可以独立在青龙面板中运行，支持环境变量配置和推送通知。

## 🚀 快速开始

### 1. 选择需要的脚本

根据您的需求选择对应的签到脚本：

| 需求 | 推荐脚本 | 环境变量 |
|-----|---------|---------|
| 漫画签到 | `pica_punch.py` + `jm_punch.py` | `PICA_ACCOUNT`, `JM_ACCOUNT` |
| 网盘签到 | `quark_punch.py` + `aliyunpan_checkin.py` + `baiduwangpan_checkin.py` + `ty_netdisk_checkin.py` | `COOKIE_QUARK`, `ALIYUN_REFRESH_TOKEN`, `BAIDU_COOKIE`, `TY_USERNAME`+`TY_PASSWORD` |
| 全平台签到 | 全部脚本 | 对应环境变量 |

### 2. 部署到青龙面板

#### 方法一：订阅部署（推荐）

在青龙面板 **订阅管理** 中添加：

```
https://github.com/你的账号/ComicsPuncher.git
```

#### 方法二：手动上传

下载需要的脚本文件，上传到青龙面板 `/ql/scripts/` 目录。

### 3. 配置环境变量

在青龙面板 **环境变量** 中添加相应配置（见下文详细配置）。

### 4. 创建定时任务

为每个脚本创建对应的定时任务（见下文定时任务配置）。

### 2. 配置环境变量

在青龙面板 **环境变量** 中添加：

#### 哔咔漫画

```
# 推荐：多账号格式（用 & 或换行分隔）
PICA_ACCOUNT=user1@example.com:pass1&user2@example.com:pass2

# 或单账号
PICA_ACCOUNT=user@example.com:password

# 兼容：旧格式（单账号）
PICA_USER=user@example.com
PICA_PW=password
```

#### 禁漫天堂

```
# 推荐：多账号格式（用 & 或换行分隔）
JM_ACCOUNT=user1:pass1&user2:pass2

# 或单账号
JM_ACCOUNT=username:password

# 兼容：旧格式（单账号）
JM_USER=username
JM_PW=password
```

#### 夸克网盘

```
# Cookie格式（从浏览器开发者工具获取）
COOKIE_QUARK=kps=xxx;sign=xxx;vcode=xxx;user=用户名

# 多账号（用换行分隔）
COOKIE_QUARK=cookie1
cookie2
```

#### 阿里云盘

```
# 单账号（refresh_token）
ALIYUN_REFRESH_TOKEN=your_refresh_token

# 多账号（用换行或 & 分隔）
ALIYUN_REFRESH_TOKEN=token1
token2
token3
```

#### 百度网盘

```
# Cookie格式
BAIDU_COOKIE=your_baidu_cookie

# 多账号（用换行分隔）
BAIDU_COOKIE=cookie1
cookie2
```

#### 天翼云盘

```
# 账号密码格式
TY_USERNAME=username1&username2
TY_PASSWORD=password1&password2

# 或单账号
TY_USERNAME=username
TY_PASSWORD=password
```

#### IKUAI 宽带

```
# 邮箱密码格式
IKUUU_EMAIL=user1@example.com,user2@example.com
IKUUU_PASSWD=password1,password2

# 或单账号
IKUUU_EMAIL=user@example.com
IKUUU_PASSWD=password
```

#### 可选配置

```
# 代理（国内需要）
MY_PROXY=http://127.0.0.1:7890

# 随机延迟（避免同时执行）
RANDOM_SIGNIN=true                    # 是否启用随机延迟，默认true
MAX_RANDOM_DELAY=3600                 # 最大随机延迟时间（秒），默认3600秒（1小时）

# 推送通知
PUSH_KEY=SCT开头的key              # Server酱
PUSH_PLUS_TOKEN=token            # PushPlus
TG_BOT_TOKEN=token               # Telegram
TG_USER_ID=user_id
DD_BOT_TOKEN=token               # 钉钉
DD_BOT_SECRET=secret
```

```
# Cookie格式
IKUUU_COOKIE=your_ikuuu_cookie
```

#### 可选配置

```
# 代理（国内需要）
MY_PROXY=http://127.0.0.1:7890

# 随机延迟（避免同时执行）
RANDOM_SIGNIN=true                    # 是否启用随机延迟，默认true
MAX_RANDOM_DELAY=3600                 # 最大随机延迟时间（秒），默认3600秒（1小时）

# 推送通知
PUSH_KEY=SCT开头的key              # Server酱
PUSH_PLUS_TOKEN=token            # PushPlus
TG_BOT_TOKEN=token               # Telegram
TG_USER_ID=user_id
DD_BOT_TOKEN=token               # 钉钉
DD_BOT_SECRET=secret
```

### 3. 创建定时任务

在青龙面板 **定时任务** 中创建：

**哔咔签到：**

| 字段 | 值 |
|-----|-----|
| 任务名称 | 哔咔签到 |
| 脚本路径 | `/ql/scripts/pica_punch.py` |
| Cron表达式 | `30 8 * * *` |
| 任务类型 | Python |

**禁漫签到：**

| 字段 | 值 |
|-----|-----|
| 任务名称 | 禁漫签到 |
| 脚本路径 | `/ql/scripts/jm_punch.py` |
| Cron表达式 | `30 8 * * *` |
| 任务类型 | Python |

**夸克网盘签到：**

| 字段 | 值 |
|-----|-----|
| 任务名称 | 夸克网盘签到 |
| 脚本路径 | `/ql/scripts/quark_punch.py` |
| Cron表达式 | `0 9 * * *` |
| 任务类型 | Python |

**阿里云盘签到：**

| 字段 | 值 |
|-----|-----|
| 任务名称 | 阿里云盘签到 |
| 脚本路径 | `/ql/scripts/aliyunpan_checkin.py` |
| Cron表达式 | `3 11 * * *` |
| 任务类型 | Python |

**百度网盘签到：**

| 字段 | 值 |
|-----|-----|
| 任务名称 | 百度网盘签到 |
| 脚本路径 | `/ql/scripts/baiduwangpan_checkin.py` |
| Cron表达式 | `0 9 * * *` |
| 任务类型 | Python |

**天翼云盘签到：**

| 字段 | 值 |
|-----|-----|
| 任务名称 | 天翼云盘签到 |
| 脚本路径 | `/ql/scripts/ty_netdisk_checkin.py` |
| Cron表达式 | `30 8 * * *` |
| 任务类型 | Python |

**IKUAI签到：**

| 字段 | 值 |
|-----|-----|
| 任务名称 | IKUAI签到 |
| 脚本路径 | `/ql/scripts/ikuuu_checkin.py` |
| Cron表达式 | `0 8 * * *` |
| 任务类型 | Python |

## 📝 Cron 表达式

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

# 方式2：使用换行分隔
PICA_ACCOUNT=user1:pass1
user2:pass2
user3:pass3

# 兼容：单账号旧格式
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
- 多个账号用换行分隔

**阿里云盘（ALIYUN_REFRESH_TOKEN）**：
- 访问阿里云盘网页版（aliyundrive.com）
- 按F12打开开发者工具 → Application → Local Storage
- 找到token项，复制refresh_token的值
- 多个账号用换行分隔

**百度网盘（BAIDU_COOKIE）**：
- 访问百度网盘网页版（pan.baidu.com）
- 按F12打开开发者工具 → Application → Cookies  
- 复制BDUSS等关键cookie参数
- 多个账号用换行分隔

**天翼云盘（TY_USERNAME + TY_PASSWORD）**：
- 访问天翼云盘网页版（cloud.189.cn）
- 使用注册的账号密码
- 多个账号用 & 分隔：`用户名1&用户名2` 和 `密码1&密码2`

**IKUAI宽带（IKUUU_EMAIL + IKUUI_PASSWD）**：
- 访问IKUAI官网注册账号
- 使用邮箱和密码登录
- 多个账号用逗号分隔：`邮箱1,邮箱2` 和 `密码1,密码2`

### Q: 账号登录失败？

A: 
1. 确认账号密码正确
2. 国内用户需要配置代理：`MY_PROXY=http://127.0.0.1:7890`
3. 检查账号是否被锁定
4. 查看青龙面板的任务日志了解具体错误信息

### Q: 多账号只有一个生效？

A: 检查账号分隔符是否正确：
```bash
# ✅ 正确的新格式
PICA_ACCOUNT=user1:pass1&user2:pass2
JM_ACCOUNT=user1:pass1&user2:pass2

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
- **[Quark_Auot_Check_In](https://github.com/Quark_Auot_Check_In)** - 夸克网盘签到脚本
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
