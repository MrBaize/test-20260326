#!/usr/bin/env python3
"""
测试真正非阻塞的管理器

这个版本绝对不会卡住界面!
"""

import time
import tkinter as tk
from tkinter import ttk, messagebox


def test_nonblocking():
    """测试真正非阻塞版本"""
    from NONBLOCKING_MANAGER import NonBlockingConnectionManager

    manager = NonBlockingConnectionManager()
    root = tk.Tk()
    root.title("真正非阻塞版本测试")
    root.geometry("400x300")

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
        status_var.set("状态: 正在连接...")
        print(f"[非阻塞版本] 开始连接...")

        def callback(result):
            print(f"[非阻塞版本] 连接完成: {result['message']}")
            print(f"[非阻塞版本] 期间点击次数: {click_count[0]}")

            status_var.set(f"状态: {result['message']}")
            messagebox.showinfo("非阻塞版本",
                f"连接完成!\n\n"
                f"结果: {result['message']}\n"
                f"期间点击: {click_count[0]}次\n"
                f"如果点击次数 > 0, 说明界面没有卡住!")

        # 在后台线程连接,不等待结果
        manager.test_connection(
            'ssh',
            ip='192.0.2.1',  # 不可路由IP,会超时
            username='test',
            password='test',
            timeout=5,
            callback=callback
        )

        # 注意: 这里立即返回,不会等待!
        print("[非阻塞版本] test_connection 立即返回,没有阻塞!")

    tk.Button(root, text="测试连接 (立即返回,不卡住)", command=on_connect,
              font=("Arial", 12), bg="lightgreen", height=2).pack(pady=10, fill="x", padx=20)

    # 说明
    info_text = (
        "使用说明:\n"
        "1. 点击 '测试连接' 按钮\n"
        "2. 立即点击 '点击测试' 按钮\n"
        "3. 如果可以点击,说明界面不卡住!"
    )
    tk.Label(root, text=info_text, fg="gray").pack(pady=10)

    return root


if __name__ == "__main__":
    print("="*70)
    print("真正非阻塞版本测试")
    print("="*70)
    print("\n特点:")
    print("- 连接操作在后台线程执行")
    print("- test_connection 立即返回,不等待")
    print("- 界面完全不会卡住\n")
    print("操作:")
    print("1. 点击 '测试连接' 按钮")
    print("2. 立即尝试点击 '点击测试' 按钮")
    print("3. 应该可以正常点击!\n")

    root = test_nonblocking()
    root.mainloop()

    print("\n测试完成!")
