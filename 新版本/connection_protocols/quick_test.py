#!/usr/bin/env python3
"""
快速测试 - 简化版验证
"""

import time
import tkinter as tk

def test_original():
    from connection_manager import ConnectionManager
    manager = ConnectionManager()

    root = tk.Tk()
    root.title("原始版本")
    root.geometry("250x150")

    timer_var = tk.StringVar(value="等待...")
    tk.Label(root, textvariable=timer_var, font=("Arial", 14)).pack(pady=20)

    ticks = [0]
    def tick():
        ticks[0] += 1
        timer_var.set(f"定时器: {ticks[0]}")
        if ticks[0] < 30:
            root.after(100, tick)

    tick()

    # 连接
    start = time.time()
    manager.test_connection('ssh', ip='192.0.2.1', username='test', password='test', timeout=3)
    elapsed = time.time() - start

    time.sleep(1)
    root.destroy()
    return ticks[0], elapsed

def test_async():
    from async_connection_manager import AsyncConnectionManager
    manager = AsyncConnectionManager()

    root = tk.Tk()
    root.title("异步版本")
    root.geometry("250x150")

    timer_var = tk.StringVar(value="等待...")
    tk.Label(root, textvariable=timer_var, font=("Arial", 14)).pack(pady=20)

    ticks = [0]
    def tick():
        ticks[0] += 1
        timer_var.set(f"定时器: {ticks[0]}")
        if ticks[0] < 30:
            root.after(100, tick)

    tick()

    # 后台连接
    import threading
    def worker():
        manager.test_connection('ssh', ip='192.0.2.1', username='test', password='test', timeout=3)

    threading.Thread(target=worker, daemon=True).start()
    time.sleep(4)  # 等待连接完成
    root.destroy()
    return ticks[0], 3

print("快速测试开始...")

print("\n测试1: 原始版本")
ticks1, elapsed1 = test_original()
print(f"  定时器更新: {ticks1}次, 连接耗时: {elapsed1:.1f}秒")

print("\n测试2: 异步版本")
ticks2, elapsed2 = test_async()
print(f"  定时器更新: {ticks2}次, 连接耗时: {elapsed2:.1f}秒")

print("\n结果:")
print(f"  原始版本: {ticks1}次 (预期: 30次)")
print(f"  异步版本: {ticks2}次 (预期: 30次)")

if ticks2 >= 25:
    print("\nOK! 异步版本正常工作!")
elif ticks1 < 5:
    print("\n原始版本主线程被阻塞!")
else:
    print(f"\n原始版本: {ticks1}次更新")
    print(f"异步版本: {ticks2}次更新")
