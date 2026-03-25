from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, 
                             QTextEdit, QLabel, QGroupBox, QPushButton, QMessageBox, QDialog,
                             QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt
from .device_config_dialog import DeviceConfigDialog

# 导入统一UI样式
from themes.ui_styles import get_common_stylesheet
import json
import os


class DeviceManagementPage(QWidget):
    def __init__(self):
        super().__init__()
        self.device_configs = {}  # 存储设备配置的字典
        self.config_file = "device_configs.json"  # 配置文件路径
        self.setStyleSheet(get_common_stylesheet())  # 应用统一UI样式
        self.init_ui()
        self.load_config()  # 加载已有配置
    
    def init_ui(self):
        # 主布局
        main_layout = QHBoxLayout()
        
        # 创建可拖拽的分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧设备管理区域（70%）
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)  # 移除内外边距
        left_layout.setSpacing(5)  # 设置组件间距
        
        # 创建垂直分割器，将左侧分为上下两部分
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 上方设备列表区域（占2/3空间）
        device_list_group = QGroupBox("设备列表")
        device_list_layout = QVBoxLayout()
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        # 新建设备按钮
        new_device_btn = QPushButton("新建设备")
        new_device_btn.clicked.connect(self.new_device)
        button_layout.addWidget(new_device_btn)
        
        # 重命名设备按钮
        rename_device_btn = QPushButton("重命名")
        rename_device_btn.clicked.connect(self.rename_device)
        button_layout.addWidget(rename_device_btn)
        
        # 删除设备按钮
        delete_device_btn = QPushButton("删除设备")
        delete_device_btn.clicked.connect(self.delete_device)
        button_layout.addWidget(delete_device_btn)
        
        button_layout.addStretch()  # 添加弹性空间
        
        device_list_layout.addLayout(button_layout)
        
        # 设备列表
        self.device_list = QListWidget()
        # 删除默认设备配置，设备列表为空
        self.device_list.itemClicked.connect(self.on_device_clicked)
        self.device_list.itemDoubleClicked.connect(self.on_device_double_clicked)
        device_list_layout.addWidget(self.device_list)
        
        device_list_group.setLayout(device_list_layout)
        
        # 下方设备详细信息区域（占1/3空间）
        device_detail_group = QGroupBox("设备详细信息")
        device_detail_layout = QVBoxLayout()
        
        # 设备详细信息表格
        self.device_detail_table = QTableWidget()
        self.device_detail_table.setColumnCount(6)
        self.device_detail_table.setHorizontalHeaderLabels([
            "协议", "IP地址", "端口", "用户名", "密码", "刷新时间"
        ])
        # 设置列宽策略
        header = self.device_detail_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.device_detail_table.setAlternatingRowColors(True)
        # 隐藏行号列（垂直表头）
        self.device_detail_table.verticalHeader().setVisible(False)
        device_detail_layout.addWidget(self.device_detail_table)
        device_detail_group.setLayout(device_detail_layout)
        
        # 添加到垂直分割器
        left_splitter.addWidget(device_list_group)
        left_splitter.addWidget(device_detail_group)
        
        # 设置垂直分割比例 2:1
        left_splitter.setStretchFactor(0, 2)
        left_splitter.setStretchFactor(1, 1)
        
        left_layout.addWidget(left_splitter)
        left_widget.setLayout(left_layout)
        
        # 右侧日志输出区域（30%）
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)  # 移除内外边距
        right_layout.setSpacing(5)  # 设置组件间距
        
        # 创建日志输出组框，将按钮和日志输出放在同一个区域
        log_group = QGroupBox("日志输出区域")
        log_group_layout = QVBoxLayout()
        log_group_layout.setContentsMargins(5, 5, 5, 5)  # 设置组框内边距
        log_group_layout.setSpacing(5)  # 设置组件间距
        
        # 日志操作按钮区域
        log_buttons_layout = QHBoxLayout()
        log_buttons_layout.setSpacing(3)  # 按钮间距更小
        
        # 创建五个日志操作按钮，使用图标和更清晰的命名
        save_log_btn = QPushButton("📁 选择路径")
        save_log_btn.setFixedHeight(25)
        save_log_btn.setToolTip("选择日志保存路径")
        
        start_log_btn = QPushButton("🔴 开始记录")
        start_log_btn.setFixedHeight(25)
        start_log_btn.setToolTip("开始实时记录日志")
        
        stop_log_btn = QPushButton("⚫ 停止记录")
        stop_log_btn.setFixedHeight(25)
        stop_log_btn.setToolTip("停止日志记录")
        
        clear_log_btn = QPushButton("🗑️ 清空日志")
        clear_log_btn.setFixedHeight(25)
        clear_log_btn.setToolTip("清空当前日志内容")
        
        open_log_btn = QPushButton("📄 打开日志")
        open_log_btn.setFixedHeight(25)
        open_log_btn.setToolTip("打开已保存的日志文件")
        
        # 将按钮添加到水平布局，按逻辑顺序排列
        log_buttons_layout.addWidget(save_log_btn)
        log_buttons_layout.addWidget(start_log_btn)
        log_buttons_layout.addWidget(stop_log_btn)
        log_buttons_layout.addWidget(clear_log_btn)
        log_buttons_layout.addWidget(open_log_btn)
        log_buttons_layout.addStretch()  # 添加弹性空间，让按钮靠左
        
        # 将按钮布局添加到组框布局
        log_group_layout.addLayout(log_buttons_layout)
        
        # 日志输出框
        log_output = QTextEdit()
        log_output.setReadOnly(True)
        log_output.setPlaceholderText("日志信息将显示在这里...")
        log_output.setStyleSheet("""
            QTextEdit {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                color: palette(text);
            }
        """)
        log_group_layout.addWidget(log_output)
        
        log_group.setLayout(log_group_layout)
        
        # 将日志输出组框添加到右侧布局
        right_layout.addWidget(log_group)
        
        right_widget.setLayout(right_layout)
        
        # 添加到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        # 设置初始比例 7:3
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)
    
    def on_device_clicked(self, item):
        """设备单击事件处理 - 显示设备详细信息表格"""
        from PyQt6.QtWidgets import QTableWidgetItem, QHeaderView
        device_name = item.text()
        
        # 清空表格
        self.device_detail_table.setRowCount(0)
        
        # 获取设备配置
        if device_name in self.device_configs:
            config = self.device_configs[device_name]
            protocols = config.get('protocols', [])
            last_refresh = config.get('last_refresh', '')
            
            # 填充表格
            for i, protocol in enumerate(protocols):
                self.device_detail_table.insertRow(i)
                
                # 协议类型
                proto_type = protocol.get('protocol', '').upper()
                self.device_detail_table.setItem(i, 0, QTableWidgetItem(proto_type))
                
                # IP地址
                ip_addr = protocol.get('ip', '')
                self.device_detail_table.setItem(i, 1, QTableWidgetItem(ip_addr))
                
                # 端口
                port = str(protocol.get('port', ''))
                self.device_detail_table.setItem(i, 2, QTableWidgetItem(port))
                
                # 用户名
                username = protocol.get('username', '')
                self.device_detail_table.setItem(i, 3, QTableWidgetItem(username))
                
                # 密码
                password = protocol.get('password', '')
                self.device_detail_table.setItem(i, 4, QTableWidgetItem(password))
                
                # 刷新时间（这里用设备的 last_refresh）
                self.device_detail_table.setItem(i, 5, QTableWidgetItem(last_refresh))
        else:
            # 没有配置时清空
            self.device_detail_table.setRowCount(0)
    
    def get_device_details(self, device_name):
        """获取设备详细信息（每种协议单独一行显示）"""
        details = f"设备名称: {device_name}\n"
        
        # 从存储的配置中获取协议数据
        if device_name in self.device_configs:
            config = self.device_configs[device_name]
            protocols = config.get('protocols', [])
            
            if protocols:
                details += f"协议数量: {len(protocols)}\n"
                
                for i, protocol in enumerate(protocols, 1):
                    protocol_type = protocol['protocol'].upper()
                    
                    if protocol['protocol'] in ['ssh', 'telnet', 'ftp', 'sftp']:
                        protocol_line = f"协议类型：{protocol_type} IP地址：{protocol.get('ip', '')} 端口号：{protocol.get('port', '')}"
                        if protocol.get('username'):
                            protocol_line += f" 用户名：{protocol['username']}"
                        if protocol.get('password'):
                            protocol_line += f" 密码：{protocol['password']}"
                        if protocol.get('baud_rate'):
                            protocol_line += f" 波特率：{protocol['baud_rate']}"
                    
                    elif protocol['protocol'] == 'serial':
                        protocol_line = f"协议类型：{protocol_type} 串口号：{protocol.get('com_port', '')}"
                        if protocol.get('baud_rate'):
                            protocol_line += f" 波特率：{protocol['baud_rate']}"
                    
                    else:
                        protocol_line = f"协议类型：{protocol_type}"
                    
                    details += f"{protocol_line}\n"
            else:
                details += "无配置协议"
        else:
            details += "无配置协议"
        
        return details
    
    def on_device_double_clicked(self, item):
        """设备双击事件处理"""
        device_name = item.text()
        
        # 创建设备配置对话框
        dialog = DeviceConfigDialog(device_name, self)
        
        # 显示对话框
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 用户点击了确定按钮
            config = dialog.get_device_config()
            
            # 保存设备配置（这里可以保存到文件或数据库）
            self.save_device_config(device_name, config)
            
            # 更新设备详细信息显示
            self.on_device_clicked(item)
            
            QMessageBox.information(self, "配置保存", 
                                  f"设备 '{device_name}' 的配置已保存！")
    
    def save_device_config(self, device_name, config):
        """保存设备配置"""
        # 将配置存储到字典中
        self.device_configs[device_name] = config
        
        # 如果设备不在列表中，添加到设备列表
        existing_devices = [self.device_list.item(i).text() for i in range(self.device_list.count())]
        if device_name not in existing_devices:
            self.device_list.addItem(device_name)
        
        print(f"设备配置已保存: {device_name}")
        print(f"协议数量: {len(config['protocols'])}")
        
        # 每次保存配置后都保存到文件
        self.save_config()
        
        # 通知其他页面更新设备列表
        self.notify_device_list_updated()
    
    def save_config(self):
        """保存设备配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.device_configs, f, ensure_ascii=False, indent=2)
            print("设备配置已保存到文件")
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def load_config(self):
        """从文件加载设备配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_configs = json.load(f)
                    
                # 更新设备配置字典
                self.device_configs.update(loaded_configs)
                
                # 更新设备列表
                for device_name in self.device_configs.keys():
                    if device_name not in [self.device_list.item(i).text() for i in range(self.device_list.count())]:
                        self.device_list.addItem(device_name)
                
                print(f"已加载 {len(self.device_configs)} 个设备的配置")
            else:
                print("配置文件不存在，将创建新的配置文件")
                # 创建空的配置文件
                self.save_config()
        except Exception as e:
            print(f"加载配置失败: {e}")
            # 如果加载失败，创建空的配置文件
            self.save_config()
    
    def new_device(self):
        """新建设备 - 弹出设备配置对话框"""
        # 创建设备配置对话框，设备名称为空
        dialog = DeviceConfigDialog("", self)
        
        # 显示对话框
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 用户点击了确定按钮
            config = dialog.get_device_config()
            device_name = config['device_name']
            
            if not device_name:
                QMessageBox.warning(self, "配置错误", "设备名称不能为空")
                return
            
            # 保存设备配置
            self.save_device_config(device_name, config)
            
            # 更新设备详细信息显示
            current_item = self.device_list.item(self.device_list.count() - 1)
            if current_item:
                self.on_device_clicked(current_item)
            
            QMessageBox.information(self, "设备创建成功", 
                                  f"设备 '{device_name}' 已成功创建！")
    
    def delete_device(self):
        """删除设备"""
        current_row = self.device_list.currentRow()
        
        if current_row < 0:
            QMessageBox.warning(self, "删除失败", "请先选择一个设备")
            return
        
        device_name = self.device_list.item(current_row).text()
        
        reply = QMessageBox.question(self, "确认删除", 
                                   f"确定要删除设备 '{device_name}' 吗？",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            # 从列表中删除设备
            self.device_list.takeItem(current_row)
            
            # 从配置字典中删除设备配置
            if device_name in self.device_configs:
                del self.device_configs[device_name]
            
            # 清空设备详细信息显示
            for child in self.findChildren(QTextEdit):
                if child.placeholderText() and "详细信息" in child.placeholderText():
                    child.setPlainText("")
                    break
            
            QMessageBox.information(self, "删除成功", 
                                  f"设备 '{device_name}' 已成功删除！")
            
            # 保存配置到文件
            self.save_config()
            
            # 通知其他页面更新设备列表
            self.notify_device_list_updated()
    
    def rename_device(self):
        """重命名设备"""
        current_row = self.device_list.currentRow()
        
        if current_row < 0:
            QMessageBox.warning(self, "重命名失败", "请先选择一个设备")
            return
        
        device_name = self.device_list.item(current_row).text()
        
        # 输入新的设备名称
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "重命名设备", "请输入新的设备名称：", text=device_name)
        
        if ok and new_name.strip():
            new_name = new_name.strip()
            
            # 检查新名称是否已存在
            existing_devices = [self.device_list.item(i).text() for i in range(self.device_list.count())]
            if new_name in existing_devices:
                QMessageBox.warning(self, "重命名失败", f"设备名称 '{new_name}' 已存在！")
                return
            
            # 更新设备列表中的名称
            self.device_list.item(current_row).setText(new_name)
            
            # 更新配置字典中的键
            if device_name in self.device_configs:
                self.device_configs[new_name] = self.device_configs[device_name]
                del self.device_configs[device_name]
                
                # 更新配置中的设备名称
                self.device_configs[new_name]['device_name'] = new_name
                
                # 保存配置到文件
                self.save_config()
            
            QMessageBox.information(self, "重命名成功", 
                                  f"设备 '{device_name}' 已重命名为 '{new_name}'！")
            
            # 通知其他页面更新设备列表
            self.notify_device_list_updated()
    
    def notify_device_list_updated(self):
        """通知其他页面设备列表已更新"""
        try:
            # 通过父窗口获取传输数据页面
            parent = self.parent()
            while parent and not hasattr(parent, 'data_transfer_page'):
                parent = parent.parent()
            
            if parent and hasattr(parent, 'data_transfer_page'):
                data_transfer_page = parent.data_transfer_page
                if hasattr(data_transfer_page, 'update_device_list'):
                    data_transfer_page.update_device_list()
        except Exception as e:
            print(f"通知设备列表更新失败: {e}")
    
    def get_device_configs(self):
        """获取设备配置字典"""
        return self.device_configs
    
    def save_device_configs(self, configs):
        """保存设备配置到文件"""
        try:
            self.device_configs = configs
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.device_configs, f, ensure_ascii=False, indent=2)
            print(f"已保存 {len(self.device_configs)} 个设备的配置到文件")
        except Exception as e:
            print(f"保存设备配置失败: {e}")