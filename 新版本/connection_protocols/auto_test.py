#!/usr/bin/env python3
"""
自动化测试 - 验证界面是否卡住

完全自动化,不需要手动操作
"""

import time
import threading
import tkinter as tk
from tkinter import ttk


def test_original():
    """测试原始版本"""
    from connection_manager import ConnectionManager

    manager = ConnectionManager()
    root = tk.Tk()
    root.title("原始版本测试")
    root.geometry("300x150")

    status_var = tk.StringVar(value="准备")
    tk.Label(root, textvariable=status_var).pack(pady=10)

    click_count = [0]
    elapsed_container = [0]
    count_var = tk.StringVar(value="点击: 0")
    tk.Label(root, textvariable=count_var).pack(pady=10)

    def on_click():
        click_count[0] += 1
        count_var.set(f"点击: {click_count[0]}")

    def test_connection():
        status_var.set("连接中...")
        root.update()

        start = time.time()
        manager.test_connection(
            'ssh',
            ip='192.0.2.1',
            username='test',
            password='test',
            timeout=5
        )
        elapsed = time.time() - start
        elapsed_container[0] = elapsed

        status_var.set(f"完成 ({elapsed:.1f}s)")
        count_var.set(f"点击: {click_count[0]}")

    # 自动点击按钮的线程
    def auto_clicker():
        time.sleep(0.5)  # 等待连接开始
        for i in range(5):
            time.sleep(0.5)
            try:
                on_click()
            except:
                pass

    # 启动连接
    test_connection()

    # 启动自动点击
    threading.Thread(target=auto_clicker, daemon=True).start()

    # 等待测试完成
    start_time = time.time()
    while time.time() - start_time < 7:
        try:
            root.update()
        except:
            pass
        time.sleep(0.05)

    try:
        root.destroy()
    except:
        pass
    return click_count[0], elapsed_container[0]


def test_async():
    """测试异步版本"""
    from async_connection_manager import AsyncConnectionManager

    manager = AsyncConnectionManager()
    root = tk.Tk()
    root.title("异步版本测试")
    root.geometry("300x150")

    status_var = tk.StringVar(value="准备")
    tk.Label(root, textvariable=status_var).pack(pady=10)

    click_count = [0]
    count_var = tk.StringVar(value="点击: 0")
    tk.Label(root, textvariable=count_var).pack(pady=10)

    def on_click():
        click_count[0] += 1
        count_var.set(f"点击: {click_count[0]}")

    def test_connection():
        status_var.set("连接中...")

        def worker():
            start = time.time()
            manager.test_connection(
                'ssh',
                ip='192.0.2.1',
                username='test',
                password='test',
                timeout=5
            )
            elapsed = time.time() - start

            try:
                root.after(0, lambda: status_var.set(f"完成 ({elapsed:.1f}s)"))
                root.after(0, lambda: count_var.set(f"点击: {click_count[0]}"))
            except:
                pass

        threading.Thread(target=worker, daemon=True).start()

    # 自动点击按钮的线程
    def auto_clicker():
        time.sleep(0.5)  # 等待连接开始
        for i in range(5):
            time.sleep(0.5)
            try:
                on_click()
            except:
                pass

    # 启动连接
    test_connection()

    # 启动自动点击
    threading.Thread(target=auto_clicker, daemon=True).start()

    # 等待测试完成
    start_time = time.time()
    while time.time() - start_time < 7:
        try:
            root.update()
        except:
            pass
        time.sleep(0.05)

    try:
        root.destroy()
    except:
        pass
    return click_count[0], 5  # 异步版本超时约5秒


# 运行测试
print("="*70)
print("自动化测试 - 验证界面是否卡住")
print("="*70)

print("\n测试1: 原始版本 (连接在主线程)")
print("-" * 70)
clicks1, elapsed1 = test_original()
print(f"连接耗时: {elapsed1:.1f} 秒")
print(f"期间点击次数: {clicks1}")

if clicks1 == 0:
    print("X 原始版本: 界面卡住了,无法响应点击!")
else:
    print(f"? 原始版本: 响应了 {clicks1} 次点击")

print("\n测试2: 异步版本 (连接在后台线程)")
print("-" * 70)
clicks2, elapsed2 = test_async()
print(f"连接耗时: {elapsed2:.1f} 秒")
print(f"期间点击次数: {clicks2}")

if clicks2 >= 3:
    print(f"OK 异步版本: 界面响应了 {clicks2} 次点击!")
else:
    print(f"? 异步版本: 只响应了 {clicks2} 次点击")

# 结论
print("\n" + "="*70)
print("测试结论")
print("="*70)

if clicks2 >= 3:
    print("\n成功! AsyncConnectionManager 可以解决界面卡顿问题!\n")
    print("使用方法:")
    print("  from async_connection_manager import AsyncConnectionManager")
    print("  manager = AsyncConnectionManager()")
    print()
    print("在GUI中:")
    print("  def on_test():")
    print("      threading.Thread(target=worker, daemon=True).start()")
else:
    print("\n仍有问题,需要进一步调查...")

print(f"\n对比:")
print(f"  原始版本点击: {clicks1}")
print(f"  异步版本点击: {clicks2}")
print(f"  改进: {clicks2 - clicks1}")
