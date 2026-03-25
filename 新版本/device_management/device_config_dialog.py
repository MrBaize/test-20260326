from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit, 
                             QPushButton, QLabel, QGroupBox, QListWidget, QListWidgetItem, 
                             QFormLayout, QMessageBox, QWidget, QFileDialog, QTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from connection_protocols.connection_manager import ConnectionManager
import json
import os


class ConnectionTestThread(QThread):
    """测试连接线程"""
    
    finished = pyqtSignal(dict)  # 测试完成信号
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
    
    def run(self):
        """执行测试连接"""
        try:
            manager = ConnectionManager()
            # 从配置字典中提取协议类型并复制配置字典
            protocol_type = self.config.get('protocol', '')
            # 创建配置副本，移除protocol字段避免参数冲突
            config_copy = self.config.copy()
            config_copy.pop('protocol', None)
            
            result = manager.test_connection(protocol_type, **config_copy)
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({
                'success': False,
                'message': f'测试连接异常: {str(e)}'
            })


class ProtocolConfigWidget(QWidget):
    """单个协议配置组件"""
    
    def __init__(self, protocol_type, parent=None):
        super().__init__(parent)
        self.protocol_type = protocol_type
        self.init_ui()
    
    def init_ui(self):
        layout = QFormLayout()
        layout.setSpacing(10)
        
        # 协议类型标签
        protocol_label = QLabel(f"协议类型: {self.protocol_type.upper()}")
        protocol_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addRow("", protocol_label)
        
        # 根据协议类型显示不同的配置字段
        if self.protocol_type in ['ssh', 'telnet', 'ftp', 'sftp']:
            # IP地址
            self.ip_edit = QLineEdit()
            self.ip_edit.setPlaceholderText("请输入IP地址")
            layout.addRow("IP地址:", self.ip_edit)
            
            # 端口
            self.port_edit = QLineEdit()
            default_ports = {
                'ssh': '22', 'telnet': '23', 'ftp': '21', 'sftp': '22'
            }
            self.port_edit.setText(default_ports.get(self.protocol_type, ''))
            self.port_edit.setPlaceholderText("请输入端口号")
            layout.addRow("端口:", self.port_edit)
            
            # 用户名
            self.username_edit = QLineEdit()
            self.username_edit.setPlaceholderText("请输入用户名")
            layout.addRow("用户名:", self.username_edit)
            
            # 密码
            self.password_edit = QLineEdit()
            self.password_edit.setPlaceholderText("请输入密码")
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addRow("密码:", self.password_edit)
            
            # Telnet特有：波特率
            if self.protocol_type == 'telnet':
                self.baudrate_combo = QComboBox()
                self.baudrate_combo.addItems(['9600', '19200', '38400', '57600', '115200'])
                layout.addRow("波特率:", self.baudrate_combo)
        
        elif self.protocol_type == 'serial':
            # 串口配置 - COM端口改为手动输入
            self.com_port_edit = QLineEdit()
            self.com_port_edit.setPlaceholderText("请输入COM端口，如COM1、COM3等")
            layout.addRow("COM端口:", self.com_port_edit)
            
            # 波特率
            self.baudrate_combo = QComboBox()
            self.baudrate_combo.addItems(['9600', '19200', '38400', '57600', '115200'])
            layout.addRow("波特率:", self.baudrate_combo)
            
            # 数据位
            self.databits_combo = QComboBox()
            self.databits_combo.addItems(['5', '6', '7', '8'])
            self.databits_combo.setCurrentText('8')
            layout.addRow("数据位:", self.databits_combo)
            
            # 校验位
            self.parity_combo = QComboBox()
            self.parity_combo.addItems(['无', '奇校验', '偶校验'])
            layout.addRow("校验位:", self.parity_combo)
            
            # 停止位
            self.stopbits_combo = QComboBox()
            self.stopbits_combo.addItems(['1', '1.5', '2'])
            layout.addRow("停止位:", self.stopbits_combo)
        
        # 按钮区域 - 测试连接和添加协议并行
        btn_layout = QHBoxLayout()
        
        # 测试连接按钮
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self.test_connection)
        btn_layout.addWidget(self.test_btn)
        
        # 添加协议按钮
        self.add_btn = QPushButton("添加协议")
        self.add_btn.clicked.connect(self.add_to_protocols)
        btn_layout.addWidget(self.add_btn)
        
        layout.addRow("", btn_layout)
        
        self.setLayout(layout)
    
    def get_config_data(self):
        """获取配置数据"""
        config = {'protocol': self.protocol_type}
        
        if self.protocol_type in ['ssh', 'telnet', 'ftp', 'sftp']:
            config.update({
                'ip': self.ip_edit.text().strip(),
                'port': int(self.port_edit.text()) if self.port_edit.text().isdigit() else 0,
                'username': self.username_edit.text().strip(),
                'password': self.password_edit.text()
            })
            
            if self.protocol_type == 'telnet':
                config['baud_rate'] = int(self.baudrate_combo.currentText())
        
        elif self.protocol_type == 'serial':
            config.update({
                'com_port': self.com_port_edit.text().strip(),
                'baud_rate': int(self.baudrate_combo.currentText()),
                'bytesize': int(self.databits_combo.currentText()),
                'parity': self.parity_combo.currentText(),
                'stopbits': float(self.stopbits_combo.currentText())
            })
        
        return config
    
    def set_config_data(self, config):
        """设置配置数据"""
        if self.protocol_type in ['ssh', 'telnet', 'ftp', 'sftp']:
            self.ip_edit.setText(config.get('ip', ''))
            self.port_edit.setText(str(config.get('port', '')))
            self.username_edit.setText(config.get('username', ''))
            self.password_edit.setText(config.get('password', ''))
            
            if self.protocol_type == 'telnet' and 'baud_rate' in config:
                self.baudrate_combo.setCurrentText(str(config['baud_rate']))
        
        elif self.protocol_type == 'serial':
            self.com_port_edit.setText(config.get('com_port', ''))
            self.baudrate_combo.setCurrentText(str(config.get('baud_rate', 9600)))
            self.databits_combo.setCurrentText(str(config.get('bytesize', 8)))
            self.parity_combo.setCurrentText(config.get('parity', '无'))
            self.stopbits_combo.setCurrentText(str(config.get('stopbits', 1)))
    
    def test_connection(self):
        """测试连接"""
        config = self.get_config_data()
        
        # 验证必填字段
        if self.protocol_type in ['ssh', 'telnet', 'ftp', 'sftp']:
            if not config['ip'] or not config['username'] or not config['password']:
                QMessageBox.warning(self, "输入错误", "请填写完整的连接信息")
                return
        elif self.protocol_type == 'serial':
            if not config['com_port']:
                QMessageBox.warning(self, "输入错误", "请选择COM端口")
                return
        
        # 禁用测试按钮，避免重复点击
        self.test_btn.setEnabled(False)
        self.test_btn.setText("测试中...")
        
        # 创建并启动测试线程
        self.test_thread = ConnectionTestThread(config)
        self.test_thread.finished.connect(self.on_test_finished)
        self.test_thread.start()
    
    def on_test_finished(self, result):
        """测试完成回调"""
        # 恢复测试按钮状态
        self.test_btn.setEnabled(True)
        self.test_btn.setText("测试连接")
        
        # 显示测试结果
        if result['success']:
            QMessageBox.information(self, "测试成功", result['message'])
        else:
            QMessageBox.critical(self, "测试失败", result['message'])
        
        # 清理线程引用
        self.test_thread = None
    
    def add_to_protocols(self):
        """添加或更新协议到设备配置列表"""
        config = self.get_config_data()
        
        # 验证必填字段
        if config['protocol'] in ['ssh', 'telnet', 'ftp', 'sftp']:
            if not config['ip'] or not config['username'] or not config['password']:
                QMessageBox.warning(self, "输入错误", "请填写完整的连接信息")
                return
        elif config['protocol'] == 'serial':
            if not config['com_port']:
                QMessageBox.warning(self, "输入错误", "请选择COM端口")
                return
        
        # 通过父窗口的对话框添加或更新协议
        parent_dialog = self.parent()
        while parent_dialog and not isinstance(parent_dialog, DeviceConfigDialog):
            parent_dialog = parent_dialog.parent()
        
        if parent_dialog and isinstance(parent_dialog, DeviceConfigDialog):
            # 检查是否处于编辑模式
            if hasattr(parent_dialog, 'editing_index') and parent_dialog.editing_index is not None:
                parent_dialog.update_protocol_from_widget(config)
            else:
                parent_dialog.add_protocol_from_widget(config)
        else:
            QMessageBox.warning(self, "错误", "无法找到设备配置对话框")


