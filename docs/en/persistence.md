---
title: "持久化 - 稳固你的战利品"
description: ""
source_url: "https://redteam-wiki.org/en/persistence"
created_at: "2025-11-27T15:18:03.528Z"
updated_at: "2025-11-27T15:21:35.112Z"
author: "芙蕾德莉卡"
---
# 持久化 - 稳固你的战利品

在上一章，通过 LPE（提权），我们已经拿到了金库的最高管理权（SYSTEM 权限）。现在，我们面临一个新的挑战：

> **所有的攻击都是暂时的。**

如果管理员重启了服务器，或者随手关掉了我们的程序，之前的努力就全部白费了。我们必须重头再来——这在实战中是不可接受的。

**“持久化 (Persistence)”**，就像是在游戏里“存档”。我们的目标是：**无论系统重启多少次，无论管理员做什么，我们的后门都能自动、隐蔽地复活。**

我们将通过四个等级，教你如何把你的“恶意代码”植入 Windows 的每一个角落。

---

### 第一层： “把名字写在开机清单上” {#第一层-把名字写在开机清单上}

*原理简单，但也最容易被杀毒软件发现。*

Windows 系统启动时，会按照一张“清单”逐个运行程序（比如你的微信、QQ自动启动）。黑客最直观的做法，就是把自己的马（Backdoor）加到这张清单里。

#### 1. 📝 注册表自启动 (Registry Run Keys) {#h-1-注册表自启动-registry-run-keys}

这是最经典的手段。Windows 注册表里有几个特定的位置（键值），专门用来存放开机启动项。

- **位置：** `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run`
- **操作：** 只要在这里添加一行，写上我们木马的路径（例如 `C:\temp\backdoor.exe`），下次开机它就会自动运行。
- **缺点：** 太招摇了。几乎所有的杀毒软件（AV）和运维工具（如 360、火绒）都会死死盯着这里。

#### 2. 📂 启动文件夹 {#h-2-启动文件夹}

这就更简单了，直接把木马的快捷方式扔进 `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp` 文件夹里。效果一样，也很容易被发现。（不过，某个常见的杀毒软件竟然不检测特定的后缀名！！）

当然还有用户自己的启动目录，它甚至不要管理员权限就可以写入 `C:\Users\username\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`

---

### 第二层：“伪装成系统的勤杂工” {#第二层伪装成系统的勤杂工}

*利用系统自带的合法功能，混淆视听。*

#### 1. ⏰ 计划任务 (Scheduled Tasks) {#h-1-计划任务-scheduled-tasks}

Windows 有一个“闹钟”功能，叫**任务计划程序 (Task Scheduler)**。它原本是用来定时更新系统或清理垃圾的。

- **简单的思路：** 我们可以创建一个任务，设定为**每当用户登录时**或**每隔30分钟**，就偷偷运行我们的脚本。
- **隐蔽性：** 我们可以把任务起名为 `GoogleUpdate` 或 `WindowsSystemCheck`，看起来人畜无害，很难引起管理员的怀疑。

#### 2. ⚙️ 系统服务 (Services) {#h-2-️-系统服务-services}

服务是 Windows 的核心组件，它们在后台默默运行，甚至不需要用户登录。

- **简单的思路：**
    - **新建服务：** 创建一个叫 `Windows Health Monitor` 的假服务，实际上运行的是后门。
    - **服务劫持：** 找到一个合法的服务，修改它的配置，让它启动时顺便加载我们的恶意 DLL。
- **优势：** 权限极高（通常是 SYSTEM 权限），且很难被手动关闭。

---

### 第三层：“劫持系统的守门人” {#第三层劫持系统的守门人}

*修改系统核心流程，让系统主动帮我们运行。*

#### 1. Winlogon 登录劫持 {#h-1-winlogon-登录劫持}

`Winlogon.exe` 是负责管理用户登录过程的关键进程。当你在输入密码时，它就在工作。

- **原理：** 注册表中有一个 `Userinit` 键值，它规定了用户登录后要运行什么程序（通常是 `userinit.exe`）。
- **手法：** 我们在后面加个“尾巴”。把键值改为 `userinit.exe, C:\hacker\backdoor.exe`。
- **效果：** 每次用户输入密码进入桌面之前，系统都会先贴心地帮我们把后门打开。

#### 2. DLL 劫持 (DLL Hijacking) {#h-2-dll-劫持-dll-hijacking}

这是利用了 Windows 的“懒惰”。当一个程序（比如 `notepad.exe`）需要用一个功能库（DLL）时，它会按照顺序去几个目录里找。

- **手法：** 假设程序需要 `version.dll`。我们自己写一个恶意的 `version.dll`，放在程序运行的目录下。程序一启动，发现旁边就有个 `version.dll`，看都不看就直接加载了——**Bingo，代码执行。**
- **应用：** 这种方法非常隐蔽，属于“借尸还魂”，不过需要转发dll的函数，防止程序的正常功能受到影响。

#### 3. COM 劫持 {#h-3-com-劫持}

Windows 里的很多软件组件（COM对象）是通过注册表里的 ID (CLSID) 来索引的。

- **手法：** 我们修改注册表，把某个常用组件（比如打开文件时会用到的组件）的路径，替换成我们的恶意文件路径。当用户只是简单地浏览文件夹时，后门就触发了。

---

### 第四层：“无文件攻击与隐形陷阱” {#第四层无文件攻击与隐形陷阱}

*不在硬盘上留下痕迹，或者深埋于系统底层。*

#### 1. 👻 WMI (Windows Management Instrumentation) {#h-1-wmi-windows-management-instrumentation}

这是目前红队最喜欢的**无文件攻击**手段之一。WMI 是 Windows 强大的管理框架。

- **原理：** WMI 允许我们设置**事件订阅 (Event Subscription)**。这就像埋设地雷：我们可以设定“当系统启动 2 分钟后”或者“当某个文件被创建时”，触发一段 PowerShell 代码。
- **优势：** **没有文件落地！** 恶意代码直接存储在 WMI 数据库里，硬盘上找不到 `.exe` 文件，传统的杀毒软件很难查杀。

#### 2. ☠️ Bootkit (MBR 后门) {#h-2-️-bootkit-mbr-后门}

这是终极的大招，但现在很难见到了。不过，最近又出现了一些巧妙的APT野外利用，值得学习 [https://www.kaspersky.com.cn/about/press-releases/more-elusive-and-more-persistent](https://www.kaspersky.com.cn/about/press-releases/more-elusive-and-more-persistent)

- **原理：** 修改硬盘的**主引导记录 (MBR)**。
- **效果：** 你的病毒运行得**比操作系统还要早**。当 Windows 还在加载 Logo 的时候，病毒已经控制了电脑。不过，随着 UEFI 安全启动的普及，这种古老的魔法正在失效。

---

### 🛡️ 防御者视角：如何把这些客人赶走？ {#️-防御者视角如何把这些客人赶走}

作为防御者，他们如何检测我们的行动？

1. **使用神器 Autoruns：** 微软官方工具 Sysinternals Suite 中的 `Autoruns` 是检测持久化的神器。它可以扫描上述提到的**几乎所有**启动位置（注册表、服务、计划任务、DLL劫持点等）。
2. **监控进程父子关系：** 正常的 `svchost.exe` 是由 `services.exe` 启动的。如果你发现一个 `powershell.exe` 突然启动了一个不明程序，那通常有问题。
3. **定期排查计划任务和 WMI：** 不要只看启动文件夹，那里通常是空的。定期的深度扫描才是关键。
