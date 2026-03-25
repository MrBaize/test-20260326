#!/usr/bin/env python3
"""
异步连接协议使用示例 - 避免界面卡顿
"""

import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading

# 使用异步连接管理器
from async_connection_manager import AsyncConnectionManager


class ConnectionTestApp:
    """连接测试GUI应用 - 演示如何避免界面卡顿"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("连接协议测试 - 异步版本")
        self.root.geometry("600x500")
        
        self.manager = AsyncConnectionManager()
        
        # 创建UI
        self._create_ui()
    
    def _create_ui(self):
        """创建用户界面"""
        # 协议选择
        ttk.Label(self.root, text="协议类型:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.protocol_var = tk.StringVar(value="ssh")
        protocol_combo = ttk.Combobox(self.root, textvariable=self.protocol_var, 
                                       values=["ssh", "telnet", "ftp", "sftp", "serial"],
                                       state="readonly", width=15)
        protocol_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        # IP地址/串口号
        ttk.Label(self.root, text="IP地址/串口:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.host_var = tk.StringVar(value="192.168.1.100")
        ttk.Entry(self.root, textvariable=self.host_var, width=20).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # 端口
        ttk.Label(self.root, text="端口:").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.port_var = tk.StringVar(value="22")
        ttk.Entry(self.root, textvariable=self.port_var, width=8).grid(row=1, column=3, padx=5, pady=5, sticky="w")
        
        # 用户名
        ttk.Label(self.root, text="用户名:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.username_var = tk.StringVar(value="root")
        ttk.Entry(self.root, textvariable=self.username_var, width=20).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        # 密码
        ttk.Label(self.root, text="密码:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.password_var = tk.StringVar(value="password")
        ttk.Entry(self.root, textvariable=self.password_var, show="*", width=20).grid(row=3, column=1, padx=5, pady=5, sticky="w")
        
        # 超时设置
        ttk.Label(self.root, text="超时(秒):").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        self.timeout_var = tk.StringVar(value="10")
        ttk.Entry(self.root, textvariable=self.timeout_var, width=8).grid(row=2, column=3, padx=5, pady=5, sticky="w")
        
        # 按钮区域
        btn_frame = ttk.Frame(self.root)
        btn_frame.grid(row=4, column=0, columnspan=4, padx=5, pady=10)
        
        self.test_btn = ttk.Button(btn_frame, text="测试连接", command=self._on_test_connection)
        self.test_btn.pack(side=tk.LEFT, padx=5)
        
        self.connect_btn = ttk.Button(btn_frame, text="建立连接", command=self._on_connect)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_btn = ttk.Button(btn_frame, text="断开连接", command=self._on_disconnect)
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        # 进度条
        self.progress = ttk.Progressbar(self.root, mode='indeterminate', length=550)
        self.progress.grid(row=5, column=0, columnspan=4, padx=5, pady=5)
        
        # 状态标签
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, foreground="blue").grid(
            row=6, column=0, columnspan=4, padx=5, pady=5, sticky="w")
        
        # 日志区域
        ttk.Label(self.root, text="日志输出:").grid(row=7, column=0, padx=5, pady=5, sticky="w")
        self.log_text = scrolledtext.ScrolledText(self.root, width=70, height=15)
        self.log_text.grid(row=8, column=0, columnspan=4, padx=5, pady=5)
    
    def _log(self, message: str):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def _set_loading(self, loading: bool):
        """设置加载状态"""
        if loading:
            self.progress.start()
            self.test_btn.config(state="disabled")
            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="disabled")
        else:
            self.progress.stop()
            self.test_btn.config(state="normal")
            self.connect_btn.config(state="normal")
            self.disconnect_btn.config(state="normal")
    
    def _on_test_connection(self):
        """测试连接按钮点击"""
        protocol = self.protocol_var.get()
        host = self.host_var.get()
        port = int(self.port_var.get())
        username = self.username_var.get()
        password = self.password_var.get()
        timeout = int(self.timeout_var.get())
        
        self.status_var.set(f"正在测试 {protocol.upper()} 连接...")
        self._log(f"开始测试 {protocol.upper()} 连接: {host}:{port}")
        self._set_loading(True)
        
        def do_test():
            try:
                # 异步调用，不会阻塞GUI
                if protocol in ['ssh', 'telnet', 'ftp', 'sftp']:
                    result = self.manager.test_connection(
                        protocol, 
                        ip=host, 
                        port=port,
                        username=username,
                        password=password,
                        timeout=timeout
                    )
                else:  # serial
                    result = self.manager.test_connection(
                        protocol,
                        com_port=host,
                        baud_rate=9600,
                        timeout=timeout
                    )
                
                # 回到主线程更新UI
                self.root.after(0, lambda: self._on_test_complete(result))
            except Exception as e:
                self.root.after(0, lambda: self._on_test_complete({
                    'success': False,
                    'message': f'测试异常: {str(e)}'
                }))
        
        # 在后台线程执行
        threading.Thread(target=do_test, daemon=True).start()
    
    def _on_test_complete(self, result: dict):
        """测试完成回调"""
        self._set_loading(False)
        
        if result['success']:
            self.status_var.set("✓ 连接测试成功")
            self._log(f"✓ 测试成功: {result['message']}")
            messagebox.showinfo("测试结果", result['message'])
        else:
            self.status_var.set(f"✗ 连接测试失败")
            self._log(f"✗ 测试失败: {result['message']}")
            messagebox.showerror("测试结果", result['message'])
    
    def _on_connect(self):
        """建立连接按钮点击"""
        protocol = self.protocol_var.get()
        host = self.host_var.get()
        port = int(self.port_var.get())
        username = self.username_var.get()
        password = self.password_var.get()
        timeout = int(self.timeout_var.get())
        
        self.status_var.set(f"正在建立 {protocol.upper()} 连接...")
        self._log(f"开始建立 {protocol.upper()} 连接: {host}:{port}")
        self._set_loading(True)
        
        def do_connect():
            try:
                if protocol in ['ssh', 'telnet', 'ftp', 'sftp']:
                    result = self.manager.connect(
                        protocol,
                        ip=host,
                        port=port,
                        username=username,
                        password=password,
                        timeout=timeout
                    )
                else:  # serial
                    result = self.manager.connect(
                        protocol,
                        com_port=host,
                        baud_rate=9600,
                        timeout=timeout
                    )
                
                self.root.after(0, lambda: self._on_connect_complete(result))
            except Exception as e:
                self.root.after(0, lambda: self._on_connect_complete({
                    'success': False,
                    'message': f'连接异常: {str(e)}'
                }))
        
        threading.Thread(target=do_connect, daemon=True).start()
    
    def _on_connect_complete(self, result: dict):
        """连接完成回调"""
        self._set_loading(False)
        
        if result['success']:
            self.status_var.set("✓ 连接已建立")
            self._log(f"✓ 连接成功: {result['message']}")
        else:
            self.status_var.set(f"✗ 连接失败")
            self._log(f"✗ 连接失败: {result['message']}")
            messagebox.showerror("连接失败", result['message'])
    
    def _on_disconnect(self):
        """断开连接按钮点击"""
        protocol = self.protocol_var.get()
        
        self.status_var.set(f"正在断开 {protocol.upper()} 连接...")
        self._log(f"断开 {protocol.upper()} 连接")
        self._set_loading(True)
        
        def do_disconnect():
            try:
                result = self.manager.disconnect(protocol)
                self.root.after(0, lambda: self._on_disconnect_complete(result))
            except Exception as e:
                self.root.after(0, lambda: self._on_disconnect_complete({
                    'success': False,
                    'message': f'断开异常: {str(e)}'
                }))
        
        threading.Thread(target=do_disconnect, daemon=True).start()
    
    def _on_disconnect_complete(self, result: dict):
        """断开完成回调"""
        self._set_loading(False)
        
        if result['success']:
            self.status_var.set("✓ 连接已断开")
            self._log(f"✓ {result['message']}")
        else:
            self.status_var.set(f"✗ 断开失败")
            self._log(f"✗ {result['message']}")


def main():
    """主函数"""
    root = tk.Tk()
    app = ConnectionTestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