class DeviceConfigDialog(QDialog):
    """设备配置对话框"""
    
    def __init__(self, device_name="", parent=None):
        super().__init__(parent)
        self.device_name = device_name
        self.protocols = []  # 存储协议配置列表
        self.editing_index = None  # 当前编辑的协议索引
        self.init_ui()
        
        # 如果设备名称不为空，尝试加载已有的配置
        if device_name and parent:
            self.load_existing_config()
    
    def load_existing_config(self):
        """加载已有的设备配置"""
        # 通过类名查找设备管理页，避免循环导入
        parent = self.parent()
        while parent and parent.__class__.__name__ != 'DeviceManagementPage':
            parent = parent.parent()
        
        if parent and parent.__class__.__name__ == 'DeviceManagementPage':
            # 检查设备配置是否存在
            if self.device_name in parent.device_configs:
                config = parent.device_configs[self.device_name]
                self.set_device_config(config)
                
                # 更新窗口标题
                self.setWindowTitle(f"设备配置 - {self.device_name}")
    
    def init_ui(self):
        self.setWindowTitle(f"设备配置 - {self.device_name}")
        self.setGeometry(200, 200, 600, 1000)
        
        # 主布局
        main_layout = QVBoxLayout()
        
        # 上部分：协议选择和设备名称 - 固定位置
        top_widget = self.create_top_widget()
        
        # 下部分：已添加的协议列表 - 可伸缩区域
        bottom_widget = self.create_bottom_widget()
        
        # 添加到主布局，设置拉伸因子
        main_layout.addWidget(top_widget, 0)  # 不拉伸，固定位置
        main_layout.addWidget(bottom_widget, 1)  # 可拉伸
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        # 同步按钮
        sync_btn = QPushButton("同步")
        sync_btn.clicked.connect(self.sync_config)
        
        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_config)
        
        # 导入按钮
        import_btn = QPushButton("导入")
        import_btn.clicked.connect(self.import_config)
        
        button_layout.addWidget(sync_btn)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(import_btn)
        
        button_layout.addStretch()
        
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def create_top_widget(self):
        """创建上部分区域"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 设备名称组 - 固定高度
        name_group = QGroupBox("设备信息")
        name_layout = QFormLayout()
        
        self.device_name_edit = QLineEdit(self.device_name)
        self.device_name_edit.setPlaceholderText("请输入设备名称")
        name_layout.addRow("设备名称:", self.device_name_edit)
        
        name_group.setLayout(name_layout)
        # 设置设备信息组固定高度
        name_group.setFixedHeight(80)
        
        # 协议选择组
        protocol_group = QGroupBox("协议配置")
        protocol_layout = QVBoxLayout()
        
        # 协议类型选择
        protocol_form_layout = QFormLayout()
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(['SSH', 'Telnet', 'Serial', 'FTP', 'SFTP'])
        protocol_form_layout.addRow("协议类型:", self.protocol_combo)
        
        # 协议配置区域
        self.config_widget_container = QWidget()
        self.config_layout = QVBoxLayout()
        self.config_widget_container.setLayout(self.config_layout)
        
        # 协议类型改变时更新配置界面
        self.protocol_combo.currentTextChanged.connect(self.update_config_widget)
        
        protocol_layout.addLayout(protocol_form_layout)
        protocol_layout.addWidget(self.config_widget_container)
        protocol_group.setLayout(protocol_layout)
        # 设置协议配置组固定高度
        protocol_group.setFixedHeight(300)
        
        # 添加到上部分布局
        layout.addWidget(name_group)
        layout.addWidget(protocol_group)
        
        widget.setLayout(layout)
        
        # 初始化配置界面
        self.update_config_widget()
        
        return widget
    
    def create_bottom_widget(self):
        """创建下部分区域"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 已添加协议组
        protocols_group = QGroupBox("已配置协议")
        protocols_layout = QVBoxLayout()
        
        # 协议列表
        self.protocols_list = QListWidget()
        self.protocols_list.itemDoubleClicked.connect(self.edit_protocol)
        protocols_layout.addWidget(self.protocols_list)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        self.edit_btn = QPushButton("编辑")
        self.edit_btn.clicked.connect(self.edit_selected_protocol)
        
        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self.delete_selected_protocol)
        
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        
        protocols_layout.addLayout(btn_layout)
        protocols_group.setLayout(protocols_layout)
        
        layout.addWidget(protocols_group)
        widget.setLayout(layout)
        
        return widget
    
    def update_config_widget(self):
        """更新协议配置界面"""
        # 清空现有配置界面
        while self.config_layout.count():
            child = self.config_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # 创建新的配置界面
        protocol_type = self.protocol_combo.currentText().lower()
        self.current_config_widget = ProtocolConfigWidget(protocol_type)
        self.config_layout.addWidget(self.current_config_widget)
        
        # 串口协议不再需要加载可用串口列表，改为手动输入
        
    def add_protocol(self):
        """添加协议到列表"""
        if not self.current_config_widget:
            return
        
        config = self.current_config_widget.get_config_data()
        self.add_protocol_from_widget(config)
    
    def add_protocol_from_widget(self, config):
        """从协议配置组件添加协议到列表"""
        # 验证必填字段
        if config['protocol'] in ['ssh', 'telnet', 'ftp', 'sftp']:
            if not config['ip'] or not config['username'] or not config['password']:
                QMessageBox.warning(self, "输入错误", "请填写完整的连接信息")
                return
        elif config['protocol'] == 'serial':
            if not config['com_port']:
                QMessageBox.warning(self, "输入错误", "请选择COM端口")
                return
        
        # 添加到协议列表
        self.protocols.append(config)
        
        # 更新列表显示
        self.update_protocols_list()
        
        # 清空当前配置界面
        self.current_config_widget.set_config_data({})
        
        QMessageBox.information(self, "成功", "协议已添加到列表")
    
    def update_protocol_from_widget(self, config):
        """更新协议配置"""
        if self.editing_index is None:
            return
            
        # 更新协议列表中的配置
        self.protocols[self.editing_index] = config
        
        # 更新列表显示
        self.update_protocols_list()
        
        # 清空当前配置界面
        self.current_config_widget.set_config_data({})
        
        # 重置编辑状态
        self.editing_index = None
        
        # 恢复按钮文本
        if hasattr(self.current_config_widget, 'add_btn'):
            self.current_config_widget.add_btn.setText("添加协议")
        
        QMessageBox.information(self, "成功", "协议已更新")
    
    def edit_selected_protocol(self):
        """编辑选中的协议"""
        current_row = self.protocols_list.currentRow()
        if current_row >= 0:
            self.edit_protocol(self.protocols_list.currentItem())
    
    def edit_protocol(self, item):
        """编辑协议"""
        if not item:
            return
        
        index = self.protocols_list.row(item)
        if index < 0 or index >= len(self.protocols):
            return
        
        config = self.protocols[index]
        
        # 设置协议类型
        protocol_name = config['protocol'].upper()
        combo_index = self.protocol_combo.findText(protocol_name)
        if combo_index >= 0:
            self.protocol_combo.setCurrentIndex(combo_index)
        
        # 设置配置数据
        self.current_config_widget.set_config_data(config)
        
        # 标记当前正在编辑的协议索引
        self.editing_index = index
        
        # 更改按钮文本为"更新协议"
        if hasattr(self.current_config_widget, 'add_btn'):
            self.current_config_widget.add_btn.setText("更新协议")
            
        QMessageBox.information(self, "编辑模式", "协议已加载到编辑界面，修改后点击'更新协议'按钮保存更改")
    
    def delete_selected_protocol(self):
        """删除选中的协议"""
        current_row = self.protocols_list.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(self, "确认删除", 
                                       "确定要删除选中的协议吗？",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                self.protocols.pop(current_row)
                self.update_protocols_list()
    
    def update_protocols_list(self):
        """更新协议列表显示"""
        self.protocols_list.clear()
        
        for i, config in enumerate(self.protocols):
            protocol_type = config['protocol'].upper()
            
            # 构建单行显示的文本
            if protocol_type in ['SSH', 'TELNET', 'FTP', 'SFTP']:
                text = f"{protocol_type}: {config.get('ip', '')}:{config.get('port', '')} ({config.get('username', '')}/{config.get('password', '')})"
                
                # 添加可选参数
                if protocol_type == 'TELNET' and 'baud_rate' in config:
                    text += f" 波特率:{config.get('baud_rate', '')}"
                
                if 'timeout' in config:
                    text += f" 超时:{config.get('timeout', '')}s"
                    
            elif protocol_type == 'SERIAL':
                text = f"{protocol_type}: {config.get('com_port', '')} @ {config.get('baud_rate', '')}bps"
                text += f" 数据位:{config.get('bytesize', '')}"
                text += f" 校验位:{config.get('parity', '')}"
                text += f" 停止位:{config.get('stopbits', '')}"
                
                if 'timeout' in config:
                    text += f" 超时:{config.get('timeout', '')}s"
            else:
                text = f"{protocol_type}: 未知协议"
            
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, i)
            # 恢复默认高度
            item.setSizeHint(QSize(0, 25))
            self.protocols_list.addItem(item)
    
    def get_device_config(self):
        """获取设备配置数据"""
        return {
            'device_name': self.device_name_edit.text().strip(),
            'protocols': self.protocols.copy()
        }
    
    def set_device_config(self, config):
        """设置设备配置数据"""
        if 'device_name' in config:
            self.device_name_edit.setText(config['device_name'])
        
        if 'protocols' in config:
            self.protocols = config['protocols'].copy()
            self.update_protocols_list()
    
    def sync_config(self):
        """同步配置到设备管理页的设备详细信息中"""
        # 获取当前设备配置
        config = self.get_device_config()
        device_name = config['device_name']
        
        if not device_name:
            QMessageBox.warning(self, "同步失败", "设备名称不能为空")
            return
        
        # 查找设备管理页
        parent = self.parent()
        
        # 通过类名查找设备管理页，避免循环导入
        while parent and parent.__class__.__name__ != 'DeviceManagementPage':
            parent = parent.parent()
        
        if parent and parent.__class__.__name__ == 'DeviceManagementPage':
            # 保存设备配置到设备管理页
            parent.device_configs[device_name] = config
            
            # 如果设备不在列表中，添加到设备列表
            device_list = parent.device_list
            existing_devices = [device_list.item(i).text() for i in range(device_list.count())]
            if device_name not in existing_devices:
                device_list.addItem(device_name)
            
            # 更新设备详细信息显示
            detail_text = self.format_device_details(config)
            
            # 查找设备详细信息显示区域
            for child in parent.findChildren(QTextEdit):
                if child.placeholderText() and "详细信息" in child.placeholderText():
                    child.setPlainText(detail_text)
                    break
            
            # 选中刚刚同步的设备
            items = device_list.findItems(device_name, Qt.MatchFlag.MatchExactly)
            if items:
                device_list.setCurrentItem(items[0])
            
            QMessageBox.information(self, "同步成功", f"设备 '{device_name}' 的配置已同步到设备管理页")
        else:
            QMessageBox.warning(self, "同步失败", "无法找到设备管理页面")
    
    def format_device_details(self, config):
        """格式化设备详细信息显示（每种协议单独一行显示）"""
        details = f"设备名称: {config['device_name']}\n"
        details += f"协议数量: {len(config['protocols'])}\n"
        
        if config['protocols']:
            for i, protocol in enumerate(config['protocols'], 1):
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
        
        return details
    
    def save_config(self):
        """保存配置到文件"""
        config = self.get_device_config()
        device_name = config['device_name']
        
        if not device_name:
            QMessageBox.warning(self, "保存失败", "请先输入设备名称")
            return
        
        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "保存设备配置", 
            f"{device_name}_config.json", 
            "JSON文件 (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(self, "保存成功", f"设备配置已保存到:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"保存文件时出错:\n{str(e)}")
    
    def import_config(self):
        """从文件导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "导入设备配置", 
            "", 
            "JSON文件 (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 验证配置格式
                if not isinstance(config, dict) or 'device_name' not in config:
                    QMessageBox.warning(self, "导入失败", "配置文件格式不正确")
                    return
                
                # 设置设备配置
                self.set_device_config(config)
                
                QMessageBox.information(self, "导入成功", f"设备配置已从文件导入:\n{os.path.basename(file_path)}")
                
            except json.JSONDecodeError:
                QMessageBox.critical(self, "导入失败", "配置文件格式错误，无法解析")
            except Exception as e:
                QMessageBox.critical(self, "导入失败", f"导入文件时出错:\n{str(e)}")