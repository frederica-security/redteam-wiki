---
title: "物理读写利用绕过技术 - mmpfn详解"
description: ""
source_url: "https://redteam-wiki.org/en/physical-memory-rw-mmpfn"
created_at: "2025-12-03T16:33:14.835Z"
updated_at: "2026-03-27T12:12:03.942Z"
author: "芙蕾德莉卡"
---
# 物理读写利用绕过技术 - mmpfn详解

## 堵住漏洞利用之门：MmMapIoSpace的限制 {#堵住漏洞利用之门mmmapiospace的限制}

在之前的章节中：我们讲解了一些利用驱动漏洞BYOVD，或者是win32k这样的内核模块漏洞，通过读写特定的内核空间结构，致盲杀毒软件或edr的方法，其中最常见的一种漏洞类型就是：通过MmMapIoSpace函数映射出了特定的物理内存空间。

从windows 1803开始，MmMapIoSpace不再被允许映射页表相关的物理地址，这直接让相关的漏洞利用，甚至是一些游戏外挂开发者都受到了影响。

那么，我们就要问一个问题：Windows是怎么实现这个机制的，我们又能不能加以绕过？

## 阻止MmMapIoSpace映射页表内存的原理 {#阻止mmmapiospace映射页表内存的原理}

阻止页表的映射后，攻击者就真的无法利用这种物理内存漏洞了么？<br> 为了解决这个问题，我们先要了解一下Windows是如何把硬件上的物理内存映射到虚拟内存，以及在处理虚拟内存时，将其翻译为特定物理内存的。
