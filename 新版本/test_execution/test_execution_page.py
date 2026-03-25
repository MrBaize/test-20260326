from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTextEdit, QLabel, QFrame, QSplitter,
                             QComboBox, QLineEdit, QCheckBox, QSpinBox,
                             QListWidget, QListWidgetItem, QFileDialog,
                             QMessageBox, QProgressBar, QScrollArea,
                             QDialog, QDialogButtonBox, QFormLayout,
                             QTextBrowser, QGroupBox, QPlainTextEdit)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QStringListModel, QEvent
from PyQt6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat, QAction, QPalette, QKeyEvent
import serial
import serial.tools.list_ports
import paramiko
import time
import threading
import json
import os
from datetime import datetime

import re  # 高性能ANSI清理
import pyte  # 虚拟终端引擎

# 导入统一UI样式
from themes.ui_styles import (
    COLOR_PRIMARY_BG, COLOR_PANEL_BG, COLOR_INPUT_BG, COLOR_ACCENT,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_BORDER,
    COLOR_TERMINAL_BG, COLOR_TERMINAL_TEXT,
    get_common_stylesheet, get_success_button_style, get_danger_button_style,
    get_compact_button_style, get_icon_button_style, get_group_style
)

# 兼容旧代码的别名
STYLE_DARK_BG = COLOR_PRIMARY_BG
STYLE_PANEL_BG = COLOR_PANEL_BG
STYLE_INPUT_BG = COLOR_INPUT_BG
STYLE_ACCENT = COLOR_ACCENT
STYLE_SUCCESS = COLOR_SUCCESS
STYLE_WARNING = COLOR_WARNING
STYLE_ERROR = COLOR_ERROR
STYLE_TEXT = COLOR_TEXT
STYLE_TEXT_DIM = COLOR_TEXT_DIM
STYLE_BORDER = COLOR_BORDER


def get_common_style():
    """获取通用样式"""
    return get_common_stylesheet()


