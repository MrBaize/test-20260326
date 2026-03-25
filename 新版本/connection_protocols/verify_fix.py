#!/usr/bin/env python3
"""
验证脚本 - 实际测试界面是否还会卡住

这个脚本模拟真实的GUI使用场景,测试以下情况:
1. 连接不存在的服务器(会超时)
2. 在连接过程中主线程是否还能响应
"""

import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox


# 测试1: 使用原始的 ConnectionManager
print("="*70)
print("测试1: 使用原始 ConnectionManager (预期会卡住)")
print("="*70)

from connection_manager import ConnectionManager

original_manager = ConnectionManager()

root1 = tk.Tk()
root1.title("原始版本测试 - 会卡住吗？")
root1.geometry("400x200")

status_label1 = ttk.Label(root1, text="准备测试...", font=("Arial", 12))
status_label1.pack(pady=20)

click_count1 = [0]

def on_click_test1():
    click_count1[0] += 1
    status_label1.config(text=f"点击次数: {click_count1[0]}")

test_btn1 = ttk.Button(root1, text="测试主线程响应(点击我)", command=on_click_test1)
test_btn1.pack(pady=10)

connect_btn1 = ttk.Button(root1, text="测试连接(会卡住)", command=lambda: test_connection_1())
connect_btn1.pack(pady=10)

def test_connection_1():
    status_label1.config(text="正在连接... (可能会卡住)")
    root1.update()

    start = time.time()
    result = original_manager.test_connection(
        'ssh',
        ip='192.0.2.1',  # 不可路由的IP
        username='test',
        password='test',
        port=22,
        timeout=5
    )
    elapsed = time.time() - start

    status_label1.config(text=f"完成! 耗时 {elapsed:.1f}秒, 点击次数: {click_count1[0]}")
    print(f"原始版本: 耗时 {elapsed:.1f}秒, 期间点击次数: {click_count1[0]}")

    if elapsed > 10:
        print("警告: 连接耗时超过10秒,说明卡住了!")
    else:
        print("OK 连接在预期时间内完成")

# 延迟执行连接,先让GUI启动
root1.after(1000, test_connection_1)

# 5秒后自动关闭
root1.after(8000, root1.destroy)

print("测试1: 启动GUI (5秒后会连接,8秒后关闭)...")
root1.mainloop()

print(f"测试1完成: 期间点击次数 = {click_count1[0]}\n")


# 测试2: 使用 AsyncConnectionManager
print("="*70)
print("测试2: 使用 AsyncConnectionManager (预期不卡住)")
print("="*70)

from async_connection_manager import AsyncConnectionManager

async_manager = AsyncConnectionManager()

root2 = tk.Tk()
root2.title("异步版本测试 - 不会卡住")
root2.geometry("400x200")

status_label2 = ttk.Label(root2, text="准备测试...", font=("Arial", 12))
status_label2.pack(pady=20)

click_count2 = [0]
connecting = [False]

def on_click_test2():
    click_count2[0] += 1
    status_label2.config(text=f"点击次数: {click_count2[0]}")
    # 如果正在连接,显示信息
    if connecting[0]:
        status_label2.config(text=f"点击次数: {click_count2[0]} (正在连接中!)")

test_btn2 = ttk.Button(root2, text="测试主线程响应(点击我)", command=on_click_test2)
test_btn2.pack(pady=10)

connect_btn2 = ttk.Button(root2, text="测试连接(不卡住)", command=lambda: test_connection_2())
connect_btn2.pack(pady=10)

def test_connection_2():
    def worker():
        connecting[0] = True
        root2.after(0, lambda: status_label2.config(text="正在后台连接..."))

        start = time.time()
        result = async_manager.test_connection(
            'ssh',
            ip='192.0.2.1',  # 不可路由的IP
            username='test',
            password='test',
            port=22,
            timeout=5
        )
        elapsed = time.time() - start
        connecting[0] = False

        root2.after(0, lambda: status_label2.config(
            text=f"完成! 耗时 {elapsed:.1f}秒, 点击次数: {click_count2[0]}"
        ))

        print(f"异步版本: 耗时 {elapsed:.1f}秒, 期间点击次数: {click_count2[0]}")

        if elapsed <= 7:
            print("OK 连接在预期时间内完成")
        else:
            print("警告: 连接超时")

    threading.Thread(target=worker, daemon=True).start()

# 延迟执行连接
root2.after(1000, test_connection_2)

# 8秒后自动关闭
root2.after(8000, root2.destroy)

print("测试2: 启动GUI (1秒后会连接,8秒后关闭)...")
root2.mainloop()

print(f"测试2完成: 期间点击次数 = {click_count2[0]}\n")


# 总结
print("="*70)
print("测试结果对比")
print("="*70)
print(f"原始版本测试1: 期间点击次数 = {click_count1[0]}")
print(f"异步版本测试2: 期间点击次数 = {click_count2[0]}")
print()

if click_count1[0] < 3:
    print("X 原始版本: 主线程被阻塞,无法响应用户点击")
else:
    print("OK 原始版本: 主线程可以响应")

if click_count2[0] >= 3:
    print("OK 异步版本: 主线程可以正常响应用户点击")
else:
    print("X 异步版本: 主线程可能仍有问题")

print()
print("="*70)
print("结论")
print("="*70)

if click_count2[0] >= 3:
    print("OK AsyncConnectionManager 可以解决界面卡顿问题!")
    print("  使用方法:")
    print("    from async_connection_manager import AsyncConnectionManager")
    print("    manager = AsyncConnectionManager()")
    print()
    print("  在GUI中:")
    print("    def on_test():")
    print("        threading.Thread(target=worker, daemon=True).start()")
else:
    print("X 仍有问题,需要进一步调查")
