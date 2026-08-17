---
title: "Nday利用 - 框架，组件，和应用"
description: ""
source_url: "https://redteam-wiki.org/en/basic-nday"
created_at: "2025-12-27T14:18:04.129Z"
updated_at: "2025-12-27T15:05:20.994Z"
author: "bunny"
---
# Nday利用 - 框架，组件，和应用

### 极低成本的攻击 {#极低成本的攻击}

谈起一次成功的红队行动或者黑客攻击，大多数人的第一反应是训练有素的专业人士利用极其先进的攻击手段/极其新颖的漏洞和精心策划与潜伏，发起的一次成本高昂的行动。但是实际情况很可能只是——惨遭加班过度的管理员忘记查阅某个软件包的安全公告，因此没有及时给某个已被公开的漏洞安装补丁。<br> 在真实场景中，这种情况并不少见，甚至不乏某些知名企业也因此遭受了惨重的实际损失。所谓的Nday利用，正是使用目前已经公开发布的漏洞发起攻击。<br> Nday是区别于0day和1day的概念。<br> 首先，在了解了前面的基础Web漏洞之后，不难理解0day漏洞的概念：某个漏洞被某个黑客发现，并且该黑客不公开/不上报漏洞，外界并不知道这个漏洞的存在，因此软件开发者也无法为该漏洞制作补丁。这种情况下的攻击称之为0day攻击（在野利用），难以防御。<br> 1day漏洞则是漏洞已经遭到披露，可能是被漏洞发现者上报或者由于在野利用过程中被捕获（因此，使用0day是一项有风险的行为，因为有概率被捕获漏洞细节），但是软件开发者还没有为此制作补丁。<br> Nday漏洞则是漏洞已经公开，且已有补丁，因此绝大部分Nday在真实环境都已被修复。但是由于现代软件纷繁复杂的架构，漏网之鱼并不鲜见。一旦我们发现了目标组织存在某个Nday漏洞，利用Nday发起攻击几乎没有成本——不需要处心积虑收集人员信息来钓鱼，也不需要使用成本高昂且珍贵的0day漏洞，大部分情况下只需要复制粘贴现有的exp（漏洞利用代码）即可。

> 补充：<br> exp（漏洞利用代码）：利用漏洞获取权限或实现某些目的的代码。<br> poc（概念验证代码）：与exp相对，它往往是漏洞验证阶段被临时编写出来的，一般仅仅只是能验证漏洞的存在，利用过程可能不稳定，或者只能实现受限功能（例如只能在有漏洞的机器上弹出计算器）<br> payload（载荷）：被发送出去的那部分数据。exp和poc可以理解为导弹发射台，负责根据需求组建完整的payload并有效投送，payload则是导弹本身。<br> CVE：一个站点，归档并索引了目前互联网上公开的各种漏洞并赋予编号。

---

在较大的组织中，安全管理是一项浩瀚的工程。试想一下，你是一家金融公司的IT负责人，公司在每个地区的分公司都有大量的各种部门，每个部门都有自己需要的数字化系统，每个系统都引入了不同的软件包和组件……这基本上是一场噩梦。

这样，我们就很容易理解某些Nday从何而来了。

举个实际例子：小白正在编写一个JavaWeb站点，他使用目前主流的技术栈，但是为了匹配网上的资料，他在pom.xml（Java项目配置文件，第三方依赖组件等索引就存储在其中）中引入的许多组件实际上并不是安全的版本。<br> 小白引入了某个json处理库组件，能够方便的转换json请求和java对象，而这个json库只是他项目中几十个组件中的一个不起眼的角落。<br> 该站点部署后，小黑通过Burpsuite的插件扫描到了这个有漏洞版本的组件，构造特定的payload进行攻击，获取了小白站点的管理员权限。

另一个例子：某所高校需要开发自己的子域名站点，用于教学质量评估，但是负责该项目的外包公司人手有限，于是选择了某个php框架来进行快速开发（例如Laravel，Yii，TP等，都是很知名的框架，可以极大提高开发效率）。但是站点上线之后很长时间没有维护，由于该框架被挖出某个RCE漏洞，校方信息化部门对此不知情，也就并没有更新补丁，最终该漏洞被恶意攻击者利用，造成内网沦陷。

还有一个例子：更加直接的例子是，目前互联网上还有大量使用CMS（内容管理系统）直接部署的站点，CMS是可以直接部署在服务器上的现成代码，例如Wordpress等。一旦CMS直接被爆出存在漏洞，那么使用该CMS的站点就全部暴露在被攻击的风险之中。

很多时候Nday就是类似这样的场景。

### ScriptKid的自我修养 {#scriptkid的自我修养}

很显然，光是了解漏洞从何而来，而不知如何利用，是不够的。<br> 由于本wiki仅分享知识的基本宗旨，本页面不会提供可在真实场景直接使用的代码。但是，这不妨碍引用一些在互联网上知名的公开站点的资料。其中有些资料甚至被集成在Kali Linux之类的渗透发行版之中。<br> 最知名的站点当属github了。有时候找到某个系统疑似是旧版，于是使用Google搜索XX系统XX版本漏洞，或者搜索CVE编号，就能找到热心网友发布在github上的exp。<br> 其次是exploit-db，它同时也作为searchsploit工具被集成在Kali Linux中。可以方便地搜索漏洞信息。<br> 然后是各种集成工具，例如MetasploitFramework（MSF），其内置了大量exp。github也能找到许多针对特定场景的利用工具，实际上也是exp集合，例如针对部分常见OA系统等专门渗透场景的工具。


