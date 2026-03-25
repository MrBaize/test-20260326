#!/usr/bin/env python3
"""
真实测试 - 模拟实际用户操作

测试方法:
1. 启动GUI窗口
2. 点击"测试连接"按钮
3. 然后立即尝试点击"点击计数"按钮
4. 观察是否可以响应点击
"""

import time
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime


# 测试原始版本
print("="*70)
print("测试1: 原始 ConnectionManager")
print("="*70)
print("操作指南:")
print("1. 等待窗口出现")
print("2. 点击 '测试连接' 按钮")
print("3. 在连接过程中,尝试点击 '点击计数' 按钮")
print("4. 观察是否能响应\n")
print("如果点击计数按钮不工作,说明界面卡住了!\n")

from connection_manager import ConnectionManager

manager1 = ConnectionManager()

root1 = tk.Tk()
root1.title("测试1: 原始版本 (会卡住吗?)")
root1.geometry("400x250")

status1 = tk.StringVar(value="状态: 就绪")
tk.Label(root1, textvariable=status1, font=("Arial", 12)).pack(pady=10)

click_count1 = [0]
count_label1 = tk.StringVar(value="点击次数: 0")
tk.Label(root1, textvariable=count_label1, font=("Arial", 14)).pack(pady=10)

def on_click1():
    click_count1[0] += 1
    count_label1.set(f"点击次数: {click_count1[0]}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 点击按钮被点击!")

tk.Button(root1, text="点击计数 (测试响应)", command=on_click1,
          font=("Arial", 12), bg="lightblue").pack(pady=10)

def on_connect1():
    status1.set("状态: 正在连接...")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始连接...")

    start = time.time()
    result = manager1.test_connection(
        'ssh',
        ip='192.0.2.1',  # 不可路由的IP,会超时
        username='test',
        password='test',
        port=22,
        timeout=5
    )
    elapsed = time.time() - start

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 连接完成, 耗时 {elapsed:.1f}秒")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 期间点击次数: {click_count1[0]}")

    status1.set(f"状态: 完成 ({elapsed:.1f}秒)")
    count_label1.set(f"点击次数: {click_count1[0]}")

tk.Button(root1, text="测试连接 (5秒超时)", command=on_connect1,
          font=("Arial", 12), bg="lightcoral").pack(pady=10)

root1.mainloop()

time.sleep(1)


# 测试异步版本
print("\n" + "="*70)
print("测试2: 异步 ConnectionManager")
print("="*70)
print("操作指南:")
print("1. 等待窗口出现")
print("2. 点击 '测试连接' 按钮")
print("3. 在连接过程中,尝试点击 '点击计数' 按钮")
print("4. 观察是否能响应")
print("5. 理论上,应该可以点击计数按钮!\n")

from async_connection_manager import AsyncConnectionManager

manager2 = AsyncConnectionManager()

root2 = tk.Tk()
root2.title("测试2: 异步版本 (不会卡住)")
root2.geometry("400x250")

status2 = tk.StringVar(value="状态: 就绪")
tk.Label(root2, textvariable=status2, font=("Arial", 12)).pack(pady=10)

click_count2 = [0]
count_label2 = tk.StringVar(value="点击次数: 0")
tk.Label(root2, textvariable=count_label2, font=("Arial", 14)).pack(pady=10)

def on_click2():
    click_count2[0] += 1
    count_label2.set(f"点击次数: {click_count2[0]}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 点击按钮被点击!")

tk.Button(root2, text="点击计数 (测试响应)", command=on_click2,
          font=("Arial", 12), bg="lightblue").pack(pady=10)

def on_connect2():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始后台连接...")

    def worker():
        root2.after(0, lambda: status2.set("状态: 正在连接..."))

        start = time.time()
        result = manager2.test_connection(
            'ssh',
            ip='192.0.2.1',  # 不可路由的IP,会超时
            username='test',
            password='test',
            port=22,
            timeout=5
        )
        elapsed = time.time() - start

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 连接完成, 耗时 {elapsed:.1f}秒")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 期间点击次数: {click_count2[0]}")

        root2.after(0, lambda: status2.set(f"状态: 完成 ({elapsed:.1f}秒)"))
        root2.after(0, lambda: count_label2.set(f"点击次数: {click_count2[0]}"))

    threading.Thread(target=worker, daemon=True).start()

tk.Button(root2, text="测试连接 (5秒超时)", command=on_connect2,
          font=("Arial", 12), bg="lightgreen").pack(pady=10)

root2.mainloop()


# 总结
print("\n" + "="*70)
print("测试结果")
print("="*70)
print(f"原始版本测试1: 点击次数 = {click_count1[0]}")
print(f"异步版本测试2: 点击次数 = {click_count2[0]}")
print()

if click_count2[0] > 0:
    print("OK 异步版本可以正常响应点击!")
    print("  说明: AsyncConnectionManager 不会阻塞界面")
else:
    print("X 异步版本可能仍有问题")

if click_count1[0] == 0:
    print("X 原始版本: 连接期间无法响应点击 (界面卡住)")
else:
    print("OK 原始版本: 可以响应点击")

print("\n" + "="*70)
print("结论")
print("="*70)

if click_count2[0] > 0:
    print("解决方案有效!")
    print("\n使用方法:")
    print("1. 导入异步管理器:")
    print("   from async_connection_manager import AsyncConnectionManager")
    print("\n2. 创建实例:")
    print("   manager = AsyncConnectionManager()")
    print("\n3. 在后台线程执行:")
    print("   threading.Thread(target=worker, daemon=True).start()")
else:
    print("需要进一步调查问题")
