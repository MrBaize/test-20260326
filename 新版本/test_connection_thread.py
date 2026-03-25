"""
连接卡死问题诊断脚本
用于测试SSH连接是否会阻塞主线程
"""

import sys
import time
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
import paramiko


class TestConnectionThread(QThread):
    """测试连接线程"""
    status_signal = pyqtSignal(str)
    success_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    
    def __init__(self, ip, port, username, password):
        super().__init__()
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
    
    def run(self):
        """后台执行连接"""
        try:
            self.status_signal.emit(f"线程启动，开始连接 {self.ip}...")
            
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.status_signal.emit("正在执行SSH连接...")
            
            ssh.connect(
                hostname=self.ip,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=5
            )
            
            self.status_signal.emit("连接成功！")
            self.success_signal.emit("连接成功")
            ssh.close()
            
        except Exception as e:
            self.error_signal.emit(f"连接失败: {str(e)}")


class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.connection_thread = None
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 状态标签
        self.status_label = QLabel("状态: 就绪")
        layout.addWidget(self.status_label)
        
        # 文本框
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("日志信息将显示在这里...")
        layout.addWidget(self.text_edit)
        
        # 主线程连接按钮（会阻塞）
        self.blocking_btn = QPushButton("🔴 主线程连接（会卡死）")
        self.blocking_btn.clicked.connect(self.blocking_connect)
        layout.addWidget(self.blocking_btn)
        
        # 后台线程连接按钮（不会阻塞）
        self.thread_btn = QPushButton("✅ 后台线程连接（推荐）")
        self.thread_btn.clicked.connect(self.thread_connect)
        layout.addWidget(self.thread_btn)
        
        # 清空按钮
        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(lambda: self.text_edit.clear())
        layout.addWidget(clear_btn)
        
        self.setLayout(layout)
        self.setWindowTitle("连接测试 - 点击按钮测试")
        self.resize(500, 400)
    
    def log(self, message):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.text_edit.append(f"[{timestamp}] {message}")
        # 强制刷新UI
        QApplication.processEvents()
    
    def blocking_connect(self):
        """主线程连接 - 会阻塞UI"""
        self.log("⚠️ 开始主线程连接（界面会卡死5秒）...")
        self.status_label.setText("状态: 主线程连接中...")
        
        # 强制刷新UI显示
        QApplication.processEvents()
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 使用一个不存在的IP，会超时5秒
            ssh.connect(
                hostname="192.168.999.999",  # 无效IP
                port=22,
                username="test",
                password="test",
                timeout=5
            )
            
            self.log("✓ 连接成功")
            ssh.close()
            
        except Exception as e:
            self.log(f"✗ 连接失败: {str(e)}")
        
        self.status_label.setText("状态: 就绪")
        self.log("主线程连接结束")
    
    def thread_connect(self):
        """后台线程连接 - 不会阻塞UI"""
        self.log("✓ 开始后台线程连接（界面不会卡死）...")
        self.status_label.setText("状态: 后台线程连接中...")
        
        # 创建连接线程
        self.connection_thread = TestConnectionThread(
            ip="192.168.999.999",  # 无效IP
            port=22,
            username="test",
            password="test"
        )
        
        # 连接信号
        self.connection_thread.status_signal.connect(self.log)
        self.connection_thread.success_signal.connect(self.on_success)
        self.connection_thread.error_signal.connect(self.on_error)
        
        # 启动线程
        self.connection_thread.start()
        self.log("✓ 线程已启动，可以继续操作界面")
    
    def on_success(self, message):
        """连接成功回调"""
        self.log(f"✓ {message}")
        self.status_label.setText("状态: 连接成功")
    
    def on_error(self, message):
        """连接失败回调"""
        self.log(f"✗ {message}")
        self.status_label.setText("状态: 连接失败")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
