---
title: "工具准备"
description: ""
source_url: "https://redteam-wiki.org/en/tools-list"
created_at: "2025-11-19T18:18:51.995Z"
updated_at: "2025-11-19T18:18:55.660Z"
author: "芙蕾德莉卡"
---
# 工具准备

> **⚠️ 警告：保命须知**
>
> 1. **虚拟机原则：** 本列表中提到的所有工具，**必须且只能**在虚拟机（VMware/VirtualBox）中运行。绝不要在宿主机上安装或运行任何攻防工具。
> 2. **来源警示：** 对于 Cobalt Strike 等商业软件，市面上流传的“破解版”**极大概率含有后门**。请务必保持警惕，我们仅提供官方链接，使用非官方版本后果自负。
> 3. **法律边界：** 所有工具仅限用于授权的红队演习、靶场训练或 CTF 比赛。

### 🏗️ 基础设施与环境 {#️-基础设施与环境}

搭建一个安全、可控的实验环境是红队行动的第一步。

| 工具名称 | 用途 | 官方/项目地址 | 备注 |
| --- | --- | --- | --- |
| **VMware Workstation** | 虚拟机软件 | [官网](https://www.vmware.com/products/workstation-pro.html) | **必备。** 建议使用 Pro 版本以便于网络配置（如仅主机模式）。 |
| **VirtualBox** | 虚拟机软件 | [官网](https://www.virtualbox.org/) | 免费开源的替代方案。 |
| **Commando VM** | Windows 攻击机环境 | [GitHub](https://github.com/mandiant/commando-vm) | Mandiant 出品的脚本，能把纯净的 Windows 变成全功能的攻击机。 |
| **Docker** | 容器服务 | [官网](https://www.docker.com/) | 快速搭建靶场（如 Vulfocus）或隔离运行工具。 |
| **Visual Studio** | C/C++ 开发环境 | [官网](https://visualstudio.microsoft.com/) | **开发 Loader 必备**。建议安装“C++ 桌面开发”组件。 |
| **Python** | 脚本语言环境 | [官网](https://www.python.org/) | 红队脚本（Exp/Poc）最常用的语言。 |

---

### ⚔️ Red Team 实战核心工具箱 {#️-red-team-实战核心工具箱}

这些工具是红队行动中的“主力武器”，涵盖从侦察到控制的全流程。虽然它们已经不适合当前的实战强度，但仍是很好的教学工具。

#### 1. 命令与控制 (C2) {#h-1-命令与控制-c2}

> **注意：** C2 服务端必须运行在 Linux 虚拟机中。

| 工具名称 | 用途 | 官方/项目地址 | 备注 |
| --- | --- | --- | --- |
| **Cobalt Strike** | 商业 C2 框架 | [官网](https://www.cobaltstrike.com/) | **业界标准**。提供强大的 Beacon 和定制化能力。*(注意：请仅在隔离环境研究)* |
| **Metasploit (MSF)** | 漏洞利用框架 | [官网](https://www.metasploit.com/) | **新手入门首选**。拥有海量 Exploit 库，适合漏洞验证。 |
| **Sliver** | 开源 C2 框架 | [GitHub](https://github.com/BishopFox/sliver) | 优秀的开源替代品，支持 Go 语言开发 Implant，免杀效果较好。 |
| **Havoc** | 现代化 C2 | [GitHub](https://github.com/HavocFramework/Havoc) | 界面类似 CS，开源且更新活跃，适合研究学习。 |

#### 2. 信息侦察与资产测绘 {#h-2-信息侦察与资产测绘}

> **原则：** 被动侦察优先，避免直接接触目标。

| 工具名称 | 用途 | 官方/项目地址 | 备注 |
| --- | --- | --- | --- |
| **Nmap** | 端口扫描神器 | [官网](https://nmap.org/) | 主机发现、端口扫描、服务识别。 |
| **Fscan** | 内网综合扫描 | [GitHub](https://github.com/shadow1ng/fscan) | **内网大杀器**。单文件，速度快，支持弱口令爆破和漏洞扫描。 |
| **Ladon** | 大型内网渗透扫描器 | [GitHub](https://github.com/k8gege/Ladon) | 功能极其丰富，支持多种协议扫描和利用。 |
| **Shodan** | 网络空间测绘 | [官网](https://www.shodan.io/) | 搜索暴露在互联网上的设备（被动侦察）。 |
| **Fofa** | 网络空间测绘 | [官网](https://fofa.info/) | 国内常用的资产测绘平台。 |

#### 3. 权限维持与横向移动 {#h-3-权限维持与横向移动}

> **场景：** 获得初始立足点后，扩大战果。

| 工具名称 | 用途 | 官方/项目地址 | 备注 |
| --- | --- | --- | --- |
| **Mimikatz** | 凭证抓取 | [GitHub](https://www.google.com/search?q=https://github.com/gentilkiwi/mimikatz) | **内网之王**。从内存中抓取密码、哈希、票据。 |
| **Impacket** | 协议工具包 | [GitHub](https://github.com/fortra/impacket) | **必备库**。包含 `psexec.py`, `wmiexec.py`, `secretsdump.py` 等横向移动神器的 Python 库。 |
| **BloodHound** | 域分析工具 | [GitHub](https://github.com/SpecterOps/BloodHound) | 图形化展示 AD 域内的攻击路径，寻找最短提权路线。 |
| **Ligolo-ng** | 内网隧道 | [GitHub](https://github.com/nicocha30/ligolo-ng) | 新一代隧道工具，性能优于传统的 Socks 代理，支持 TUN 接口。 |
| **Frp** | 反向代理 | [GitHub](https://github.com/fatedier/frp) | 高性能反向代理应用，常用于内网穿透。 |

#### 4. 免杀与武器化 (Weaponization) {#h-4-免杀与武器化-weaponization}

> **场景：** 让你的 Payload 绕过 AV/EDR。

| 工具名称 | 用途 | 官方/项目地址 | 备注 |
| --- | --- | --- | --- |
| **Donut** | Shellcode 生成器 | [GitHub](https://github.com/TheWover/donut) | 将 EXE/.NET 程序转换为 Shellcode。 |
| **SysWhispers2/3** | 系统调用生成 | [GitHub](https://github.com/jthuraisamy/SysWhispers2) | 生成直接系统调用 (Direct Syscalls) 代码，绕过 EDR 的 API Hook。 |

---

### 🚩 辅助工具 (技能补充) {#辅助工具-技能补充}

虽然 Red Team 更侧重实战，但部分工具在特定场景（如 Web 漏洞挖掘、逆向分析、流量取证）中依然非常有用。

#### 🌐 Web 安全 {#web-安全}

- **Burp Suite:** [官网](https://portswigger.net/burp) - 这里的绝对核心，代理、抓包、重放。
- **SQLMap:** [GitHub](https://github.com/sqlmapproject/sqlmap) - 自动化 SQL 注入工具。
- **Dirsearch:** [GitHub](https://github.com/maurosoria/dirsearch) - 目录爆破工具。
- **Hackbar:** [浏览器插件] - 快速修改 HTTP 请求参数。
- **AntSword (蚁剑):** [GitHub](https://github.com/AntSwordProject/antSword) - 开源 Webshell 管理工具。

#### 💫 逆向与 Pwn {#逆向与-pwn}

- **IDA Pro / Free:** [官网](https://hex-rays.com/ida-free/) - 静态反汇编神器。
- **Ghidra:** [官网](https://ghidra-sre.org/) - NSA 开源的逆向工具，免费且强大。
- **x64dbg:** [官网](https://x64dbg.com/) - Windows 下优秀的动态调试器。
- **Pwntools:** [GitHub](https://github.com/Gallopsled/pwntools) - 编写 Pwn 题 Exp 的 Python 库，实战中也可用于写二进制漏洞利用脚本。

#### 📡 流量与杂项 {#流量与杂项}

- **Wireshark:** [官网](https://www.wireshark.org/) - 流量分析。实战中用于分析异常流量或调试 C2 协议。
- **CyberChef:** [官网](https://gchq.github.io/CyberChef/) - 瑞士军刀般的编解码工具，处理 Base64、Hex 等数据极其方便。

---

### 💡 食用指南 {#食用指南}

1. **按需下载：** 不要试图下载所有工具。根据你当前的任务（是打 Web、是做内网渗透、还是写 Loader）来选择工具。
2. **工具箱化：** 建议在虚拟机中维护一个自己的 `Tools` 目录，将常用工具分类存放（如 `Scan`, `Exploit`, `C2`, `Tunnel`）。
3. **保持更新：** 攻防技术迭代极快，定期去 GitHub 检查工具的更新，关注新的 Issue 和功能。
