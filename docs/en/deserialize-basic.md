---
title: "反序列化 - 现代进攻技术"
description: ""
source_url: "https://redteam-wiki.org/en/deserialize-basic"
created_at: "2025-12-21T14:46:18.899Z"
updated_at: "2025-12-21T16:00:32.911Z"
author: "bunny"
---
# 反序列化 - 现代进攻技术

## 它是如何诞生的 {#它是如何诞生的}

反序列化（unserialize/deserialize），是序列化（serialize）的逆操作。序列化和反序列化本身只是正常的程序功能，但是一旦设计不慎，缺乏访问控制的反序列化能够导致攻击者改变程序的正常执行流程，这种情况下我们称之为存在反序列化漏洞。<br> 反序列化漏洞以极其难以理解与掌握而闻名。不过今天这里可以用较为简单的方法来学习它。

---

序列化，是指把某个对象“降维”。

```text
<?php
class User {
    public $username;
    public $role;

    public function __construct($username, $role) {
        $this->username = $username;
        $this->role = $role;
    }

    public function welcome() {
        return "欢迎回来, " . $this->username . " (身份: " . $this->role . ")";
    }
}

// --- 第一部分：序列化 (保存) ---
$user = new User("user01", "Editor");
$serializedData = serialize($user);

echo "序列化后的字符串: \n" . $serializedData . "\n\n";
// 输出结果类似于: O:4:"User":2:{s:8:"username";s:6:"user01";s:4:"role";s:6:"Editor";}

// --- 第二部分：反序列化 (还原) ---
$newObject = unserialize($serializedData);

echo "还原后的对象行为: \n";
echo $newObject->welcome();
?>
```

到这里其实就可以理解为什么需要有序列化和反序列化了。我们有时候需要持久存储或者在网络上传输一个对象，但是这很难直接做到，所以我们按照某种规范，把对象内的数据提取出来，将其组合成字符串，便于存储或者传输，等要使用这个对象的时候，根据字符串找出对应数据，即可将对象还原。

因此，反序列化实际上是试图还原对象的过程。这就意味着如果反序列化的对象是外部可控的，那么攻击者能够构造一个恶意对象，执行想要的功能。<br> 最关键的一点是，根据前面的描述，我们很容易意识到一点，反序列化的安全问题来自于对外部输入的信任，而非特定的编程语言特性——这就意味着这种漏洞并不会局限于某一两种编程语言，而是具有广泛的影响。`Java，PHP，Python，.NET`，以及诸如此类……现在全部笼罩在这种漏洞的风险之中。

## 它是如何成为梦魇的 {#它是如何成为梦魇的}

2015年，一篇文章出现在了互联网上。作者展示了一种在当时是全新的攻击方式，并且实现了这样的效果：<br> **黑掉WebLogic、WebSphere、JBoss、Jenkins 和 OpenNMS。**

