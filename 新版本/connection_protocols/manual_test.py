#!/usr/bin/env python3
"""
手动测试 - 请亲自点击测试

使用方法:
1. 运行这个脚本
2. 会弹出两个窗口
3. 分别点击"测试连接"按钮
4. 然后立即点击"点击测试"按钮
5. 观察哪个窗口可以响应点击
"""

import time
import tkinter as tk
from tkinter import ttk, messagebox


# ========== 窗口1: 原始版本 ==========
def window1_original():
    from connection_manager import ConnectionManager

    manager = ConnectionManager()
    root = tk.Tk()
    root.title("窗口1: 原始版本 (会卡住)")
    root.geometry("400x250")
    root.geometry("+100+100")  # 位置

    # 状态
    status_var = tk.StringVar(value="状态: 就绪")
    tk.Label(root, textvariable=status_var, font=("Arial", 12)).pack(pady=10)

    # 点击计数
    click_count = [0]
    count_var = tk.StringVar(value="点击测试: 0次")
    tk.Label(root, textvariable=count_var, font=("Arial", 14, "bold"), fg="blue").pack(pady=10)

    # 点击测试按钮
    def on_click():
        click_count[0] += 1
        count_var.set(f"点击测试: {click_count[0]}次")

    tk.Button(root, text="点击测试 (测试是否卡住)", command=on_click,
              font=("Arial", 12), bg="lightblue", height=2).pack(pady=10, fill="x", padx=20)

    # 测试连接按钮
    def on_connect():
        status_var.set("状态: 正在连接...")

        start = time.time()
        result = manager.test_connection(
            'ssh',
            ip='192.0.2.1',  # 不可路由IP,会超时
            username='test',
            password='test',
            timeout=5
        )
        elapsed = time.time() - start

        status_var.set(f"状态: 完成 ({elapsed:.1f}秒)")
        messagebox.showinfo("窗口1", f"连接完成!\n耗时: {elapsed:.1f}秒\n期间点击: {click_count[0]}次")

    tk.Button(root, text="测试连接 (点击后立即点上面)", command=on_connect,
              font=("Arial", 12), bg="lightcoral", height=2).pack(pady=10, fill="x", padx=20)

    return root


# ========== 窗口2: 异步版本 ==========
def window2_async():
    from async_connection_manager import AsyncConnectionManager

    manager = AsyncConnectionManager()
    root = tk.Tk()
    root.title("窗口2: 异步版本 (不卡住)")
    root.geometry("400x250")
    root.geometry("+550+100")  # 位置

    # 状态
    status_var = tk.StringVar(value="状态: 就绪")
    tk.Label(root, textvariable=status_var, font=("Arial", 12)).pack(pady=10)

    # 点击计数
    click_count = [0]
    count_var = tk.StringVar(value="点击测试: 0次")
    tk.Label(root, textvariable=count_var, font=("Arial", 14, "bold"), fg="green").pack(pady=10)

    # 点击测试按钮
    def on_click():
        click_count[0] += 1
        count_var.set(f"点击测试: {click_count[0]}次")

    tk.Button(root, text="点击测试 (测试是否卡住)", command=on_click,
              font=("Arial", 12), bg="lightblue", height=2).pack(pady=10, fill="x", padx=20)

    # 测试连接按钮
    def on_connect():
        def worker():
            root.after(0, lambda: status_var.set("状态: 正在连接..."))

            start = time.time()
            result = manager.test_connection(
                'ssh',
                ip='192.0.2.1',  # 不可路由IP,会超时
                username='test',
                password='test',
                timeout=5
            )
            elapsed = time.time() - start

            root.after(0, lambda: status_var.set(f"状态: 完成 ({elapsed:.1f}秒)"))
            root.after(0, lambda: messagebox.showinfo("窗口2", f"连接完成!\n耗时: {elapsed:.1f}秒\n期间点击: {click_count[0]}次"))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    tk.Button(root, text="测试连接 (点击后立即点上面)", command=on_connect,
              font=("Arial", 12), bg="lightgreen", height=2).pack(pady=10, fill="x", padx=20)

    return root


# ========== 主程序 ==========
if __name__ == "__main__":
    print("="*70)
    print("手动测试 - 验证界面是否卡住")
    print("="*70)
    print("\n操作指南:")
    print("1. 会弹出两个窗口")
    print("2. 在两个窗口中分别点击 '测试连接' 按钮")
    print("3. 立即尝试点击 '点击测试' 按钮")
    print("4. 观察哪个窗口可以响应点击\n")
    print("预期结果:")
    print("- 窗口1 (原始版本): 会卡住,无法点击")
    print("- 窗口2 (异步版本): 可以正常点击")
    print("\n等待窗口出现...\n")

    # 创建两个窗口
    root1 = window1_original()
    root2 = window2_async()

    # 运行两个窗口
    # 注意: tkinter不支持多个mainloop,这里需要特殊处理
    # 所以我们只显示一个窗口,关闭后再显示下一个

    print("测试窗口1 (原始版本): 点击 '测试连接' 后尝试点击上面的按钮")
    print("如果点击不了,说明卡住了!\n")

    root1.mainloop()

    print("\n测试窗口2 (异步版本): 点击 '测试连接' 后尝试点击上面的按钮")
    print("这个应该可以点击!\n")

    root2.mainloop()

    print("\n测试完成!")
