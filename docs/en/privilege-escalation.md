---
title: "权限提升 - 从小兵到女王"
description: ""
source_url: "https://redteam-wiki.org/en/privilege-escalation"
created_at: "2025-11-27T14:47:34.880Z"
updated_at: "2025-11-27T16:09:24.145Z"
author: "芙蕾德莉卡"
---
# 权限提升 - 从小兵到女王

本章节建议搭配芙蕾德莉卡的pdf讲解视频观看： [https://www.bilibili.com/video/BV1DverzuEzL](https://www.bilibili.com/video/BV1DverzuEzL)<br> 涉及的pdf如下：<br> [https://github.com/tyranid/windows-logical-eop-workshop/releases/download/44CON-2017/Introduction.to.Logical.Privilege.Escalation.on.Windows.pdf](https://github.com/tyranid/windows-logical-eop-workshop/releases/download/44CON-2017/Introduction.to.Logical.Privilege.Escalation.on.Windows.pdf)

## 1. 引言：Hard Mode 开启 {#h-1-引言hard-mode-开启}

在上一章《Bypass UAC》中，我们的生活很美好：我们本来就在 **Administrators** 组里，只需要用一点小手段绕过弹窗，就能获得至高无上的权力。

但在现实的红队行动中，**90% 的情况**是你通过钓鱼邮件，横向移动或 Web 漏洞拿到的 Shell，只是一个**卑微的普通用户/域用户**（比如 `User` 或 `IIS AppPool`）。

这时候，你再用 UACME 是没用的，因为你的“身份证”上根本就没有“管理员”这三个字。你不需要“解锁”，你需要的是**篡位**。

这一章，我们将探讨如何从**普通用户 (Pawn)** 逆袭成为 **SYSTEM (Queen)**。我们将跟随 Windows 提权大师 **James Forshaw** 的思路，学习一种不需要写汇编代码的高级艺术——**逻辑提权**。

---

## 2. 暴力破解 vs. 逻辑欺骗 {#h-2-暴力破解-vs-逻辑欺骗}

想要获得更高的权限，通常有两条路：

- **路子正（内存破坏）：** 寻找 Windows 内核的缓冲区溢出漏洞（Kernel Exploit）。这就像是拿着大锤去砸宫殿的墙，进行正面猛攻。但现在微软把墙修得越来越厚（SMEP, ASLR, KVA），这条路越来越难走，而且容易把系统搞蓝屏。
- **路子巧（逻辑漏洞）：** 这是 James Forshaw 提倡的方法。**我们不砸墙，我们骗保安。**
    - 逻辑提权的本质是：**利用系统原本合法的“规则”，组合出程序员意想不到的“后果”。**

---

## 3. 知己知彼：宫殿的规则 (Windows Internals) {#h-3-知己知彼宫殿的规则-windows-internals}

要骗过保安，你得先懂宫殿的规矩。在 Windows 里，权限控制主要看三个东西：

### 1️⃣ 你的工牌：Token (访问令牌) {#h-1️⃣-你的工牌token-访问令牌}

每个进程都有一个 Token。它决定了你是谁。

- **普通用户 Token：** 只能访问自己的桌面和文档。
- **SYSTEM Token：** 拥有整个操作系统的生杀大权。

> **提权的目标：** 偷到一个 SYSTEM 的 Token，贴在自己脑门上。

### 2️⃣ 门禁名单：DACL (访问控制列表) {#h-2️⃣-门禁名单dacl-访问控制列表}

每个文件和服务都有一张名单。

- 通常，`C:\Windows\System32` 的名单上写着：`Administrator: Full Control`，`User: Read Only`。
- 这就是为什么你无法替换系统文件的原因。

### 3️⃣ 女皇的替身：Impersonation (模拟) {#h-3️⃣-女皇的替身impersonation-模拟}

这是 Windows 最容易被利用的机制。

- **原理：** 系统服务（SYSTEM 权限）经常需要帮用户办事。为了安全，服务会暂时**“模拟”**成那个用户的权限去办事。
- **漏洞：** 如果我们能诱骗一个 SYSTEM 服务来连接我们（比如通过命名管道 Named Pipe），并且它**忘记**了降级（或者我们可以利用某种技巧捕获它的凭证），我们就能把它的 Token 偷过来！

---

## 4. 寻找猎物：攻击面枚举 (Hunting) {#h-4-寻找猎物攻击面枚举-hunting}

作为一个小兵，我们要在系统里四处游荡，寻找那些**配置错误**或**逻辑不严谨**的角落。

### 1️⃣ 寻找“忘了锁的门” (Weak Permissions) {#h-1️⃣-寻找忘了锁的门-weak-permissions}

有些软件安装时很粗心，把安装目录设为了 `Everyone: Full Control`。

- **实战：** 如果你发现一个以 SYSTEM 权限运行的杀毒软件，它的服务主程序竟然允许你**修改**。
- **操作：** 把你的木马改名为该杀毒软件的名字，重启服务。
- **结果：** 系统自动以 SYSTEM 权限启动了你的木马。

### 2️⃣ 寻找“傻瓜服务” (Unquoted Service Path) {#h-2️⃣-寻找傻瓜服务-unquoted-service-path}

- **原理：** Windows 解析路径的逻辑缺陷。
    - 路径：`C:\Program Files\My App\service.exe`
    - 如果路径没加引号，系统会按顺序尝试运行：
        1. `C:\Program.exe` ❌
        2. `C:\Program Files\My.exe` ❌
        3. `C:\Program Files\My App\service.exe` ✅
- **利用：** 如果你有权限在 C 盘根目录写文件，你就放一个恶意的 `Program.exe`。下次服务重启时，它就会错误地执行你的程序！

### 3️⃣ 寻找“热心肠的仆人” (Potato Attacks / Named Pipes) {#h-3️⃣-寻找热心肠的仆人-potato-attacks-named-pipes}

这是基于 James Forshaw 理论最经典的实战应用（如 JuicyPotato, PrintNightmare）。

- **剧本：**
    1. **设局：** 我们创建一个恶意的 COM 对象或 RPC 服务器（想象成一个虚假的求助站）。
    2. **诱骗：** 我们强行触发一个高权限的 SYSTEM 服务（如 DCOM 服务），让它来访问我们的求助站。
    3. **窃取：** 当 SYSTEM 服务连接我们时，它会携带它的身份凭证（Token）。
    4. **伪装：** 我们利用 Windows 的 API（`ImpersonateNamedPipeClient`），直接把这个 SYSTEM Token 拿过来，变成了我们自己的。

---

## 5. 逻辑漏洞的高级艺术：符号链接 (Symlinks) {#h-5-逻辑漏洞的高级艺术符号链接-symlinks}

James Forshaw 最擅长的领域。这是一种**隔山打牛**的战术。

**场景：**<br> 有一个系统服务，任务是定期清理 `C:\Temp\log.txt`。它是 SYSTEM 权限。

**攻击逻辑：**

1. **观察：** 我们发现这个服务在删除文件前，没有严格检查文件是不是真的日志。
2. **偷梁换柱：** 我们删掉 `log.txt`，并在原地建立一个**符号链接 (Mount Point / Junction)**，指向 `C:\Windows\System32\drivers\pci.sys`（关键驱动文件）。
3. **借刀杀人：** 服务再次运行时，它以为自己在删日志，实际上顺着我们的链接，把系统的关键驱动删了！
4. **提权：** 同样的逻辑，如果服务是**写文件**，我们就能让它帮我们把恶意 DLL 写入 System32 目录。

> **核心思想：** 我没有权限写系统目录，但我可以把一个“我有权写的地方”变成“通往系统目录的虫洞”。

---

## 6. 实战兵器：从手工到自动化 {#h-6-实战兵器从手工到自动化}

理解了原理，实战中我们通常使用封装好的工具。

- **PowerUp (PowerShell):** 经典的枚举工具。
    - `Invoke-AllChecks`：自动帮你扫描有没有“没加引号的服务路径”、“权限错误的注册表键值”等。
- **Potato Family (土豆家族):**
    - `JuicyPotato` / `RottenPotato` / `SweetPotato`：专门利用 COM/RPC 机制骗取 SYSTEM Token 的神器。
- **PrintNightmare / SpoolSample:** 利用打印机服务（Spooler）的逻辑漏洞，强制让域控制器或者本机回连我们，从而窃取凭证。

---

## 7. 总结：核心思维方式 {#h-7-总结核心思维方式}

从 Bypass UAC 到 Privilege Escalation，你会发现利用思维的转变：

- **Bypass UAC** 是在想：**“我是没带钥匙的老板，怎么让保安别管我？”**
- **Privilege Escalation** 是在想：**“我只是个扫地的，但我怎么诱骗老板把金库钥匙落在我这里？”**

逻辑提权不需要你对抗昂贵的杀毒软件内存防御，你需要对抗的是**程序员的逻辑疏忽**。只要系统里还存在“服务帮用户办事”的逻辑，这种提权路径就永远存在。