参考链接：<br> [https://foxglovesecurity.com/2015/11/06/what-do-weblogic-websphere-jboss-jenkins-opennms-and-your-application-have-in-common-this-vulnerability/](https://foxglovesecurity.com/2015/11/06/what-do-weblogic-websphere-jboss-jenkins-opennms-and-your-application-have-in-common-this-vulnerability/)

以一种简单粗暴的方式（几乎横扫整个Java世界），把Java反序列化漏洞带入了世人的视野。

---

实际上，由于反序列化是出于还原对象的考虑，因此大部分语言中，反序列化只能还原出系统上本来就存在的类（至少Java是如此）。但是为什么还是发生了这么严重的安全问题？要知道，一个反序列化时会立刻执行恶意命令的类几乎是不可能存在的（因为那基本上属于后门）。<br> 答案是**利用链**。<br> 以这篇文章为例，作者实际上是挖掘了Apache Commons Collections这个组件（也就是所谓的CC库）中存在的利用链。而前文所述的各种被黑掉的中间件，正是在有反序列化漏洞的基础上，集成了这一非常普通的常用组件。

Apache Commons Collections 是 Java 中极其流行的第三方库，专门用于扩展 Java 原生的集合框架（如 List, Map）。它提供了一种叫 Transformer 的接口，允许开发者在操作集合时，对其中的对象进行自动化的转换。

### 致命的齿轮：利用链（Gadget Chain） {#致命的齿轮利用链gadget-chain}

要把一个简单的“反序列化”操作变成“执行任意命令（RCE）”，需要像搭积木一样把几个类串联起来。

第一步：核心动力——InvokerTransformer<br> 这是链条的末端。这个类有一个特性：它可以通过 Java 的反射机制调用任意方法。

只要黑客能控制它的输入，就可以让它去调用 Runtime.getRuntime().exec("calc.exe")。

第二步：链式调用——ChainedTransformer<br> 一个 InvokerTransformer 只能执行一步动作，但 ChainedTransformer 像一个传送带，可以把多个 Transformer 串在一起。

黑客把多个精心构造的 Transformer 放进去，形成一个： 获取 Runtime 类 -> 获取 getRuntime 方法 -> 执行命令 的完整闭环。

第三步：自动触发——TransformedMap 或 LazyMap<br> 这是链条的开关。当 Map 中的数据被修改或访问时，它会自动触发内部的 Transformer。

第四步：入口点（反序列化）——AnnotationInvocationHandler<br> 这是最天才的一步。研究人员发现这个 JDK 自带的内部类在反序列化（readObject）时，会去操作一个 Map 成员。

链条闭合：黑客伪造一个 AnnotationInvocationHandler 的序列化对象，里面塞入恶意构造的 Map。

触发：当服务器调用 unserialize() 时，会自动触发 AnnotationInvocationHandler 的逻辑，进而触发 Map 转换，最后由 InvokerTransformer 执行系统命令。

乍一听很复杂（实际上确实有点复杂）。但是底层逻辑是简单的，即某个类的readObject（会在反序列化时被执行，目的是将对象还原）其中会操作其他对象，而其他对象也可以操作另一个对象，最终到达了危险功能。这个过程在复杂的利用链中会比较长，但也有很短的利用链，例如urldns链。

URLDNS 链的精妙之处在于它利用了 HashMap 的一个“特性”：

入口点 (Entry Point)：java.util.HashMap

HashMap 在反序列化（readObject）时，为了重建哈希表，必须重新计算存储的所有键（Key）的哈希值（hash 方法）。

触发点 (Trigger)：java.net.URL

当 URL 对象作为 HashMap 的键时，计算其哈希值（调用 URL.hashCode()）会触发一个有趣的动作。

终点 (Sink)：URLStreamHandler.getHostAddress()

为了计算 URL 的哈希值，Java 认为必须知道该域名对应的 IP 地址。于是，它会自动调用网络协议栈去发起一次 DNS 解析。

因此，该链条的目标不是为了执行系统命令（RCE），而是为了让服务器发起一次 DNS 请求。

当黑客在自己的服务器上监控 DNS 日志时，如果收到了来自目标服务器的解析请求，就证明目标服务器成功触发了反序列化逻辑。<br> 最重要的一点是：它完全不依赖任何第三方库（只使用 JDK 自带的类），因此在任何安装了 Java 的环境下都能运行。<br> 在安全测试中，它常被用来当作“探测针”，用来确认一个点是否存在反序列化漏洞。

所以，反序列化漏洞的底层逻辑其实很纯粹：入口点通常是类的 readObject 方法（在还原对象时被自动触发），它在执行时会链式地调用或修改其他关联对象。通过精心构造这些对象的层级关系，攻击者可以引导程序逻辑最终走向某个危险函数（Sink）。这个过程即所谓的“利用链”，它既可以是像 CC 链那样曲折复杂的长链，也可以是像 URLDNS 链 那样短小精悍、不依赖第三方库的探测短链。

---

诚然，在今天，直接通过 Web 接口接收原始二进制流并反序列化的行为已大大减少。然而，对开发效率的极致追求，使得现代应用依然需要跨端传输复杂的对象结构——只是载体从二进制流演变成了 XML 和 JSON。 > 这种转变并未从根本上消除风险。当 JSON 解析器（如 Fastjson 或 Jackson）为了方便开发者，试图根据字符串内容自动“还原”出对应的 Java 对象时，“自动化实例化”的过程再次给了攻击者可乘之机。这本质上是将原本针对 readObject 的攻击，转移到了针对类的 setter、getter 或构造函数的攻击。

这就是反序列化漏洞的前世今生了，从早期通过网络传输二进制流，到今天的各种json库实现反序列化……我想现在读者已经能建立起一个对这种漏洞的整体认知，并且能大致理解今天的各种反序列化漏洞的成因了。不过如果想要进一步探索这种漏洞，还是需要去逐个分析现有的利用链和历史漏洞。

### Why so serial? {#why-so-serial}

[https://github.com/frohoff/ysoserial](https://github.com/frohoff/ysoserial)<br> ysoserial工具，最初是用来演示反序列化漏洞的，因此它相当于一个反序列化Payload构造器，等同于SQL注入中的SQLmap的地位。<br> 基本上，无论是前期对利用链本身的研究，还是后期对工具进行二开从而创作属于自己的利用链，ysoserial都是无法绕开的一款经典工具。<br> 同样的，后续在`.NET`领域中，也诞生了对应的另一款工具：`ysoserial.net`<br> 不过，在一个页面中展示所有语言的反序列化漏洞未免有些激进，更何况还有Python等语言的反序列化没有提及，因此这里碍于篇幅而无法展开，留给各位读者自行探索。

### 反序列化漏洞在红队行动中的意义是什么？ {#反序列化漏洞在红队行动中的意义是什么}

在之前的页面中，我们提到上传脚本文件作为Webshell，可以使得我们获取服务器权限。但是现代Web应用中，能够通过文件上传漏洞获取权限的情况越来越少了。因此有时候不得不挖掘反序列化漏洞，直接在内存层面上完成攻击，不需要上传或者写入文件，而是直接实现远程代码执行。同时，为了克服现代环境的限制，反序列化漏洞往往能够与**内存马**技术配合，从而在不接触硬盘的情况下实现远程控制。

内存马，在Java领域最为广泛，是一种不接触磁盘，在内存中直接运行的Webshell，例如通过动态注册一个恶意Filter，使得以某种形式传入的隐蔽参数可以被执行。在过去，内存马需要先上传Webshell，然后执行Webshell来植入内存马（当然，这样就失去大部分意义了……），但是反序列化等现代攻击手段使得整个攻击过程完全在内存中进行，直接远程执行代码打入内存马，然后访问内存马实现远程控制，全程无需写入任何文件。