class SerialTerminal(QPlainTextEdit):
    """
    高性能串口终端控件 - 基于 pyte 虚拟终端引擎
    
    核心架构：
    1. pyte.Screen: 虚拟屏幕缓冲区（完整模拟 VT100 终端）
    2. pyte.Stream: 字节流解析器（处理控制字符和 ANSI 序列）
    3. 增量渲染：只更新变化的部分，避免全量刷新
    
    优势：
    - 完整支持 VT100/VT102 终端标准
    - 正确处理所有控制字符（\r, \n, \b 等）
    - 支持 ANSI 转义序列（颜色、光标移动等）
    - 性能优异（pyte 使用优化的正则）
    """
    
    command_entered = pyqtSignal(str)
    data_received = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # ========== 基础配置 ==========
        self.setReadOnly(True)
        self.setMaximumBlockCount(10000)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        
        # 禁用输入法
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)
        self.setAttribute(Qt.WidgetAttribute.WA_KeyCompression, False)
        
        # 样式设置
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0a0a0a;
                color: #7cfc00;
                border: 1px solid #2d4a6f;
                border-radius: 6px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                padding: 5px;
            }
        """)
        
        # ========== pyte 虚拟终端引擎（双缓冲架构）==========
        # WindTerm 风格：显示缓冲区和日志缓冲区分离
        
        # 1. 显示缓冲区（用于终端显示，实时更新）
        self.display_screen = pyte.Screen(200, 10000)
        self.display_stream = pyte.Stream(self.display_screen)
        
        # 2. 日志缓冲区（用于日志保存，独立更新）
        self.log_screen = pyte.Screen(200, 10000)
        self.log_stream = pyte.Stream(self.log_screen)
        
        # ========== 性能优化：增量更新 ==========
        self._last_display_lines = []
        self._last_saved_lines = []  # 上次保存到日志的行内容
        self._refresh_timer = QTimer()
        
        # 禁用初始滚动到底部
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh_display)
        self._refresh_delay = 16  # 60fps
        
        # ========== 日志管理（WindTerm风格）==========
        self.log_lines = []
        self.auto_save = True
        self.log_file = None
        self._permanent_log_buffer = []  # 存储(time, text)元组
        self._saved_buffer_count = 0  # 已保存到日志的缓冲区条目数
        
        # 延迟日志保存计时器（批量保存，避免频繁IO）
        self._log_save_timer = QTimer()
        self._log_save_timer.setSingleShot(True)
        self._log_save_timer.timeout.connect(self._save_pending_log)
        self._log_save_delay = 1000  # WindTerm风格：延迟 1000ms 批量保存
        self._pending_save_lines = None  # 待保存的内容
        
        # ========== 输入模式管理 ==========
        self.input_mode = False
        self.command_buffer = ""
        
        # ========== 键盘事件去重 ==========
        self._last_key_time = 0
        self._last_key_text = ""
        
        # ========== 自动滚动控制 ==========
        self._auto_scroll = False  # 初始不自动滚动，等待新数据
        self._is_initializing = True  # 初始化标志
        self.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        
        # 连接线程安全信号
        self.data_received.connect(self._on_data_received)
    
    # ==================== 数据接收与处理 ====================
    
    def _on_data_received(self, text):
        """线程安全的数据接收槽"""
        self.append_raw(text)
    
    def append_raw(self, text):
        """
        高性能文本追加 - WindTerm风格双缓冲架构
        
        数据流：
        1. 同时进入显示缓冲区（用于实时显示）
        2. 同时进入日志缓冲区（用于批量保存）
        
        关键改进：在接收时记录时间戳，保证日志时间准确性
        
        pyte 会自动处理：
        - \r: 光标移到行首
        - \n: 光标移到下一行
        - \b: 退格
        - ANSI 转义序列：颜色、光标移动等
        """
        if not text:
            return
        
        # 保存原始数据和时间戳（用于日志）
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._permanent_log_buffer.append((current_time, text))
        
        # WindTerm风格：双缓冲架构
        # 1. 更新显示缓冲区（实时显示）
        try:
            self.display_stream.feed(text)
        except Exception as e:
            print(f"[显示缓冲区错误] {e}")
            clean_text = text.replace('\x1b', '')
            self.display_stream.feed(clean_text)
        
        # 2. 更新日志缓冲区（批量保存）
        try:
            self.log_stream.feed(text)
        except Exception as e:
            print(f"[日志缓冲区错误] {e}")
            clean_text = text.replace('\x1b', '')
            self.log_stream.feed(clean_text)
        
        # 触发刷新（节流）
        if not self._refresh_timer.isActive():
            self._refresh_timer.start(self._refresh_delay)
    
    def _refresh_display(self):
        """
        刷新显示（WindTerm风格）
        
        显示逻辑：
        1. 从显示缓冲区获取内容（无时间戳）
        2. 终端显示保持原始SSH输出格式
        3. 日志从独立的日志缓冲区保存（批量延迟）
        """
        # 从显示缓冲区获取内容
        current_lines = list(self.display_screen.display)
        
        # 检查是否有变化
        if current_lines == self._last_display_lines:
            return
        
        # 去除右侧空白的行
        display_lines = []
        for line in current_lines:
            # 去除右侧空白，但保留至少一个空格（空行）
            stripped = line.rstrip()
            display_lines.append(stripped if stripped else '')
        
        # 设置文本（不带时间戳，保持原始格式）
        text = '\n'.join(display_lines)
        
        # 保存当前滚动位置
        scroll_bar = self.verticalScrollBar()
        current_pos = scroll_bar.value()
        max_pos = scroll_bar.maximum()
        
        # 设置文本
        self.setPlainText(text)
        
        # 初始化完成后，恢复用户滚动位置
        if not self._is_initializing:
            if current_pos < max_pos:
                scroll_bar.setValue(current_pos)
        
        self._last_display_lines = current_lines
        
        # WindTerm风格：延迟批量保存日志（从独立的日志缓冲区）
        if self.auto_save and self.log_file:
            # 从日志缓冲区获取内容（可能与显示缓冲区不同）
            log_lines = list(self.log_screen.display)
            cleaned_log_lines = [line.rstrip() for line in log_lines]
            
            self._pending_save_lines = cleaned_log_lines
            # 重置计时器（如果期间有新数据，重新计时）
            if self._log_save_timer.isActive():
                self._log_save_timer.stop()
            self._log_save_timer.start(self._log_save_delay)
    
    def _scroll_to_bottom(self):
        """滚动到底部"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
    
    def _on_scroll_changed(self, value):
        """检测用户手动滚动，禁用自动滚动"""
        # 如果用户滚动到接近底部（90%位置），恢复自动滚动
        scroll_bar = self.verticalScrollBar()
        if value >= scroll_bar.maximum() * 0.9:
            self._auto_scroll = True
        else:
            self._auto_scroll = False
    
    # ==================== 输入处理 ====================
    
    def set_input_mode(self, enabled):
        """设置输入模式"""
        self.input_mode = enabled
        if enabled:
            self.setFocus()
    
    def keyPressEvent(self, event: QKeyEvent):
        """键盘事件处理"""
        # 忽略自动重复
        if event.isAutoRepeat():
            event.accept()
            return
        
        if not self.input_mode:
            event.ignore()
            return
        
        key = event.key()
        text = event.text()
        modifiers = event.modifiers()
        
        # 去重检查
        current_time = time.time() * 1000
        if text and text == self._last_key_text and (current_time - self._last_key_time) < 50:
            event.accept()
            return
        
        if text:
            self._last_key_time = current_time
            self._last_key_text = text
        
        # Ctrl+C - 中断
        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_C:
            self.command_entered.emit("\x03")
            event.accept()
            return
        
        # Ctrl+L - 清屏
        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_L:
            self.clear_screen()
            self.command_entered.emit("\x0c")
            event.accept()
            return
        
        # Enter/Return
        if key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:
            self.command_entered.emit("\r")
            self._last_key_text = ""
            event.accept()
            return
        
        # Backspace
        if key == Qt.Key.Key_Backspace:
            self.command_entered.emit("\x7f")  # DEL 字符（SSH标准）
            event.accept()
            return
        
        # Tab
        if key == Qt.Key.Key_Tab:
            self.command_entered.emit("\t")
            event.accept()
            return
        
        # 方向键（ANSI序列）
        arrow_keys = {
            Qt.Key.Key_Up: "\x1b[A",
            Qt.Key.Key_Down: "\x1b[B",
            Qt.Key.Key_Right: "\x1b[C",
            Qt.Key.Key_Left: "\x1b[D"
        }
        if key in arrow_keys:
            self.command_entered.emit(arrow_keys[key])
            event.accept()
            return
        
        # 普通字符
        if text:
            self.command_entered.emit(text)
            event.accept()
            return
        
        event.ignore()
    
    def inputMethodEvent(self, event):
        """阻止输入法"""
        event.ignore()
    
    def event(self, event):
        """过滤输入法查询"""
        if event.type() == QEvent.Type.InputMethodQuery:
            event.ignore()
            return True
        return super().event(event)
    
    # ==================== 辅助方法 ====================
    
    def clear_screen(self):
        """清屏（双缓冲）"""
        # 重置显示缓冲区
        self.display_screen = pyte.Screen(200, 10000)
        self.display_stream = pyte.Stream(self.display_screen)
        
        # 重置日志缓冲区
        self.log_screen = pyte.Screen(200, 10000)
        self.log_stream = pyte.Stream(self.log_screen)
        
        self._last_display_lines = []
        self._last_saved_lines = []
        self.clear()
        self.log_lines.clear()
    
    def resize_screen(self, cols, rows):
        """调整屏幕大小（双缓冲）"""
        self.display_screen.resize(rows, cols)
        self.log_screen.resize(rows, cols)
    
    def get_all_text(self):
        """获取所有文本"""
        return self.toPlainText()
    
    def _save_to_log(self, text):
        """保存到日志文件（已废弃，改用 _save_display_to_log）"""
        pass
    
    def _save_pending_log(self):
        """延迟保存待处理的日志内容"""
        if self._pending_save_lines is not None:
            self._save_display_to_log(self._pending_save_lines)
            self._pending_save_lines = None
    
    def _save_display_to_log(self, display_lines):
        """
        批量保存SSH输出到日志（程序消息已直接写入）
        
        参数:
            display_lines: 日志缓冲区的行列表（SSH输出，不带时间戳）
        
        策略：
        - 只保存新增的行（追加模式）
        - 批量写入，减少IO
        - 每行使用自己的时间戳
        """
        if not self.log_file:
            return
        
        try:
            # 只保存新增的行
            if len(display_lines) <= len(self._last_saved_lines):
                return
            
            new_lines = display_lines[len(self._last_saved_lines):]
            
            if not new_lines:
                return
            
            # 批量写入日志文件
            with open(self.log_file, 'a', encoding='utf-8') as f:
                for line in new_lines:
                    line = line.rstrip()
                    if line:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        f.write(f"[{timestamp}] {line}\n")
            
            # 更新已保存行数
            self._last_saved_lines = display_lines.copy()
            
        except Exception as e:
            print(f"保存日志失败: {e}")
    
    def _clean_ansi_for_log(self, text):
        """清理 ANSI 转义序列，用于日志保存"""
        # ANSI 转义序列正则表达式（更全面）
        ansi_escape = re.compile(
            r'\x1b\[[0-9;?]*[a-zA-Z]|'  # CSI 序列（颜色、光标移动等）
            r'\x1b\][^\x07]*\x07|'       # OSC 序列（窗口标题等）
            r'\x1b[()][AB012]|'          # 字符集选择
            r'\x1b[=>78]|'               # 其他控制
            r'\x1b\[[0-9;]*[JKhlmsu]|'   # 清屏/模式设置
            r'\x1b\?[0-9;]*[a-zA-Z]|'    # 扩展序列 (?2004l 等)
            r'\x1b\[[0-9;]*[a-zA-Z][a-zA-Z]|'  # 双重字母结尾
        )
        return ansi_escape.sub('', text)
    
    def set_auto_save(self, enabled, filepath=None):
        """设置自动保存"""
        self.auto_save = enabled
        if filepath:
            self.log_file = filepath
    
    def set_log_delay(self, delay_ms):
        """
        设置日志保存延迟（批量保存优化）
        
        参数:
            delay_ms: 延迟毫秒数（建议2000ms）
                     - SSH输出批量保存，减少IO操作
                     - 程序消息直接保存，不受延迟影响
        """
        self._log_save_delay = delay_ms
    
    def get_timestamp(self):
        """获取时间戳"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def append_output(self, text, with_timestamp=False, auto_scroll=True):
        """
        追加程序消息到终端和日志（分离处理）
        
        WindTerm风格：
        1. 显示：进入显示缓冲区（在终端显示）
        2. 日志：直接写入日志文件（不进入日志缓冲区，避免和SSH输出混合）
        
        这用于显示程序自身的信息（如连接状态、执行状态等）。
        时间戳只在日志文件中添加，终端保持工整格式。
        
        参数:
            auto_scroll: 是否自动滚动到底部，默认True
        """
        # 1. 进入显示缓冲区（在终端显示）
        self.append_raw("\r" + text + "\r\n")
        
        # 设置自动滚动（仅当是串口数据时启用，程序消息不启用）
        if auto_scroll:
            self._auto_scroll = True
        
        # 2. 直接写入日志文件（不进入日志缓冲区，避免穿插）
        if self.log_file and self.auto_save:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 移除空行和纯空白行，去除前导空格
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                for line in lines:
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(f"[{timestamp}] {line}\n")
            except Exception as e:
                print(f"记录日志失败: {e}")
    
    def append_info(self, text):
        """追加信息（分离处理）"""
        self.append_output(f"ℹ {text}", auto_scroll=False)
    
    def append_error(self, text):
        """追加错误（分离处理）"""
        self.append_output(f"✗ {text}", auto_scroll=False)
    
    def append_warning(self, text):
        """追加警告（分离处理）"""
        self.append_output(f"⚠ {text}", auto_scroll=False)
    
    def append_command(self, text):
        """追加命令（分离处理）"""
        self.append_output(f"> {text}", auto_scroll=False)
    
    def append_response(self, text):
        """追加响应（兼容旧接口）"""
        self.append_raw(text)
    
    def search_text(self, keyword):
        """搜索文本"""
        matches = []
        text = self.toPlainText()
        for i, line in enumerate(text.split('\n')):
            if keyword in line:
                matches.append(i)
        return matches


class ConnectionThread(QThread):
    """设备连接线程 - 避免阻塞UI"""
    
    connection_success = pyqtSignal(str, object)  # 协议类型, 连接对象
    connection_failed = pyqtSignal(str)  # 错误信息
    status_update = pyqtSignal(str)  # 状态更新
    
    def __init__(self, protocol, params):
        super().__init__()
        self.protocol = protocol
        self.params = params
        self.running = True
    
    def run(self):
        """后台执行连接"""
        try:
            print(f"[连接线程] 开始执行，协议: {self.protocol}")
            if self.protocol == "ssh":
                self._connect_ssh()
            elif self.protocol == "serial":
                self._connect_serial()
            elif self.protocol == "telnet":
                self._connect_telnet()
            print("[连接线程] 执行完成")
        except Exception as e:
            print(f"[连接线程] 异常: {str(e)}")
            if self.running:
                self.connection_failed.emit(f"连接失败: {str(e)}")
    
    def _connect_ssh(self):
        """SSH连接"""
        import paramiko
        
        ip = self.params.get('ip', '')
        port = int(self.params.get('port', 22))
        username = self.params.get('username', '')
        password = self.params.get('password', '')
        
        print(f"[SSH连接] 准备连接 {username}@{ip}:{port}")
        self.status_update.emit(f"正在连接 {username}@{ip}:{port}...")
        
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            print("[SSH连接] 开始执行SSH连接...")
            # 在后台线程执行连接
            ssh_client.connect(
                hostname=ip,
                port=port,
                username=username,
                password=password,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10
            )
            print("[SSH连接] SSH连接成功，创建shell通道...")
            
            # 创建shell通道
            ssh_channel = ssh_client.invoke_shell(term='xterm', width=80, height=24)
            ssh_channel.settimeout(1)
            print("[SSH连接] Shell通道创建成功")
            
            if self.running:
                print("[SSH连接] 发送连接成功信号")
                self.connection_success.emit("ssh", (ssh_client, ssh_channel))
                
        except paramiko.AuthenticationException as e:
            print(f"[SSH连接] 认证失败: {str(e)}")
            if self.running:
                self.connection_failed.emit("SSH认证失败，请检查用户名和密码")
        except paramiko.SSHException as e:
            print(f"[SSH连接] SSH异常: {str(e)}")
            if self.running:
                self.connection_failed.emit(f"SSH连接失败: {str(e)}")
        except Exception as e:
            print(f"[SSH连接] 其他异常: {str(e)}, 类型: {type(e).__name__}")
            if self.running:
                self.connection_failed.emit(f"连接失败: {str(e)}")
    
    def _connect_serial(self):
        """串口连接"""
        import serial
        
        port_name = self.params.get('com_port', '')
        baudrate = int(self.params.get('baud_rate', 115200))
        
        self.status_update.emit(f"正在连接串口 {port_name}...")
        
        try:
            serial_client = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            
            if self.running:
                self.connection_success.emit("serial", serial_client)
                
        except Exception as e:
            if self.running:
                self.connection_failed.emit(f"串口连接失败: {str(e)}")
    
    def _connect_telnet(self):
        """Telnet连接"""
        from connection_protocols.telnet_client import TelnetClient
        
        ip = self.params.get('ip', '')
        port = int(self.params.get('port', 23))
        username = self.params.get('username', '')
        password = self.params.get('password', '')
        
        self.status_update.emit(f"正在连接 Telnet {ip}:{port}...")
        
        try:
            telnet_client = TelnetClient()
            result = telnet_client.connect(ip, username, password, port, timeout=10)
            
            if result.get('success'):
                if self.running:
                    self.connection_success.emit("telnet", telnet_client)
            else:
                if self.running:
                    self.connection_failed.emit(result.get('message', 'Telnet连接失败'))
        except Exception as e:
            if self.running:
                self.connection_failed.emit(f"Telnet连接失败: {str(e)}")
    
    def stop(self):
        """停止连接"""
        self.running = False


class CommandExecutor(QThread):
    """命令执行线程"""
    
    command_sent = pyqtSignal(str)
    response_received = pyqtSignal(str)
    execution_finished = pyqtSignal(bool, str)
    progress_updated = pyqtSignal(int, int)
    status_updated = pyqtSignal(str)
    execution_started = pyqtSignal()  # 执行开始信号
    execution_completed = pyqtSignal()  # 执行完成信号
    
    def __init__(self, serial_client, ssh_channel, telnet_client, commands, loop_count, loop_delay,
                 wait_complete_enabled, wait_keyword, wait_timeout, wait_failure_action,
                 stop_enabled, stop_keyword, stop_action, serial_execute=False):
        super().__init__()
        self.serial_client = serial_client
        self.ssh_channel = ssh_channel
        self.telnet_client = telnet_client  # Telnet客户端
        self.commands = commands
        self.loop_count = loop_count
        self.loop_delay = loop_delay
        self.wait_complete_enabled = wait_complete_enabled
        self.wait_keyword = wait_keyword
        self.wait_timeout = wait_timeout
        self.wait_failure_action = wait_failure_action
        self.stop_enabled = stop_enabled
        self.stop_keyword = stop_keyword
        self.stop_action = stop_action
        self.serial_execute = serial_execute  # 串行执行模式
        self.running = True
        self.response_buffer = ""
    
    def run(self):
        success_count = 0
        fail_count = 0
        self.execution_log = []  # 执行日志缓存

        # 判断是否需要等待响应
        # 串行模式 或 开启了等待完成，都需要等待响应
        need_wait_response = self.serial_execute or self.wait_complete_enabled
        
        # 通知UI开始执行
        self.execution_started.emit()
        
        try:
            for loop in range(1, self.loop_count + 1):
                if not self.running:
                    break
                
                self.progress_updated.emit(loop, self.loop_count)
                
                # 串行模式：缓存状态消息，不实时显示
                if self.serial_execute:
                    self.execution_log.append(f"▶ 正在执行第 {loop}/{self.loop_count} 轮...")
                else:
                    self.status_updated.emit(f"▶ 正在执行第 {loop}/{self.loop_count} 轮...")
                
                for cmd in self.commands:
                    if not self.running:
                        break
                    
                    self.command_sent.emit(cmd)
                    try:
                        # 优先使用SSH发送
                        if self.ssh_channel:
                            self.ssh_channel.send(cmd + '\n')
                        # 其次使用Telnet发送
                        elif self.telnet_client and self.telnet_client.connected:
                            result = self.telnet_client.send_command(cmd, wait_time=0.1)
                            if result.get('success'):
                                output = result.get('output', '')
                                self.response_buffer += output
                                self.response_received.emit(output)
                        # 最后使用串口发送
                        elif self.serial_client:
                            command_bytes = cmd.encode('utf-8') + b'\r\n'
                            self.serial_client.write(command_bytes)
                        else:
                            self.execution_finished.emit(False, "未连接设备")
                            return
                    except Exception as e:
                        self.execution_finished.emit(False, f"发送命令失败: {str(e)}")
                        return
                    
                    # 串行执行模式：每个命令后都等待响应完成
                    if self.serial_execute:
                        keyword_found = False
                        start_time = time.time()
                        
                        # 如果用户配置了关键字则使用，否则使用#作为默认关键字（SSH提示符）
                        wait_keyword = self.wait_keyword if self.wait_complete_enabled else "#"
                        
                        while self.running and not keyword_found:
                            try:
                                # SSH读取 - 仅当没有独立的SSH读取线程时
                                if self.ssh_channel and not hasattr(self, 'ssh_thread') or (hasattr(self, 'ssh_thread') and not self.ssh_thread.is_alive()):
                                    if self.ssh_channel.recv_ready():
                                        data = self.ssh_channel.recv(8192)
                                        if data:
                                            text = data.decode('utf-8', errors='ignore')
                                            self.response_buffer += text
                                            self.response_received.emit(text)
                                            
                                            # 调试：打印收到的内容
                                            print(f"[串行执行] SSH收到: {text[:100]}")
                                    
                                    if self.ssh_channel.recv_stderr_ready():
                                        data = self.ssh_channel.recv_stderr(8192)
                                        if data:
                                            text = data.decode('utf-8', errors='ignore')
                                            self.response_buffer += text
                                            self.response_received.emit(text)
                                # 串口读取
                                elif self.serial_client and self.serial_client.in_waiting > 0:
                                    data = self.serial_client.read(self.serial_client.in_waiting)
                                    text = data.decode('utf-8', errors='replace')
                                    self.response_buffer += text
                                    self.response_received.emit(text)
                                # Telnet读取
                                elif self.telnet_client and self.telnet_client.connected:
                                    result = self.telnet_client.read_output()
                                    if result.get('success'):
                                        output = result.get('output', '')
                                        if output:
                                            self.response_buffer += output
                                            self.response_received.emit(output)
                                
                                if self.stop_enabled and self.stop_keyword:
                                    if self.stop_keyword in self.response_buffer:
                                        if self.stop_action == 0:
                                            self.execution_finished.emit(False, f"检测到停止条件: {self.stop_keyword}")
                                            return
                                        else:
                                            log_msg = f"⚠ 检测到停止条件: {self.stop_keyword}，继续执行"
                                            if self.serial_execute:
                                                self.execution_log.append(log_msg)
                                            else:
                                                self.status_updated.emit(log_msg)
                                            self.response_buffer = ""
                                
                                # 检查关键字
                                if wait_keyword and wait_keyword in self.response_buffer:
                                    print(f"[串行执行] 找到关键字: {wait_keyword}")
                                    keyword_found = True
                                    break
                                
                                # 超时检测
                                if self.wait_complete_enabled:
                                    timeout = self.wait_timeout
                                else:
                                    timeout = self.loop_delay * 2  # 默认等待loop_delay的2倍
                                
                                if (time.time() - start_time) * 1000 > timeout:
                                    print(f"[串行执行] 超时，当前buffer: {self.response_buffer[:200]}")
                                    if self.wait_complete_enabled and self.wait_failure_action == 2:
                                        self.execution_finished.emit(False, f"等待关键字超时: {wait_keyword}")
                                        return
                                    else:
                                        # 超时但不是严重错误，继续下一条
                                        log_msg = "⚠ 命令超时，跳过继续"
                                        if self.serial_execute:
                                            self.execution_log.append(log_msg)
                                        else:
                                            self.status_updated.emit(log_msg)
                                        break
                                
                                time.sleep(0.01)
                            except Exception as e:
                                self.response_received.emit(f"读取错误: {str(e)}\n")
                                break
                        
                        if keyword_found:
                            self.response_buffer = ""
                            success_count += 1
                        else:
                            fail_count += 1
                    
                    # 原有等待完成模式（仅当未开启串行执行时）
                    elif self.wait_complete_enabled and self.wait_keyword:
                        keyword_found = False
                        start_time = time.time()
                        
                        while self.running and not keyword_found:
                            try:
                                if self.serial_client.in_waiting > 0:
                                    data = self.serial_client.read(self.serial_client.in_waiting)
                                    text = data.decode('utf-8', errors='replace')
                                    self.response_buffer += text
                                    self.response_received.emit(text)
                                    
                                    if self.stop_enabled and self.stop_keyword:
                                        if self.stop_keyword in self.response_buffer:
                                            if self.stop_action == 0:
                                                self.execution_finished.emit(False, f"检测到停止条件: {self.stop_keyword}")
                                                return
                                            else:
                                                self.status_updated.emit(f"⚠ 检测到停止条件: {self.stop_keyword}，继续执行")
                                                self.response_buffer = ""
                                    
                                if self.wait_keyword in self.response_buffer:
                                    keyword_found = True
                                    break

                                if (time.time() - start_time) * 1000 > self.wait_timeout:
                                    if self.wait_failure_action == 0:
                                        continue
                                    elif self.wait_failure_action == 1:
                                        self.status_updated.emit(f"⚠ 命令超时，跳过继续")
                                        break
                                    else:
                                        self.execution_finished.emit(False, f"等待关键字超时: {self.wait_keyword}")
                                        return
                                
                                time.sleep(0.01)
                            except Exception as e:
                                self.response_received.emit(f"读取错误: {str(e)}\n")
                                break
                        
                        # 统计成功/失败
                        if keyword_found:
                            self.response_buffer = ""
                            success_count += 1
                        else:
                            # 超时且未找到关键字
                            if self.wait_failure_action == 1:
                                fail_count += 1
                    else:
                        # 普通模式：等待loop_delay毫秒，默认算作成功
                        if self.loop_delay > 0:
                            time.sleep(self.loop_delay / 1000.0)
                        success_count += 1
                    
                    # 处理停止条件（串行模式缓存消息）
                    if self.stop_enabled and self.stop_keyword:
                        if self.stop_keyword in self.response_buffer:
                            if self.stop_action == 0:
                                self.execution_finished.emit(False, f"检测到停止条件: {self.stop_keyword}")
                                return
                            else:
                                log_msg = f"⚠ 检测到停止条件: {self.stop_keyword}，继续执行"
                                if self.serial_execute:
                                    self.execution_log.append(log_msg)
                                else:
                                    self.status_updated.emit(log_msg)
                    
                    if self.loop_delay > 0:
                        time.sleep(self.loop_delay / 1000.0)
                
                if self.loop_delay > 0 and loop < self.loop_count:
                    time.sleep(self.loop_delay / 1000.0)
            
            # 等待命令完成输出（最后一条命令需要额外等待时间）
            if self.wait_complete_enabled and self.wait_keyword:
                # 如果开启了等待完成，等待3秒让最后输出完成
                time.sleep(3)
            elif not self.wait_complete_enabled:
                # 如果没有开启等待完成，等待2秒让命令完成
                time.sleep(2)
            
            # 通知UI执行即将完成，准备恢复串口读取
            self.execution_completed.emit()
            
            self.execution_finished.emit(True, f"✓ 执行完成！成功: {success_count}, 失败: {fail_count}")
        
        except Exception as e:
            self.execution_finished.emit(False, f"执行错误: {str(e)}")
    
    def stop(self):
        self.running = False


class TemplateDialog(QDialog):
    def __init__(self, parent=None, template_data=None):
        super().__init__(parent)
        self.template_data = template_data or {}
        self.setStyleSheet(get_common_style())
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("编辑模板")
        self.setMinimumSize(450, 350)
        
        layout = QFormLayout(self)
        layout.setSpacing(10)
        
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.template_data.get("name", ""))
        self.name_edit.setPlaceholderText("输入模板名称...")
        layout.addRow("模板名称:", self.name_edit)
        
        self.commands_edit = QTextEdit()
        self.commands_edit.setPlaceholderText("每行一条命令...")
        self.commands_edit.setText(self.template_data.get("commands", ""))
        layout.addRow("命令列表:", self.commands_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_data(self):
        return {
            "name": self.name_edit.text(),
            "commands": self.commands_edit.toPlainText()
        }


class TestExecutionPage(QWidget):
    """测试执行器页面"""
    
    def __init__(self):
        super().__init__()
        self.setStyleSheet(get_common_style())
        
        self.serial_client = None
        self.serial_thread = None
        self.ssh_client = None
        self.ssh_channel = None
        self.telnet_client = None  # Telnet客户端
        self.telnet_thread = None  # Telnet读取线程
        self.running = False
        self.command_executor = None
        self.connection_thread = None  # 连接线程
        self.serial_read_paused = False  # 串行执行时暂停串口读取
        self.ssh_read_paused = False  # 串行执行时暂停SSH读取
        self.ssh_echo_mode = False  # SSH字符回显模式
        self.timer = QTimer()
        self.timer.start_time = None
        self.success_count = 0
        self.fail_count = 0
        
        self.device_configs = self.load_device_configs()
        self.templates = self.load_templates()
        
        self.init_ui()
    
    def load_device_configs(self):
        config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "device_configs.json")
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def load_templates(self):
        template_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates.json")
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def save_templates(self):
        template_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates.json")
        try:
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(self.templates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"无法保存模板: {str(e)}")
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # 左侧 - 终端显示区域
        left_widget = self.create_terminal_panel()
        main_layout.addWidget(left_widget, 2)
        
        # 右侧 - 命令执行区域
        right_widget = self.create_control_panel()
        main_layout.addWidget(right_widget, 1)
        
        self.setLayout(main_layout)
        
        self.timer.timeout.connect(self.update_timer)
        
        # 初始化默认日志
        self.setup_default_log()
    
    def create_terminal_panel(self):
        """创建串口终端面板"""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {STYLE_DARK_BG};
                border-radius: 8px;
                border: 1px solid {STYLE_BORDER};
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # ==================== 设备连接区域 ====================
        conn_group = QGroupBox("设备连接")
        conn_group.setStyleSheet(f"""
            QGroupBox {{
                color: {STYLE_TEXT};
                border: 1px solid {STYLE_BORDER};
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 14px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {STYLE_ACCENT};
            }}
        """)
        
        conn_layout = QHBoxLayout()
        conn_layout.setSpacing(8)
        
        # 设备选择 - 使用紧凑标签
        conn_layout.addWidget(QLabel("设备"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(120)
        # 填充设备列表
        if self.device_configs:
            self.device_combo.addItems(list(self.device_configs.keys()))
        else:
            self.device_combo.addItem("未配置设备")
        self.device_combo.currentTextChanged.connect(self.on_device_changed)
        conn_layout.addWidget(self.device_combo)
        
        conn_layout.addWidget(QLabel("协议"))
        self.protocol_combo = QComboBox()
        self.protocol_combo.setMinimumWidth(80)
        self.protocol_combo.currentIndexChanged.connect(self.on_protocol_changed)
        conn_layout.addWidget(self.protocol_combo)
        
        # 参数显示（紧凑）
        self.param_label = QLabel("未选择")
        self.param_label.setStyleSheet("color: #7F8C8D; font-size: 11px; padding: 2px 6px; background: #F5F9FC; border-radius: 3px;")
        conn_layout.addWidget(self.param_label)
        
        conn_layout.addStretch()
        
        # 刷新按钮 - 使用统一图标按钮样式
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setToolTip("刷新")
        self.refresh_btn.setFixedSize(32, 28)
        self.refresh_btn.setStyleSheet(get_icon_button_style(32))
        self.refresh_btn.clicked.connect(self.refresh_ports)
        conn_layout.addWidget(self.refresh_btn)
        
        # 连接/断开按钮组
        btn_group_layout = QHBoxLayout()
        btn_group_layout.setSpacing(8)
        
        self.connect_btn = QPushButton("连接")
        self.connect_btn.setToolTip("连接")
        self.connect_btn.setMinimumWidth(70)
        self.connect_btn.setStyleSheet(get_success_button_style())
        self.connect_btn.clicked.connect(self.toggle_connection)
        btn_group_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("断开")
        self.disconnect_btn.setToolTip("断开")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.setMinimumWidth(70)
        self.disconnect_btn.setStyleSheet(get_danger_button_style())
        self.disconnect_btn.clicked.connect(self.disconnect)
        btn_group_layout.addWidget(self.disconnect_btn)
        
        conn_layout.addLayout(btn_group_layout)
        
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)
        
        # ==================== 终端显示区域 ====================
        terminal_group = QGroupBox("终端输出")
        terminal_group.setStyleSheet(f"""
            QGroupBox {{
                color: {STYLE_TEXT};
                border: 1px solid {STYLE_BORDER};
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 14px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {STYLE_ACCENT};
            }}
        """)
        
        terminal_layout = QVBoxLayout()
        terminal_layout.setSpacing(5)
        
        # 终端工具栏（紧凑）
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        
        # 搜索框（紧凑）
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索...")
        self.search_input.setFixedWidth(120)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {STYLE_INPUT_BG};
                color: {STYLE_TEXT};
                border: 1px solid {STYLE_BORDER};
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: {STYLE_ACCENT};
            }}
        """)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        toolbar.addWidget(self.search_input)
        
        toolbar.addStretch()
        
        # 日志操作按钮（紧凑）
        self.auto_save_check = QCheckBox("自动保存")
        self.auto_save_check.setChecked(True)
        self.auto_save_check.setStyleSheet("color: #7F8C8D; font-size: 11px;")
        self.auto_save_check.stateChanged.connect(self.on_auto_save_changed)
        toolbar.addWidget(self.auto_save_check)
        
        # 日志操作按钮组
        log_btn_layout = QHBoxLayout()
        log_btn_layout.setSpacing(4)
        
        self.save_log_btn = QPushButton("保存")
        self.save_log_btn.setToolTip("保存日志")
        self.save_log_btn.setMinimumWidth(50)
        self.save_log_btn.setStyleSheet(get_compact_button_style())
        self.save_log_btn.clicked.connect(self.save_log)
        log_btn_layout.addWidget(self.save_log_btn)
        
        self.copy_log_btn = QPushButton("复制")
        self.copy_log_btn.setToolTip("复制")
        self.copy_log_btn.setMinimumWidth(50)
        self.copy_log_btn.setStyleSheet(get_compact_button_style())
        self.copy_log_btn.clicked.connect(self.copy_log)
        log_btn_layout.addWidget(self.copy_log_btn)
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setToolTip("清空")
        self.clear_btn.setMinimumWidth(50)
        self.clear_btn.setStyleSheet(get_compact_button_style())
        self.clear_btn.clicked.connect(self.clear_terminal)
        log_btn_layout.addWidget(self.clear_btn)
        
        toolbar.addLayout(log_btn_layout)
        
        terminal_layout.addLayout(toolbar)
        
        # 终端
        self.terminal = SerialTerminal()
        self.terminal.append_output("═══ 串口终端就绪 ═══")
        self.terminal.append_output("请选择设备并连接开始测试...")
        
        # 初始化完成，允许自动滚动
        self.terminal._is_initializing = False
        terminal_layout.addWidget(self.terminal)

        # 连接终端命令输入信号（确保只连接一次）
        try:
            self.terminal.command_entered.disconnect()
        except:
            pass
        self.terminal.command_entered.connect(self.send_command)
        
        terminal_group.setLayout(terminal_layout)
        
        # 终端显示区域
        layout.addWidget(terminal_group)
        
        panel.setLayout(layout)
        
        return panel
    
    def create_control_panel(self):
        """创建右侧命令控制面板"""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {STYLE_PANEL_BG};
                border-radius: 8px;
                border: 1px solid {STYLE_BORDER};
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # ==================== 命令执行区域 ====================
        exec_group = QGroupBox("命令执行")
        exec_group.setStyleSheet(f"""
            QGroupBox {{
                color: {STYLE_TEXT};
                border: 1px solid {STYLE_BORDER};
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 14px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {STYLE_ACCENT};
            }}
        """)
        
        exec_layout = QVBoxLayout()
        exec_layout.setSpacing(8)
        
        # 命令输入
        cmd_label = QLabel("命令列表（每行一条）:")
        cmd_label.setStyleSheet(f"color: {STYLE_TEXT_DIM}; font-weight: normal;")
        exec_layout.addWidget(cmd_label)
        
        self.command_text = QTextEdit()
        self.command_text.setPlaceholderText("输入命令，每行一条...")
        self.command_text.setMinimumHeight(100)
        self.command_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #0a0a0a;
                color: #00ff00;
                border: 1px solid {STYLE_BORDER};
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                padding: 5px;
            }}
        """)
        exec_layout.addWidget(self.command_text)
        
        # ==================== 动态参数区域 ====================
        params_group = QGroupBox("动态参数")
        params_group.setStyleSheet(f"""
            QGroupBox {{
                color: {STYLE_TEXT};
                border: 1px solid {STYLE_BORDER};
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {STYLE_WARNING};
            }}
        """)
        
        params_layout = QVBoxLayout()
        params_layout.setSpacing(4)
        
        params_hint = QLabel("💡 使用 $A $B $C 变量，如: ping $A -c $B")
        params_hint.setStyleSheet(f"color: {STYLE_TEXT_DIM}; font-weight: normal; font-size: 10px;")
        params_layout.addWidget(params_hint)
        
        # 参数输入行
        params_row = QHBoxLayout()
        params_row.setSpacing(8)
        
        params_row.addWidget(QLabel("$A:"))
        self.param_a_input = QLineEdit()
        self.param_a_input.setPlaceholderText("IP/范围/列表")
        self.param_a_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0a0a0a;
                color: #00ff00;
                border: 1px solid {STYLE_BORDER};
                border-radius: 3px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 3px 6px;
            }}
        """)
        params_row.addWidget(self.param_a_input)
        
        params_row.addWidget(QLabel("$B:"))
        self.param_b_input = QLineEdit()
        self.param_b_input.setPlaceholderText("数字/范围/列表")
        self.param_b_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0a0a0a;
                color: #00ff00;
                border: 1px solid {STYLE_BORDER};
                border-radius: 3px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 3px 6px;
            }}
        """)
        params_row.addWidget(self.param_b_input)
        
        params_row.addWidget(QLabel("$C:"))
        self.param_c_input = QLineEdit()
        self.param_c_input.setPlaceholderText("网卡/列表")
        self.param_c_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0a0a0a;
                color: #00ff00;
                border: 1px solid {STYLE_BORDER};
                border-radius: 3px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 3px 6px;
            }}
        """)
        params_row.addWidget(self.param_c_input)
        
        params_layout.addLayout(params_row)
        params_group.setLayout(params_layout)
        exec_layout.addWidget(params_group)
        
        # ==================== 等待完成和停止条件 ====================
        wait_stop_row = QHBoxLayout()
        wait_stop_row.setSpacing(12)
        
        # 等待完成
        wait_group = QHBoxLayout()
        wait_group.setSpacing(6)
        
        self.wait_complete_check = QCheckBox("等待完成")
        self.wait_complete_check.setStyleSheet(f"color: {STYLE_TEXT}; font-size: 11px;")
        wait_group.addWidget(self.wait_complete_check)
        
        wait_group.addWidget(QLabel("关键字:"))
        self.wait_keyword_input = QLineEdit()
        self.wait_keyword_input.setPlaceholderText("如: root@~]")
        self.wait_keyword_input.setFixedWidth(70)
        self.wait_keyword_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {STYLE_INPUT_BG};
                color: {STYLE_TEXT};
                border: 1px solid {STYLE_BORDER};
                border-radius: 3px;
                padding: 2px 5px;
                font-size: 11px;
            }}
        """)
        wait_group.addWidget(self.wait_keyword_input)
        
        wait_group.addWidget(QLabel("超时:"))
        self.wait_timeout_spin = QSpinBox()
        self.wait_timeout_spin.setRange(100, 60000)
        self.wait_timeout_spin.setValue(3000)
        self.wait_timeout_spin.setFixedWidth(60)
        self.wait_timeout_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {STYLE_INPUT_BG};
                color: {STYLE_TEXT};
                border: 1px solid {STYLE_BORDER};
                border-radius: 3px;
                padding: 2px;
                font-size: 11px;
            }}
        """)
        wait_group.addWidget(self.wait_timeout_spin)
        
        wait_group.addWidget(QLabel("ms"))
        
        wait_group.addWidget(QLabel("失败:"))
        self.wait_failure_combo = QComboBox()
        self.wait_failure_combo.addItems(["继续", "跳过", "停止"])
        self.wait_failure_combo.setFixedWidth(60)
        self.wait_failure_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {STYLE_INPUT_BG};
                color: {STYLE_TEXT};
                border: 1px solid {STYLE_BORDER};
                border-radius: 3px;
                padding: 2px;
                font-size: 11px;
            }}
        """)
        wait_group.addWidget(self.wait_failure_combo)
        
        wait_stop_row.addLayout(wait_group)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet(f"color: {STYLE_BORDER};")
        wait_stop_row.addWidget(separator)
        
        # 停止条件
        stop_group = QHBoxLayout()
        stop_group.setSpacing(6)
        
        self.stop_check = QCheckBox("停止条件")
        self.stop_check.setStyleSheet(f"color: {STYLE_TEXT}; font-size: 11px;")
        stop_group.addWidget(self.stop_check)
        
        stop_group.addWidget(QLabel("关键字:"))
        self.stop_keyword_input = QLineEdit()
        self.stop_keyword_input.setPlaceholderText("如: ERROR")
        self.stop_keyword_input.setFixedWidth(70)
        self.stop_keyword_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {STYLE_INPUT_BG};
                color: {STYLE_TEXT};
                border: 1px solid {STYLE_BORDER};
                border-radius: 3px;
                padding: 2px 5px;
                font-size: 11px;
            }}
        """)
        stop_group.addWidget(self.stop_keyword_input)
        
        stop_group.addWidget(QLabel("处理:"))
        self.stop_action_combo = QComboBox()
        self.stop_action_combo.addItems(["停止", "继续"])
        self.stop_action_combo.setFixedWidth(60)
        self.stop_action_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {STYLE_INPUT_BG};
                color: {STYLE_TEXT};
                border: 1px solid {STYLE_BORDER};
                border-radius: 3px;
                padding: 2px;
                font-size: 11px;
            }}
        """)
        stop_group.addWidget(self.stop_action_combo)
        
        wait_stop_row.addLayout(stop_group)
        wait_stop_row.addStretch()
        
        exec_layout.addLayout(wait_stop_row)
        
        # 循环设置
        loop_layout = QHBoxLayout()
        loop_layout.setSpacing(10)

        loop_layout.addWidget(QLabel("循环:"))
        self.loop_count_spin = QSpinBox()
        self.loop_count_spin.setRange(1, 9999)
        self.loop_count_spin.setValue(1)
        self.loop_count_spin.setFixedWidth(60)
        self.loop_count_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {STYLE_INPUT_BG};
                color: {STYLE_TEXT};
                border: 1px solid {STYLE_BORDER};
                border-radius: 3px;
                padding: 2px;
                font-size: 11px;
            }}
        """)
        loop_layout.addWidget(self.loop_count_spin)

        loop_layout.addWidget(QLabel("次"))

        loop_layout.addWidget(QLabel("延时:"))
        self.loop_delay_spin = QSpinBox()
        self.loop_delay_spin.setRange(0, 60000)
        self.loop_delay_spin.setValue(500)
        self.loop_delay_spin.setFixedWidth(60)
        self.loop_delay_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {STYLE_INPUT_BG};
                color: {STYLE_TEXT};
                border: 1px solid {STYLE_BORDER};
                border-radius: 3px;
                padding: 2px;
                font-size: 11px;
            }}
        """)
        loop_layout.addWidget(self.loop_delay_spin)

        loop_layout.addWidget(QLabel("ms"))
        loop_layout.addStretch()

        exec_layout.addLayout(loop_layout)

        # 串行执行选项
        serial_exec_layout = QHBoxLayout()
        serial_exec_layout.setSpacing(10)

        self.serial_execute_check = QCheckBox("串行执行")
        self.serial_execute_check.setStyleSheet(f"color: {STYLE_TEXT}; font-size: 11px;")
        self.serial_execute_check.setToolTip("开启后，等待当前命令响应完成后再发送下一条命令")
        serial_exec_layout.addWidget(self.serial_execute_check)

        serial_exec_layout.addStretch()

        exec_layout.addLayout(serial_exec_layout)
        
        # 进度和统计
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(8)
        
        self.progress_label = QLabel("进度: 0/0")
        self.progress_label.setStyleSheet(f"color: {STYLE_TEXT_DIM}; font-size: 11px;")
        progress_layout.addWidget(self.progress_label)
        
        self.timer_label = QLabel("⏱ 00:00")
        self.timer_label.setStyleSheet(f"color: {STYLE_TEXT_DIM}; font-size: 11px;")
        progress_layout.addWidget(self.timer_label)
        
        self.stats_label = QLabel("成功:0 失败:0")
        self.stats_label.setStyleSheet(f"color: {STYLE_TEXT_DIM}; font-size: 11px;")
        progress_layout.addWidget(self.stats_label)
        
        progress_layout.addStretch()
        exec_layout.addLayout(progress_layout)
        
        exec_group.setLayout(exec_layout)
        layout.addWidget(exec_group)
        
        # 执行按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.start_btn = QPushButton("▶ 开始执行")
        self.start_btn.setMinimumWidth(100)
        self.start_btn.setStyleSheet(get_success_button_style())
        self.start_btn.clicked.connect(self.start_execution)
        btn_layout.addWidget(self.start_btn)
        
        self.stop_exec_btn = QPushButton("⏹ 停止")
        self.stop_exec_btn.setMinimumWidth(80)
        self.stop_exec_btn.setStyleSheet(get_danger_button_style())
        self.stop_exec_btn.clicked.connect(self.stop_execution)
        btn_layout.addWidget(self.stop_exec_btn)
        
        layout.addLayout(btn_layout)
        
        # 即时命令输入（用于SSH交互模式）
        cmd_input_layout = QHBoxLayout()
        cmd_input_layout.setSpacing(6)
        
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("即时命令...")
        self.cmd_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0a0a0a;
                color: #00ff00;
                border: 1px solid {STYLE_BORDER};
                border-radius: 3px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 4px;
            }}
        """)
        self.cmd_input.returnPressed.connect(self.on_send_command)
        cmd_input_layout.addWidget(self.cmd_input)
        
        self.send_cmd_btn = QPushButton("发送")
        self.send_cmd_btn.setMinimumWidth(60)
        self.send_cmd_btn.setStyleSheet(get_success_button_style())
        self.send_cmd_btn.clicked.connect(self.on_send_command)
        cmd_input_layout.addWidget(self.send_cmd_btn)
        
        layout.addLayout(cmd_input_layout)
        
        layout.addStretch()
        
        panel.setLayout(layout)
        
        return panel
    
    def setup_default_log(self, protocol="serial"):
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "log")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 根据协议类型命名日志文件
        log_file = os.path.join(log_dir, f"{protocol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        self.terminal.set_auto_save(True, log_file)
    
    def on_device_changed(self, device_name):
        self.protocol_combo.clear()
        
        if device_name and device_name in self.device_configs:
            device = self.device_configs[device_name]
            protocols = device.get("protocols", [])
            
            valid_protocols = [p for p in protocols 
                              if p.get("protocol", "").lower() in ["serial", "ssh", "telnet"]]
            
            for p in valid_protocols:
                protocol_name = p.get("protocol", "").upper()
                self.protocol_combo.addItem(protocol_name, p)
    
    def on_protocol_changed(self, index):
        if index >= 0:
            protocol_data = self.protocol_combo.currentData()
            if protocol_data:
                protocol = protocol_data.get("protocol", "").lower()
                
                if protocol == "serial":
                    com = protocol_data.get("com_port", "N/A")
                    baud = protocol_data.get("baud_rate", "N/A")
                    self.param_label.setText(f"│ {com} │ {baud} bps │")
                elif protocol in ["ssh", "telnet"]:
                    ip = protocol_data.get("ip", "N/A")
                    port = protocol_data.get("port", "N/A")
                    self.param_label.setText(f"│ {ip} │ {port} │")
            else:
                self.param_label.setText("请选择设备和协议")
        else:
            self.param_label.setText("请选择设备和协议")
    
    def refresh_ports(self):
        self.on_device_changed(self.device_combo.currentText())
    
    def toggle_connection(self):
        """切换连接状态 - 使用QTimer确保UI响应"""
        # 使用QTimer.singleShot确保不在任何阻塞操作中
        QTimer.singleShot(10, self._do_toggle_connection)
    
    def _do_toggle_connection(self):
        """实际执行连接切换"""
        print("[DEBUG] 开始执行连接切换")
        
        protocol_data = self.protocol_combo.currentData()
        if not protocol_data:
            self.terminal.append_error("请先选择设备和协议")
            print("[DEBUG] 未选择设备和协议")
            return
        
        protocol = protocol_data.get("protocol", "").lower()
        print(f"[DEBUG] 协议类型: {protocol}")
        
        # 判断当前连接状态
        is_connected = False
        if protocol == "serial" and self.serial_client and self.serial_client.is_open:
            is_connected = True
        elif protocol in ["ssh", "telnet"] and self.ssh_client:
            is_connected = True
        
        print(f"[DEBUG] 当前连接状态: {is_connected}")
        
        if not is_connected:
            if protocol == "serial":
                print("[DEBUG] 调用串口连接")
                self.connect_serial()
            elif protocol == "ssh":
                print("[DEBUG] 调用SSH连接")
                self.connect_ssh()
            elif protocol == "telnet":
                self.connect_telnet()
            else:
                self.terminal.append_warning(f"⚠ {protocol.upper()} 暂未实现")
        else:
            print("[DEBUG] 断开连接")
            self.disconnect()
    
    def connect_serial(self):
        """串口连接 - 使用后台线程"""
        protocol_data = self.protocol_combo.currentData()
        if not protocol_data:
            self.terminal.append_error("请先选择设备和协议")
            return
        
        protocol = protocol_data.get("protocol", "").lower()
        
        if protocol != "serial":
            self.terminal.append_warning(f"⚠ 当前协议不是串口")
            return
        
        port_name = protocol_data.get("com_port", "")
        baudrate = int(protocol_data.get("baud_rate", 115200))
        
        if not port_name:
            self.terminal.append_error("串口配置不完整，缺少COM端口")
            return
        
        # 禁用连接按钮，防止重复连接
        self.connect_btn.setEnabled(False)
        self.terminal.append_info(f"正在连接串口 {port_name}...")
        
        # 创建连接线程
        self.connection_thread = ConnectionThread("serial", protocol_data)
        self.connection_thread.status_update.connect(self.on_connection_status_update)
        self.connection_thread.connection_success.connect(self.on_serial_connected)
        self.connection_thread.connection_failed.connect(self.on_connection_failed)
        self.connection_thread.start()
    
    def connect_ssh(self):
        """SSH连接 - 使用后台线程"""
        print("[DEBUG] connect_ssh 开始执行")
        
        protocol_data = self.protocol_combo.currentData()
        if not protocol_data:
            self.terminal.append_error("请先选择设备和协议")
            return
        
        protocol = protocol_data.get("protocol", "").lower()
        if protocol != "ssh":
            self.terminal.append_warning(f"当前协议不是SSH")
            return
        
        ip = protocol_data.get("ip", "")
        port = int(protocol_data.get("port", 22))
        username = protocol_data.get("username", "")
        password = protocol_data.get("password", "")
        
        print(f"[DEBUG] SSH配置: ip={ip}, port={port}, username={username}")
        
        if not ip or not username:
            self.terminal.append_error("SSH配置不完整，请检查IP和用户名")
            return
        
        # 立即禁用连接按钮
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(False)
        self.device_combo.setEnabled(False)
        self.protocol_combo.setEnabled(False)
        
        # 不在这里显示连接信息，由 ConnectionThread 的 status_update 信号触发
        print("[DEBUG] 准备创建连接线程")
        
        # 创建连接线程
        self.connection_thread = ConnectionThread("ssh", protocol_data)
        self.connection_thread.status_update.connect(self.on_connection_status_update)
        self.connection_thread.connection_success.connect(self.on_ssh_connected)
        self.connection_thread.connection_failed.connect(self.on_connection_failed)
        
        print("[DEBUG] 启动连接线程")
        self.connection_thread.start()
        print("[DEBUG] 连接线程已启动")
    
    def connect_telnet(self):
        """Telnet连接"""
        print("[DEBUG] connect_telnet 开始执行")
        
        protocol_data = self.protocol_combo.currentData()
        if not protocol_data:
            self.terminal.append_error("请先选择设备和协议")
            return
        
        protocol = protocol_data.get("protocol", "").lower()
        if protocol != "telnet":
            self.terminal.append_warning(f"当前协议不是Telnet")
            return
        
        ip = protocol_data.get("ip", "")
        port = int(protocol_data.get("port", 23))
        username = protocol_data.get("username", "")
        password = protocol_data.get("password", "")
        
        print(f"[DEBUG] Telnet配置: ip={ip}, port={port}, username={username}")
        
        if not ip:
            self.terminal.append_error("Telnet配置不完整，请检查IP")
            return
        
        # 禁用连接按钮
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(False)
        self.device_combo.setEnabled(False)
        self.protocol_combo.setEnabled(False)
        
        # 创建Telnet连接线程
        self.connection_thread = ConnectionThread("telnet", protocol_data)
        self.connection_thread.status_update.connect(self.on_connection_status_update)
        self.connection_thread.connection_success.connect(self.on_telnet_connected)
        self.connection_thread.connection_failed.connect(self.on_connection_failed)
        
        print("[DEBUG] 启动Telnet连接线程")
        self.connection_thread.start()
        print("[DEBUG] Telnet连接线程已启动")
    
    def on_telnet_connected(self, protocol, connection_obj):
        """Telnet连接成功回调"""
        print(f"[主线程] Telnet连接成功")
        self.telnet_client = connection_obj
        
        # 设置Telnet日志文件
        self.setup_default_log("telnet")
        
        # 启动Telnet读取线程
        self.telnet_thread = threading.Thread(target=self.read_from_telnet, daemon=True)
        self.telnet_thread.start()
        
        # 启用断开按钮
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        
        self.terminal.append_info(f"✓ Telnet已连接 {connection_obj.connection_info.get('ip', '')}")
    
    def read_from_telnet(self):
        """Telnet读取线程"""
        print("[DEBUG] read_from_telnet 线程启动")
        while self.running and self.telnet_client and self.telnet_client.connected:
            try:
                # 串行执行模式：暂停读取
                if hasattr(self, 'ssh_read_paused') and self.ssh_read_paused:
                    time.sleep(0.05)
                    continue
                
                # 使用Telnet的expect来读取输出
                if self.telnet_client.telnet:
                    # 尝试非阻塞读取
                    try:
                        self.telnet_client.telnet.sock.setblocking(False)
                        data = self.telnet_client.telnet.read_very_eager()
                        if data:
                            text = data.decode('utf-8', errors='ignore')
                            if text:
                                self.terminal.data_received.emit(text)
                    except:
                        pass
                
                time.sleep(0.01)
            except Exception as e:
                if self.running:
                    self.terminal.data_received.emit(f"\n[错误] Telnet读取错误: {str(e)}\n")
                break
        
        if self.running:
            self.terminal.data_received.emit("\n[信息] Telnet连接已断开\n")
            QTimer.singleShot(0, lambda: self.disconnect())
    
    def read_from_ssh(self):
        """SSH读取线程"""
        while self.running and self.ssh_channel:
            try:
                # 串行执行模式：暂停读取，等待命令执行完成
                if self.ssh_read_paused:
                    time.sleep(0.05)
                    continue
                    
                # 检查是否有数据可读
                if self.ssh_channel.recv_ready():
                    data = self.ssh_channel.recv(8192)
                    if data:
                        text = data.decode('utf-8', errors='ignore')
                        if text:
                            # 使用信号更新 GUI（线程安全）
                            self.terminal.data_received.emit(text)
                            
                            # 直接写入日志（带时间戳），过滤命令回显
                            if self.terminal.log_file and self.terminal.auto_save:
                                try:
                                    clean_text = self.terminal._clean_ansi_for_log(text)
                                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    
                                    # 过滤回显模式：检测是否遇到命令提示符
                                    if self.ssh_echo_mode:
                                        # 检查是否包含提示符（┌──、└─、CTP>、<HUAWEI>、$、#、> 等）
                                        if '┌──' in clean_text or '└─#' in clean_text or '└─$' in clean_text or 'CTP>' in clean_text or '<HUAWEI>' in clean_text or clean_text.endswith('$') or clean_text.endswith('#') or clean_text.endswith('>'):
                                            self.ssh_echo_mode = False  # 退出回显模式
                                            # 跳过提示符行，记录后续内容
                                            all_lines = clean_text.split('\n')
                                            lines = []
                                            skip_prompt = True
                                            for line in all_lines:
                                                stripped = line.strip()
                                                if skip_prompt and ('┌──' in stripped or '└─#' in stripped or '└─$' in stripped or 'CTP>' in stripped or stripped.endswith('$') or stripped.endswith('#') or stripped.endswith('>')):
                                                    skip_prompt = False
                                                    continue
                                                if stripped:
                                                    lines.append(stripped)
                                            if not lines:
                                                return
                                        else:
                                            # 在回显模式下，跳过所有内容
                                            return
                                    else:
                                        # 正常模式：记录所有行
                                        lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
                                    with open(self.terminal.log_file, 'a', encoding='utf-8') as f:
                                        for line in lines:
                                            f.write(f"[{timestamp}] {line}\n")
                                except Exception as e:
                                    print(f"SSH日志写入失败: {e}")

                if self.ssh_channel.recv_stderr_ready():
                    data = self.ssh_channel.recv_stderr(8192)
                    if data:
                        text = data.decode('utf-8', errors='ignore')
                        if text:
                            self.terminal.data_received.emit(text)
                            
                            # 直接写入日志（带时间戳）
                            if self.terminal.log_file and self.terminal.auto_save:
                                try:
                                    clean_text = self.terminal._clean_ansi_for_log(text)
                                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    
                                    # 过滤回显模式：检测是否遇到命令提示符
                                    if self.ssh_echo_mode:
                                        if '┌──' in clean_text or '└─#' in clean_text or '└─$' in clean_text or 'CTP>' in clean_text or '<HUAWEI>' in clean_text or clean_text.endswith('$') or clean_text.endswith('#') or clean_text.endswith('>'):
                                            self.ssh_echo_mode = False
                                            # 跳过提示符行，记录后续内容
                                            all_lines = clean_text.split('\n')
                                            lines = []
                                            skip_prompt = True
                                            for line in all_lines:
                                                stripped = line.strip()
                                                if skip_prompt and ('┌──' in stripped or '└─#' in stripped or '└─$' in stripped or 'CTP>' in stripped or stripped.endswith('$') or stripped.endswith('#') or stripped.endswith('>')):
                                                    skip_prompt = False
                                                    continue
                                                if stripped:
                                                    lines.append(stripped)
                                            if not lines:
                                                return
                                        else:
                                            return
                                    else:
                                        lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
                                    with open(self.terminal.log_file, 'a', encoding='utf-8') as f:
                                        for line in lines:
                                            f.write(f"[{timestamp}] {line}\n")
                                except Exception as e:
                                    print(f"SSH日志写入失败: {e}")

                time.sleep(0.01)
            except Exception as e:
                if self.running:
                    # 使用信号显示错误
                    self.terminal.data_received.emit(f"\n[错误] SSH读取错误: {str(e)}\n")
                break

        if self.running:
            self.terminal.data_received.emit("\n[信息] SSH连接已断开\n")
            QTimer.singleShot(0, lambda: self.disconnect())
    
    def on_connection_status_update(self, status):
        """连接状态更新"""
        print(f"[主线程] 连接状态更新: {status}")
        self.terminal.append_info(status)
    
    def on_serial_connected(self, protocol, connection_obj):
        """串口连接成功回调"""
        print(f"[主线程] 串口连接成功")
        self.serial_client = connection_obj
        baudrate = int(self.protocol_combo.currentData().get("baud_rate", 115200))
        port_name = self.protocol_combo.currentData().get("com_port", "")
        
        self.terminal.append_info(f"✓ 已连接 {port_name} @ {baudrate} bps")
        
        # 重新设置串口日志文件
        self.setup_default_log("serial")
        
        self.update_connection_state(True)
        
        self.running = True
        self.serial_thread = threading.Thread(target=self.read_from_serial, daemon=True)
        self.serial_thread.start()
        
        self.start_btn.setEnabled(True)
        
        # 启用终端输入模式
        self.terminal.set_input_mode(True)
        
        # 清理连接线程
        if self.connection_thread:
            self.connection_thread = None
    
    def on_ssh_connected(self, protocol, connection_obj):
        """SSH连接成功回调"""
        print(f"[主线程] SSH连接成功回调触发")
        self.ssh_client, self.ssh_channel = connection_obj
        print(f"[主线程] ssh_client: {self.ssh_client}, ssh_channel: {self.ssh_channel}")
        
        # 先设置SSH日志文件（确保连接时的消息也能记录）
        self.setup_default_log("ssh")
        
        self.terminal.append_info(f"✓ SSH连接成功")
        
        print("[主线程] 更新连接状态")
        self.update_connection_state(True)
        
        print("[主线程] 启动SSH读取线程")
        self.running = True
        self.ssh_thread = threading.Thread(target=self.read_from_ssh, daemon=True)
        self.ssh_thread.start()
        
        print("[主线程] 启用开始按钮")
        self.start_btn.setEnabled(True)
        
        # 启用终端输入模式
        print("[主线程] 启用终端输入模式")
        self.terminal.set_input_mode(True)
        
        # 清理连接线程
        if self.connection_thread:
            self.connection_thread = None
        
        print("[主线程] SSH连接成功处理完成")
    
    def on_connection_failed(self, error_msg):
        """连接失败回调"""
        print(f"[主线程] 连接失败: {error_msg}")
        self.terminal.append_error(error_msg)
        
        # 恢复连接按钮
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.device_combo.setEnabled(True)
        self.protocol_combo.setEnabled(True)
        
        # 清理连接线程
        if self.connection_thread:
            self.connection_thread = None
        
        # 清理连接线程
        if self.connection_thread:
            self.connection_thread = None
    
    def update_connection_state(self, connected):
        self.connect_btn.setEnabled(not connected)
        self.disconnect_btn.setEnabled(connected)
        self.device_combo.setEnabled(not connected)
        self.protocol_combo.setEnabled(not connected)
    
    def disconnect(self):
        self.running = False
        
        # 停止连接线程（如果正在进行）
        if self.connection_thread and self.connection_thread.isRunning():
            self.connection_thread.stop()
            self.connection_thread.wait()
            self.connection_thread = None
        
        # 恢复串口和SSH读取
        self.serial_read_paused = False
        self.ssh_read_paused = False
        
        # 断开串口
        if self.serial_client and self.serial_client.is_open:
            self.serial_client.close()
        self.serial_client = None
        
        # 断开SSH
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except:
                pass
        self.ssh_client = None
        self.ssh_channel = None
        
        # 断开Telnet
        if self.telnet_client:
            try:
                self.telnet_client.disconnect()
            except:
                pass
        self.telnet_client = None
        self.telnet_thread = None
        
        self.terminal.append_info("✓ 已断开连接")
        self.update_connection_state(False)
        self.start_btn.setEnabled(False)
        self.stop_execution()

        # 禁用终端输入模式
        self.terminal.set_input_mode(False)

    def read_from_serial(self):
        print("[DEBUG] read_from_serial 线程启动")
        while self.running and self.serial_client and self.serial_client.is_open:
            try:
                # 串行执行模式：暂停读取，等待命令执行完成
                if self.serial_read_paused:
                    time.sleep(0.05)
                    continue
                    
                if self.serial_client.in_waiting > 0:
                    data = self.serial_client.read(self.serial_client.in_waiting)
                    print(f"[DEBUG] 收到串口数据: {len(data)} 字节")
                    try:
                        text = data.decode('utf-8', errors='replace')
                        # 直接调用方法进行GUI更新
                        self.terminal.append_raw(text)
                        
                        # 直接写入日志（带时间戳）
                        if self.terminal.log_file and self.terminal.auto_save:
                            try:
                                clean_text = self.terminal._clean_ansi_for_log(text)
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                # 为每行添加时间戳，跳过空行和纯空白行，去除前导空格
                                lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
                                with open(self.terminal.log_file, 'a', encoding='utf-8') as f:
                                    for line in lines:
                                        f.write(f"[{timestamp}] {line}\n")
                            except Exception as e:
                                print(f"串口日志写入失败: {e}")
                    except Exception as e:
                        print(f"[DEBUG] 解码错误: {e}")
                time.sleep(0.01)
            except Exception as e:
                if self.running:
                    self.terminal.append_error(f"读取错误: {str(e)}")
                break
        print("[DEBUG] read_from_serial 线程结束")
    
    def on_send_command(self):
        """即时命令输入处理"""
        command = self.cmd_input.text().strip()
        if command:
            self.send_command(command + '\n')  # 及时命令需要换行
            self.cmd_input.clear()
    
    def send_command(self, command):
        """发送命令或字符到设备"""
        # 优先使用SSH发送
        if self.ssh_channel:
            try:
                # 直接发送，不添加换行（终端模式）
                self.ssh_channel.send(command)
                # 设置回显模式，过滤命令回显直到出现提示符
                self.ssh_echo_mode = True
                return True
            except Exception as e:
                self.terminal.append_error(f"SSH发送失败: {str(e)}")
                return False

        # 其次使用串口发送
        if not self.serial_client or not self.serial_client.is_open:
            self.terminal.append_error("未连接设备")
            return False

        try:
            command_bytes = command.encode('utf-8')
            self.serial_client.write(command_bytes)
            return True
        except Exception as e:
            self.terminal.append_error(f"发送失败: {str(e)}")
            return False
    
    def clear_terminal(self):
        """清空终端"""
        self.terminal.clear_screen()
        self.terminal.log_lines = []
        self.terminal.append_output("═══ 终端已清空 ═══")
    
    def save_log(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存日志", 
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "log"),
            "日志文件 (*.log *.txt)"
        )
        
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.terminal.get_all_text())
                QMessageBox.information(self, "保存成功", f"日志已保存到:\n{filepath}")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"无法保存日志:\n{str(e)}")
    
    def on_auto_save_changed(self, state):
        self.terminal.set_auto_save(state == Qt.CheckState.Checked.value)
    
    def copy_log(self):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.terminal.toPlainText())
        self.terminal.append_info("✓ 日志已复制到剪贴板")
    
    def on_search_text_changed(self, text):
        if not text:
            return
        
        matches = self.terminal.search_text(text)
        if matches:
            self.terminal.append_info(f"🔍 找到 {len(matches)} 处匹配")
    
    def parse_parameter_value(self, param_value):
        """
        解析参数值，支持多种格式：
        - 单个值: "192.168.1.1" -> ["192.168.1.1"]
        - 数字范围: "1-99" -> [1, 2, 3, ..., 99]
        - IP范围: "192.168.1.1-192.168.1.10" -> ["192.168.1.1", ..., "192.168.1.10"]
        - 列表: "a,b,c" -> ["a", "b", "c"]
        
        返回: 值列表
        """
        if not param_value or not param_value.strip():
            return []
        
        param_value = param_value.strip()
        
        # 尝试解析为数字范围 (如: 1-99)
        if '-' in param_value and not ',' in param_value:
            parts = param_value.split('-')
            if len(parts) == 2:
                try:
                    start = int(parts[0].strip())
                    end = int(parts[1].strip())
                    if start <= end:
                        return list(range(start, end + 1))
                except ValueError:
                    pass
        
        # 尝试解析为IP范围 (如: 192.168.1.1-192.168.1.10)
        if '-' in param_value and param_value.count('.') >= 6:  # 至少6个点（两个IP）
            parts = param_value.split('-')
            if len(parts) == 2:
                try:
                    ip1_parts = parts[0].strip().split('.')
                    ip2_parts = parts[1].strip().split('.')
                    if len(ip1_parts) == 4 and len(ip2_parts) == 4:
                        # 提取最后一段数字范围
                        last_octet_start = int(ip1_parts[3])
                        last_octet_end = int(ip2_parts[3])
                        prefix = '.'.join(ip1_parts[:3])
                        return [f"{prefix}.{i}" for i in range(last_octet_start, last_octet_end + 1)]
                except ValueError:
                    pass
        
        # 尝试解析为列表 (如: a,b,c 或 192.168.1.1,192.168.1.2)
        if ',' in param_value:
            items = [item.strip() for item in param_value.split(',') if item.strip()]
            return items
        
        # 单个值
        return [param_value]
    
    def replace_parameters(self, command, param_values):
        """
        替换命令中的参数变量
        
        参数:
            command: 命令字符串，例如 "ping $A -c $B"
            param_values: 参数字典，例如 {'A': ['192.168.1.1'], 'B': [4]}
        
        返回: 替换后的命令列表（如果参数有多个值，会生成多条命令）
        """
        # 检查命令中是否包含参数
        if '$A' not in command and '$B' not in command and '$C' not in command:
            return [command]
        
        # 获取参数值的笛卡尔积
        from itertools import product
        
        param_a_values = param_values.get('A', [''])
        param_b_values = param_values.get('B', [''])
        param_c_values = param_values.get('C', [''])
        
        # 如果某个参数没有提供值，使用空字符串
        if not param_a_values:
            param_a_values = ['']
        if not param_b_values:
            param_b_values = ['']
        if not param_c_values:
            param_c_values = ['']
        
        # 生成所有参数组合
        commands = []
        for a, b, c in product(param_a_values, param_b_values, param_c_values):
            cmd = command.replace('$A', str(a)).replace('$B', str(b)).replace('$C', str(c))
            commands.append(cmd)
        
        return commands
    
    def expand_command_parameters(self, commands):
        """
        扩展命令列表，替换所有参数
        
        参数:
            commands: 原始命令列表
        
        返回: 替换参数后的命令列表
        """
        # 解析参数值
        param_values = {}
        
        param_a_text = self.param_a_input.text()
        if param_a_text.strip():
            param_values['A'] = self.parse_parameter_value(param_a_text)
        
        param_b_text = self.param_b_input.text()
        if param_b_text.strip():
            param_values['B'] = self.parse_parameter_value(param_b_text)
        
        param_c_text = self.param_c_input.text()
        if param_c_text.strip():
            param_values['C'] = self.parse_parameter_value(param_c_text)
        
        # 如果没有参数，直接返回原命令
        if not param_values:
            return commands
        
        # 替换参数
        expanded_commands = []
        for cmd in commands:
            expanded = self.replace_parameters(cmd, param_values)
            expanded_commands.extend(expanded)
        
        return expanded_commands
    
    def get_commands(self):
        """获取命令列表（已应用参数替换）"""
        text = self.command_text.toPlainText()
        commands = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 应用参数扩展
        expanded_commands = self.expand_command_parameters(commands)
        
        return expanded_commands
    
    def start_execution(self):
        # 获取原始命令
        text = self.command_text.toPlainText()
        original_commands = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not original_commands:
            self.terminal.append_error("请先输入命令")
            return
        
        # 获取扩展后的命令（应用参数替换）
        commands = self.get_commands()
        
        # 检查连接状态（支持串口和SSH）
        is_connected = (self.serial_client and self.serial_client.is_open) or (self.ssh_client and self.ssh_channel)
        if not is_connected:
            self.terminal.append_error("请先连接设备")
            return
        
        loop_count = self.loop_count_spin.value()
        loop_delay = self.loop_delay_spin.value()
        
        wait_complete = self.wait_complete_check.isChecked()
        wait_keyword = self.wait_keyword_input.text() if wait_complete else ""
        wait_timeout = self.wait_timeout_spin.value()
        wait_failure = self.wait_failure_combo.currentIndex()
        
        stop_enabled = self.stop_check.isChecked()
        stop_keyword = self.stop_keyword_input.text() if stop_enabled else ""
        stop_action = self.stop_action_combo.currentIndex()
        
        # 显示命令扩展信息
        if len(commands) != len(original_commands):
            self.terminal.append_info(f"═══ 原始命令: {len(original_commands)} 条 → 扩展后: {len(commands)} 条 ═══")
        else:
            self.terminal.append_info(f"═══ 开始执行: {len(commands)} 条命令 ═══")
        
        # 获取串行执行模式
        serial_execute = self.serial_execute_check.isChecked()
        
        self.command_executor = CommandExecutor(
            self.serial_client, self.ssh_channel, self.telnet_client, commands, loop_count, loop_delay,
            wait_complete, wait_keyword, wait_timeout, wait_failure,
            stop_enabled, stop_keyword, stop_action, serial_execute
        )
        
        # 优化：程序消息已直接保存，SSH输出使用批量保存
        # 统一使用2000ms延迟，减少IO操作，提升性能
        self.terminal.set_log_delay(2000)
        
        self.command_executor.command_sent.connect(self.on_command_sent)
        self.command_executor.response_received.connect(self.on_response_received)
        self.command_executor.execution_finished.connect(self.on_execution_finished)
        self.command_executor.progress_updated.connect(self.on_progress_updated)
        self.command_executor.status_updated.connect(self.on_status_updated)
        
        # 串行执行模式：暂停串口和SSH读取线程，避免数据穿插
        if serial_execute:
            self.serial_read_paused = True
            self.ssh_read_paused = True
        
        self.start_btn.setEnabled(False)
        self.stop_exec_btn.setEnabled(True)
        self.connect_btn.setEnabled(False)
        
        self.success_count = 0
        self.fail_count = 0
        self.update_stats()
        
        self.timer.start_time = time.time()
        self.timer.start(1000)
        
        self.command_executor.start()
        
        # 注意：进度消息由 CommandExecutor 循环中自动发送，不要重复发送
    
    def on_command_sent(self, command):
        """命令发送回调 - SSH/串口会回显，不在终端重复显示"""
        # 命令会由SSH回显，我们不显示在终端
        # 但记录 [CMD] 标记到日志（直接写入，不进入pyte避免穿插）
        if self.terminal.log_file and self.terminal.auto_save:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(self.terminal.log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{timestamp}] [CMD] {command}\n")
            except Exception as e:
                print(f"记录命令日志失败: {e}")
        
        # 设置回显模式，过滤命令回显
        if self.ssh_channel:
            self.ssh_echo_mode = True
    
    def on_response_received(self, response):
        self.terminal.append_response(response)
        
        # 直接写入日志文件（确保响应不丢失）
        if self.terminal.log_file and self.terminal.auto_save:
            try:
                # 清理 ANSI 转义序列
                clean_response = self.terminal._clean_ansi_for_log(response)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 为每行添加时间戳，跳过空行和纯空白行
                lines = [line.strip() for line in clean_response.split('\n') if line.strip()]
                with open(self.terminal.log_file, 'a', encoding='utf-8') as f:
                    for line in lines:
                        f.write(f"[{timestamp}] {line}\n")
            except Exception as e:
                print(f"记录响应日志失败: {e}")
    
    def on_execution_finished(self, success, message):
        self.timer.stop()
        
        # 串行模式：先输出缓存的执行日志
        if hasattr(self.command_executor, 'execution_log') and self.command_executor.execution_log:
            for log_msg in self.command_executor.execution_log:
                self.terminal.append_info(log_msg)
        
        # 关键修复：在显示"执行完成"前，先强制保存所有挂起的SSH输出
        # 避免"执行完成"消息穿插在SSH输出中间
        if hasattr(self.terminal, '_pending_save_lines') and self.terminal._pending_save_lines is not None:
            # 立即保存所有挂起的日志
            self.terminal._save_display_to_log(self.terminal._pending_save_lines)
            self.terminal._pending_save_lines = None
        
        # 恢复串口读取（串行执行模式结束后）
        self.serial_read_paused = False
        self.ssh_read_paused = False
        self.ssh_echo_mode = False  # 退出回显模式
        
        # 再等待一小段时间（确保所有输出都已显示）
        QTimer.singleShot(500, lambda: self._show_execution_result(success, message))
    
    def _show_execution_result(self, success, message):
        """显示执行结果"""
        if success:
            self.terminal.append_info(message)
        else:
            self.terminal.append_error(message)
        
        self.start_btn.setEnabled(True)
        self.stop_exec_btn.setEnabled(False)
        self.connect_btn.setEnabled(True)
    
    def on_progress_updated(self, current, total):
        self.progress_label.setText(f"进度: {current}/{total}")
    
    def on_status_updated(self, status):
        self.terminal.append_info(status)
    
    def stop_execution(self):
        if self.command_executor and self.command_executor.isRunning():
            self.command_executor.stop()
            self.command_executor.wait()
        
        self.timer.stop()
        
        # 恢复串口和SSH读取（防止被暂停）
        self.serial_read_paused = False
        self.ssh_read_paused = False
        
        self.terminal.append_warning("⚠ 执行已停止")
        
        self.start_btn.setEnabled(True)
        self.stop_exec_btn.setEnabled(False)
        self.connect_btn.setEnabled(True)
    
    def update_timer(self):
        if self.timer.start_time:
            elapsed = int(time.time() - self.timer.start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            self.timer_label.setText(f"⏱ {hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def update_stats(self):
        total = self.success_count + self.fail_count
        if total > 0:
            rate = (self.success_count / total) * 100
            self.stats_label.setText(f"成功: {self.success_count}  失败: {self.fail_count}  成功率: {rate:.1f}%")
        else:
            self.stats_label.setText("成功: 0  失败: 0  成功率: 0%")
    
    # 模板管理
    def update_template_list(self):
        self.template_list.clear()
        for name in self.templates.keys():
            self.template_list.addItem(name)
    
    def add_template(self):
        dialog = TemplateDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data["name"]:
                self.templates[data["name"]] = data["commands"]
                self.save_templates()
                self.update_template_list()
    
    def edit_template(self):
        current = self.template_list.currentItem()
        if not current:
            return
        
        name = current.text()
        commands = self.templates.get(name, "")
        
        dialog = TemplateDialog(self, {"name": name, "commands": commands})
        if dialog.exec():
            data = dialog.get_data()
            if data["name"] and data["name"] != name:
                del self.templates[name]
            if data["name"]:
                self.templates[data["name"]] = data["commands"]
                self.save_templates()
                self.update_template_list()
    
    def del_template(self):
        current = self.template_list.currentItem()
        if not current:
            return
        
        name = current.text()
        reply = QMessageBox.question(self, "确认删除", f"确定要删除模板 '{name}' 吗?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.templates[name]
            self.save_templates()
            self.update_template_list()
    
    def apply_template(self):
        current = self.template_list.currentItem()
        if not current:
            return
        
        name = current.text()
        commands = self.templates.get(name, "")
        if commands:
            self.command_text.setPlainText(commands)
            self.terminal.append_info(f"✓ 已加载模板: {name}")
