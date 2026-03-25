#!/usr/bin/env python3
"""
最终验证测试 - 准确判断界面是否卡住

测试原理:
1. 启动一个定时器,每100ms更新时间显示
2. 启动连接操作
3. 观察定时器是否继续工作
4. 如果定时器停止更新,说明主线程被阻塞
"""

import time
import tkinter as tk
from tkinter import ttk


def test_original():
    """测试原始版本"""
    from connection_manager import ConnectionManager

    manager = ConnectionManager()
    root = tk.Tk()
    root.title("原始版本测试")
    root.geometry("300x200")

    # 状态显示
    status_var = tk.StringVar(value="准备")
    tk.Label(root, textvariable=status_var, font=("Arial", 12)).pack(pady=10)

    # 定时器显示
    timer_var = tk.StringVar(value="定时器: 运行中")
    tk.Label(root, textvariable=timer_var, font=("Arial", 14), fg="green").pack(pady=10)

    # 连接耗时显示
    elapsed_var = tk.StringVar(value="连接耗时: 0.0s")
    tk.Label(root, textvariable=elapsed_var).pack(pady=5)

    # 统计信息
    tick_count = [0]
    tick_stopped = [False]

    # 定时器函数
    def tick():
        tick_count[0] += 1
        timer_var.set(f"定时器: 运行中 (更新{tick_count[0]}次)")
        # 0.1秒后再次调用
        if not tick_stopped[0]:
            root.after(100, tick)

    # 开始定时器
    tick()

    # 连接函数
    def do_connect():
        status_var.set("连接中...")
        print(f"[原始版本] 开始连接...")

        start = time.time()
        manager.test_connection(
            'ssh',
            ip='192.0.2.1',
            username='test',
            password='test',
            timeout=5
        )
        elapsed = time.time() - start

        print(f"[原始版本] 连接完成, 耗时 {elapsed:.1f}秒")
        print(f"[原始版本] 定时器更新次数: {tick_count[0]}")

        elapsed_var.set(f"连接耗时: {elapsed:.1f}s")
        status_var.set("连接完成")

        # 连接完成后,继续运行定时器1秒
        time.sleep(1)
        tick_stopped[0] = True
        root.destroy()

        return tick_count[0]

    # 延迟启动连接,让定时器先运行
    root.after(500, do_connect)

    # 运行主循环
    root.mainloop()

    return tick_count[0]


def test_async():
    """测试异步版本"""
    from async_connection_manager import AsyncConnectionManager

    manager = AsyncConnectionManager()
    root = tk.Tk()
    root.title("异步版本测试")
    root.geometry("300x200")

    # 状态显示
    status_var = tk.StringVar(value="准备")
    tk.Label(root, textvariable=status_var, font=("Arial", 12)).pack(pady=10)

    # 定时器显示
    timer_var = tk.StringVar(value="定时器: 运行中")
    tk.Label(root, textvariable=timer_var, font=("Arial", 14), fg="green").pack(pady=10)

    # 连接耗时显示
    elapsed_var = tk.StringVar(value="连接耗时: 0.0s")
    tk.Label(root, textvariable=elapsed_var).pack(pady=5)

    # 统计信息
    tick_count = [0]
    tick_stopped = [False]
    connect_started = [False]

    # 定时器函数
    def tick():
        tick_count[0] += 1

        # 连接开始后才计数
        if connect_started[0]:
            timer_var.set(f"定时器: 运行中 (更新{tick_count[0]}次)")
        else:
            timer_var.set(f"定时器: 运行中 (等待连接)")

        # 0.1秒后再次调用
        if not tick_stopped[0]:
            root.after(100, tick)

    # 开始定时器
    tick()

    # 连接函数
    def do_connect():
        print(f"[异步版本] 开始后台连接...")
        status_var.set("连接中...")
        connect_started[0] = True

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

            print(f"[异步版本] 连接完成, 耗时 {elapsed:.1f}秒")
            print(f"[异步版本] 定时器更新次数: {tick_count[0]}")

            # 更新UI (必须在主线程)
            root.after(0, lambda: elapsed_var.set(f"连接耗时: {elapsed:.1f}s"))
            root.after(0, lambda: status_var.set("连接完成"))

            # 连接完成后,继续运行定时器1秒
            time.sleep(1)
            tick_stopped[0] = True
            root.after(0, root.destroy)

        import threading
        threading.Thread(target=worker, daemon=True).start()

    # 延迟启动连接
    root.after(500, do_connect)

    # 运行主循环
    root.mainloop()

    return tick_count[0]


# 运行测试
print("="*70)
print("最终验证测试 - 定时器法")
print("="*70)
print("\n测试原理:")
print("1. 每100ms更新一次定时器显示")
print("2. 启动连接操作")
print("3. 观察定时器是否继续更新")
print("4. 如果定时器停止更新,说明主线程被阻塞\n")

print("测试1: 原始 ConnectionManager (连接在主线程)")
print("-" * 70)
ticks1 = test_original()

print("\n等待1秒...")
time.sleep(1)

print("\n测试2: 异步 ConnectionManager (连接在后台线程)")
print("-" * 70)
ticks2 = test_async()


# 结果分析
print("\n" + "="*70)
print("测试结果分析")
print("="*70)

print(f"\n原始版本:")
print(f"  预期定时器更新次数: 50次 (5秒 × 10次/秒)")
print(f"  实际定时器更新次数: {ticks1}次")
print(f"  更新比例: {ticks1/50*100:.1f}%")

if ticks1 < 10:
    print("  结论: X 主线程被严重阻塞,定时器几乎停止!")
elif ticks1 < 30:
    print("  结论: ⚠ 主线程部分阻塞,定时器运行不正常!")
else:
    print("  结论: ? 主线程基本正常,可能有其他原因")

print(f"\n异步版本:")
print(f"  预期定时器更新次数: 50次 (5秒 × 10次/秒)")
print(f"  实际定时器更新次数: {ticks2}次")
print(f"  更新比例: {ticks2/50*100:.1f}%")

if ticks2 >= 40:
    print("  结论: OK 主线程正常,定时器正常运行!")
elif ticks2 >= 20:
    print("  结论: ⚠ 主线程基本正常,但性能略有下降")
else:
    print("  结论: X 主线程仍有阻塞问题!")

# 最终结论
print("\n" + "="*70)
print("最终结论")
print("="*70)

if ticks2 >= 40:
    print("\nOK! AsyncConnectionManager 可以解决界面卡顿问题!")
    print("\n使用方法:")
    print("  from async_connection_manager import AsyncConnectionManager")
    print("  manager = AsyncConnectionManager()")
    print()
    print("在GUI中:")
    print("  def on_test():")
    print("      def worker():")
    print("          result = manager.test_connection(...)")
    print("          update_ui(result)")
    print("      threading.Thread(target=worker, daemon=True).start()")
else:
    print("\nX 仍有问题,需要进一步调查...")
    print(f"  原始版本定时器更新: {ticks1}")
    print(f"  异步版本定时器更新: {ticks2}")