## 如何编写批量web漏洞POC模板 {#如何编写批量web漏洞POC模板}

于上述章节中我们了解了什么是Nday，由此可见Nday因其时效性与危害性，使其在实际攻防与安全运营工作中通常作为作为重点排查项，近几年由于AI挖洞产出的效率直线上涨，监管单位组织的相关战役如“一高一弱”等频率也越来越高，那这就间接督促相关安全（运维/运营/辖区监管/企业安全部）从业者拿到1day或Nday的情报（如请求包、源码中的漏洞点位）后，通常需要第一时间自己挖掘对应漏洞并编写批量扫描POC，对工作范围内资产快速排查隐患。

早些年时候写poc大部分都是用py或者go，通常根据自己习惯提前写好一个相对通用的请求模板，然后再根据漏洞请求逐一修改模板，后续由于出现了像 `Nuclei` 这种快速标准化漏洞验证工具，此类工具仅需要提供流式的请求与条件匹配即可，此时编写web漏洞模板不需要再考虑代码的实现部分。由于每个漏洞模板都是yaml文件，因此也就间接使得漏洞管理更标准化，那后续出现的像 [`Faraday`](https://github.com/infobyte/faraday) 等漏洞资产管理平台通常都内部集成或支持外接 `nuclei`。

*注1：极个别情况下还是需要编写使用脚本，如vite的cve其中一个lfi变种需要用不被url编码情况下的 `../../` 就需要用到py的 `io.socket` 来发包，因为nuclei会自动编码掉。*

*注2：faraday平台集成的nuclei版本较老，在很长一段时间只支持老版本nuclei语法，编写时候需要注意*

### 挑选合适的扫描工具 {#挑选合适的扫描工具}

在编写扫描批量POC模板前要先选择一款适合自己的扫描工具，这里简单列举了几款常用工具：

1.[Nuclei](https://github.com/projectdiscovery/nuclei)

模板采用 `YAML` 格式，`Nuclei` 自始至终都是占比最高的一款漏洞模板扫描工具，由 [projectdiscovery](https://projectdiscovery.io/) 开发维护，不论是模板兼容性还是提供的函数都相对丰富，如今顺应时代提供了[web与ai协助编写模板](https://cloud.projectdiscovery.io/)，大幅提升了产出效率，**要注意**由于其使用 `httpx` 做资产存活检测，在导入扫描资产时个人建议提供写明 `http/https`协议头（如：`https://localhost.com`），尽量避免直接使用 `localhost.com:8443` 省去其识别协议的时间。

2.[XPOC](https://github.com/chaitin/xpoc)

模板采用 `YAML` 格式，由长亭的 `CT stack` 团队开发维护，是从xray项目拆出来的，可惜的是 `XPOC` 已经很久没有更新了，且 `0.1.0` 在实际体验中存在一定问题（个人还是推荐 `0.0.8` 版本），还会再某些特定包含特殊转义符号的body时导致模板格式问题，但由于该工具较早的提供了[web端模板编辑器](https://poc.xray.cool/) 一定程度上提升了POC模板的编写效率，以及也提供了相对规整的 [模板函数](https://docs.xray.cool/plugins/yaml/YAMLTypeFunc) and老版本的XPOC扫描存活资产效率较高，再一个支持html的报告导出，所以这里还是推荐编写简易模板时学习使用。

### 编写自己的第一个POC扫描模板 {#编写自己的第一个POC扫描模板}

此前我们在编写复杂模板时需要翻阅[nuclei模板文档](https://docs.projectdiscovery.io/templates/introduction)，但如今Nuclei项目方接入了ai辅助，使得当前模板编写变得非常容易，仅需要登录 [`https://cloud.projectdiscovery.io/`](https://cloud.projectdiscovery.io/) ，把自己每一步的请求包与要匹配的特征字段告知ai，接下来仅需微调即可，比如下面这个是我构建的一个LFI请求包。

```http
POST /test-api/file/queryfile?filename=etc/password HTTP/1.1
Host: localhost:8000
User-Agent: curl/8.19.0
Accept: */*
Content-Type: application/json
Content-Length: 32
Connection: keep-alive

{"dirname":"../../../../../../"}
```

在web端和ai对话如下

```
帮我编写模板，我的请求时POST /test-api/file/queryfile?filename=etc/password HTTP/1.1 Host: localhost:8000 User-Agent: curl/8.19.0 Accept: */* Content-Type: application/json Content-Length: 32 Connection: keep-alive {"dirname":"../../../../../../"}，预期符合漏洞匹配的返回为passwd内容
```

其返回模板如下

```yaml
id: directory-traversal-queryfile

info:
  name: Directory Traversal via Query File
  author: ProjectDiscoveryAI
  severity: high
  description: |
    This template checks for a directory traversal vulnerability in the `/test-api/file/queryfile` endpoint, where a crafted `dirname` parameter can lead to leakage of sensitive files such as `/etc/passwd`.
  tags: directory-traversal

http:
  - raw:
      - |
        POST /test-api/file/queryfile?filename=etc/passwd HTTP/1.1
        Host: {{Hostname}}
        User-Agent: curl/8.19.0
        Accept: */*
        Content-Type: application/json
        Content-Length: 32
        Connection: keep-alive

        {"dirname":"../../../../../../"}

    matchers-condition: and
    matchers:
      - type: word
        words:
          - "root:x:0:0:" # Typical content in /etc/passwd for root user
          - "/bin/bash" # Typical shell entry in /etc/passwd files
      - type: status
        status:
          - 200
```

相信大部分其实没有文档也能看懂，当然还是建议自己多动手改改，因为ai也有概率抽风。
