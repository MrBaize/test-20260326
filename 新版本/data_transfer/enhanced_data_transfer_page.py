"""
增强版数据传输页面
完全按照需求重新设计的三区域布局
支持SFTP/FTP协议，大文件传输，文件夹传输
"""

import os
import sys
import json
import time
import fnmatch
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QTextEdit, QFileDialog, QMessageBox,
    QInputDialog, QLineEdit, QComboBox, QGroupBox, QDialog,
    QFormLayout, QHBoxLayout, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QMenu

from .file_transfer_engine import FileTransferEngine, TransferTask, TransferStatus
from .ui_constants import UIConstants
from .path_utils import PathUtils
from .error_handler import ErrorHandler

# 导入统一UI样式
from themes.ui_styles import get_common_stylesheet


class TransferProgressThread(QThread):
    """传输进度监控线程"""
    progress_update = pyqtSignal(dict)
    
    def __init__(self, transfer_engine):
        super().__init__()
        self.transfer_engine = transfer_engine
        self.running = True
    
    def run(self):
        while self.running:
            progress_info = self.transfer_engine.get_progress_info()
            if progress_info:
                self.progress_update.emit(progress_info)
            QThread.msleep(UIConstants.DEFAULTS['progress_update_interval'])
    
    def stop(self):
        self.running = False


class EnhancedDataTransferPage(QWidget):
    """增强版数据传输主页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(get_common_stylesheet())  # 应用统一UI样式
        self.transfer_engine = FileTransferEngine()
        self.transfer_engine.refresh_callback = self.refresh_all_files
        self.progress_thread = None
        self.current_device = None
        self.device_configs = {}
        self.protocol_combos = {}  # 保存每个设备行的协议下拉框引用
        self.init_ui()
        self.setup_context_menus()
        # 连接传输引擎的刷新信号到界面刷新函数（同时刷新本地和远程）
        self.transfer_engine.refresh_signal.connect(self.refresh_all_files)
        print("[界面初始化] 已连接刷新信号")
        # 延迟加载设备配置，确保界面完全初始化后再加载数据
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.delayed_init)
        # 设备表格的双击连接在 init_ui 方法中已处理，这里不再需要重复连接

    def refresh_all_files(self):
        """同时刷新本地和远程文件列表"""
        print("[界面刷新] 开始同时刷新本地和远程文件列表")
        self.refresh_local_files()
        self.refresh_remote_files()
        print("[界面刷新] 本地和远程文件列表刷新完成")

    def setup_context_menus(self):
        """设置右键菜单"""
        # 本地文件表右键菜单
        self.local_files_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.local_files_table.customContextMenuRequested.connect(self.show_local_context_menu)
        
        # 远程文件表右键菜单
        self.remote_files_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.remote_files_table.customContextMenuRequested.connect(self.show_remote_context_menu)

    def show_local_context_menu(self, position):
        """显示本地文件表右键菜单"""
        selected_items = self.local_files_table.selectedItems()
        if not selected_items:
            return
            
        from PyQt6.QtWidgets import QMessageBox
        menu = QMenu()
        delete_action = menu.addAction("删除")
        delete_action.triggered.connect(self.delete_local_files)
        
        menu.exec(self.local_files_table.mapToGlobal(position))

    def show_remote_context_menu(self, position):
        """显示远程文件表右键菜单"""
        if not self.current_device:
            return
            
        selected_items = self.remote_files_table.selectedItems()
        if not selected_items:
            return
            
        from PyQt6.QtWidgets import QMessageBox
        menu = QMenu()
        delete_action = menu.addAction("删除")
        delete_action.triggered.connect(self.delete_remote_files)
        
        menu.exec(self.remote_files_table.mapToGlobal(position))

    def delete_local_files(self):
        """删除本地文件"""
        selected_items = self.local_files_table.selectedItems()
        if not selected_items:
            return
            
        # 获取选中的唯一行
        rows = set()
        for item in selected_items:
            rows.add(item.row())
        
        # 确认删除
        if not ErrorHandler.ask_confirmation(self, "确认删除", f"确定要删除选中的 {len(rows)} 个项目吗？"):
            return
        
        current_path = self.local_path_input.text() or os.getcwd()
        deleted_count = 0
        failed_items = []
        
        for row in sorted(rows, reverse=True):  # 倒序删除避免索引变化
            file_name_item = self.local_files_table.item(row, 0)
            if file_name_item:
                file_name = file_name_item.text()
                file_path = PathUtils.join_paths(current_path, file_name)
                
                try:
                    if os.path.isdir(file_path):
                        import shutil
                        shutil.rmtree(file_path)
                    else:
                        os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    failed_items.append(f"{file_name} ({str(e)})")
        
        self.refresh_local_files()
        
        # 统一显示操作结果
        ErrorHandler.handle_operation_result(self, 'delete', deleted_count, failed_items)

    def delete_remote_files(self):
        """删除远程文件"""
        if not self.current_device:
            QMessageBox.warning(self, "警告", "请先连接设备")
            return
            
        selected_items = self.remote_files_table.selectedItems()
        if not selected_items:
            return
            
        # 获取选中的唯一行和文件名，同时获取文件类型
        files_to_delete = []
        for item in selected_items:
            if item.column() == 0:  # 文件名列
                row = item.row()
                file_name = item.text()
                # 获取文件类型（第1列）
                type_item = self.remote_files_table.item(row, 1)
                file_type = type_item.text() if type_item else "文件"
                files_to_delete.append({'name': file_name, 'type': file_type})
        
        if not files_to_delete:
            return
            
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除选中的 {len(files_to_delete)} 个远程项目吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            remote_path = self.remote_path_input.text() or "/"
            deleted_count = 0
            failed_files = []
            
            for file_info in files_to_delete:
                file_name = file_info['name']
                file_type = file_info['type']
                remote_file_path = os.path.join(remote_path, file_name).replace('\\', '/')
                
                print(f"[DEBUG] 尝试删除文件: {file_name}, 类型: {file_type}, 远程路径: {remote_file_path}")
                print(f"[DEBUG] 当前设备: {self.current_device}")
                print(f"[DEBUG] 设备配置: {self.device_configs.get(self.current_device, '无配置')}")
                
                try:
                    # 检查设备是否已连接
                    if self.current_device not in self.transfer_engine.connected_devices:
                        print(f"[DEBUG] 设备未连接，尝试连接...")
                        conn_result = self.transfer_engine.connect_device(
                            self.current_device, 
                            self.device_configs[self.current_device]
                        )
                        print(f"[DEBUG] 连接结果: {conn_result}")
                        if not conn_result:
                            failed_files.append(f"{file_name} (设备连接失败)")
                            continue
                    
                    # 使用 FileTransferEngine 的实际删除功能
                    print(f"[DEBUG] 调用删除方法...")
                    if file_type == "目录":
                        success = self.transfer_engine.delete_remote_directory(
                            remote_file_path, 
                            self.device_configs[self.current_device],
                            self.current_device  # 传入设备ID
                        )
                    else:
                        success = self.transfer_engine.delete_remote_file(
                            remote_file_path, 
                            self.device_configs[self.current_device],
                            self.current_device  # 传入设备ID
                        )
                    
                    print(f"[DEBUG] 删除结果: {success}")
                    
                    if success:
                        deleted_count += 1
                        print(f"[DEBUG] 删除成功: {file_name}")
                    else:
                        failed_files.append(f"{file_name} (删除失败-返回False)")
                        print(f"[DEBUG] 删除失败: {file_name}")
                        
                except Exception as e:
                    print(f"[DEBUG] 删除异常: {file_name}, 错误: {str(e)}, 类型: {type(e).__name__}")
                    import traceback
                    traceback.print_exc()
                    failed_files.append(f"{file_name} ({str(e)})")
            
            self.refresh_remote_files()
            
            # 显示结果消息
            if failed_files:
                QMessageBox.warning(self, "删除结果", 
                                   f"成功删除 {deleted_count} 个项目\n失败项目:\n" + "\n".join(failed_files))
            else:
                QMessageBox.information(self, "删除成功", f"成功删除 {deleted_count} 个项目")

    def delayed_init(self):
        """延迟初始化，确保界面完全加载后再加载数据"""
        self.load_device_configs()
        self.start_progress_monitor()

    def init_ui(self):
        """初始化界面布局"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(UIConstants.LAYOUT_CONFIG['layout_spacing'])
        main_layout.setContentsMargins(10, UIConstants.LAYOUT_CONFIG['panel_margin_top'], 10, 10)
        
        # 上部：三区域布局
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：设备管理区域
        self.left_panel = self.create_device_panel()
        top_splitter.addWidget(self.left_panel)
        
        # 中间：本地文件区域
        self.middle_panel = self.create_local_files_panel()
        top_splitter.addWidget(self.middle_panel)
        
        # 右侧：远程文件区域
        self.right_panel = self.create_remote_files_panel()
        top_splitter.addWidget(self.right_panel)
        
        # 设置分割比例（按内容自动伸缩）
        top_splitter.setStretchFactor(0, UIConstants.LAYOUT_CONFIG['left_panel_stretch'])
        top_splitter.setStretchFactor(1, UIConstants.LAYOUT_CONFIG['middle_panel_stretch'])
        top_splitter.setStretchFactor(2, UIConstants.LAYOUT_CONFIG['right_panel_stretch'])
        
        # 下部：传输进度区域
        self.bottom_panel = self.create_progress_panel()
        
        main_layout.addWidget(top_splitter, UIConstants.LAYOUT_CONFIG['top_panel_ratio'])
        main_layout.addWidget(self.bottom_panel, UIConstants.LAYOUT_CONFIG['bottom_panel_ratio'])
        
        self.setLayout(main_layout)
    
    def create_device_panel(self):
        """创建设备管理面板"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(UIConstants.LAYOUT_CONFIG['layout_spacing'])
        layout.setContentsMargins(0, UIConstants.LAYOUT_CONFIG['panel_margin_top'], 0, 0)
        
        # 设备管理组框
        device_group = QGroupBox("设备管理")
        device_layout = QVBoxLayout()
        device_layout.setSpacing(UIConstants.LAYOUT_CONFIG['layout_spacing'])
        
        # 顶部按钮栏
        top_buttons = QHBoxLayout()
        top_buttons.setSpacing(UIConstants.LAYOUT_CONFIG['button_spacing'])
        
        self.new_device_btn = QPushButton("新建")
        self.login_btn = QPushButton("登录")
        self.disconnect_btn = QPushButton("断开")
        self.refresh_devices_btn = QPushButton("刷新")
        self.edit_device_btn = QPushButton("修改")
        
        # 设置按钮固定高度和工具提示
        for btn in [self.new_device_btn, self.login_btn, self.disconnect_btn, 
                   self.refresh_devices_btn, self.edit_device_btn]:
            btn.setFixedHeight(UIConstants.LAYOUT_CONFIG['button_height'])
        
        self.new_device_btn.setToolTip("新建设备配置")
        self.login_btn.setToolTip("登录设备")
        self.disconnect_btn.setToolTip("断开设备连接")
        self.refresh_devices_btn.setToolTip("刷新设备列表")
        self.edit_device_btn.setToolTip("修改设备参数")
        
        self.new_device_btn.clicked.connect(self.new_device)
        self.login_btn.clicked.connect(self.login_device)
        self.disconnect_btn.clicked.connect(self.disconnect_device)
        self.refresh_devices_btn.clicked.connect(self.refresh_devices)
        self.edit_device_btn.clicked.connect(self.edit_device)
        
        top_buttons.addWidget(self.new_device_btn)
        top_buttons.addWidget(self.login_btn)
        top_buttons.addWidget(self.disconnect_btn)
        top_buttons.addWidget(self.refresh_devices_btn)
        top_buttons.addWidget(self.edit_device_btn)
        top_buttons.addStretch()  # 添加弹性空间，让按钮靠左
        layout.addLayout(top_buttons)
        
        # 设备列表表格
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(7)
        self.device_table.setMinimumWidth(750)
        self.device_table.setStyleSheet("""
            QTableWidget {
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 1px 3px;
            }
        """)
        self.device_table.setHorizontalHeaderLabels([
            "设备", "状态", "协议", "IP", "端口", "操作", "时间"
        ])
        
        # 设置列宽策略 - 与本地文件列表保持一致
        header = self.device_table.horizontalHeader()
        header.setSectionsMovable(True)  # 允许列头拖拽移动
        header.setDragEnabled(True)  # 启用拖拽
        header.setDragDropMode(QHeaderView.DragDropMode.InternalMove)  # 内部移动模式
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # 交互式调整模式
        # header.setStretchLastSection(True)  # 禁用最后一列拉伸，避免压缩其他列导致按钮被挡
        
        # 确保所有列都可见
        for i in range(self.device_table.columnCount()):
            self.device_table.setColumnHidden(i, False)
        
        # 设置列宽（使用常量）
        self.device_table.setColumnWidth(0, UIConstants.COLUMN_WIDTHS['device_name'])
        self.device_table.setColumnWidth(1, UIConstants.COLUMN_WIDTHS['device_status'])
        self.device_table.setColumnWidth(2, UIConstants.COLUMN_WIDTHS['protocol'])
        self.device_table.setColumnWidth(3, UIConstants.COLUMN_WIDTHS['ip_address'])
        self.device_table.setColumnWidth(4, UIConstants.COLUMN_WIDTHS['port'])
        self.device_table.setColumnWidth(5, UIConstants.COLUMN_WIDTHS['operation'])
        self.device_table.setColumnWidth(6, 150)  # 时间列固定宽度
        
        # 设置表格整体宽度策略
        self.device_table.horizontalHeader().setMinimumSectionSize(50)
        
        # 隐藏行号列（垂直表头）
        self.device_table.verticalHeader().setVisible(False)
        
        device_layout.addWidget(self.device_table)
        device_group.setLayout(device_layout)
        layout.addWidget(device_group)
        
        panel.setLayout(layout)
        return panel
    
    def create_local_files_panel(self):
        """创建本地文件面板"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(UIConstants.LAYOUT_CONFIG['layout_spacing'])
        layout.setContentsMargins(0, UIConstants.LAYOUT_CONFIG['panel_margin_top'], 0, 0)
        
        # 本地文件组框
        local_group = QGroupBox("本地文件")
        local_layout = QVBoxLayout()
        local_layout.setSpacing(UIConstants.LAYOUT_CONFIG['layout_spacing'])
        
        # 顶部工具栏
        top_toolbar = QHBoxLayout()
        top_toolbar.setSpacing(UIConstants.LAYOUT_CONFIG['button_spacing'])
        
        # 路径输入框
        self.local_path_input = QLineEdit()
        self.local_path_input.setPlaceholderText("当前路径")
        self.local_path_input.returnPressed.connect(self.on_local_path_enter)
        
        # 操作按钮
        self.local_back_btn = QPushButton("返回上层")
        self.local_new_file_btn = QPushButton("新建文件")
        self.local_new_folder_btn = QPushButton("新建文件夹")
        self.local_rename_btn = QPushButton("重命名")
        self.local_upload_btn = QPushButton("上传文件")
        
        # 设置按钮固定高度和工具提示
        for btn in [self.local_back_btn, self.local_new_file_btn, self.local_new_folder_btn, 
                   self.local_rename_btn, self.local_upload_btn]:
            btn.setFixedHeight(UIConstants.LAYOUT_CONFIG['button_height'])
        
        self.local_back_btn.setToolTip("返回上一层目录")
        self.local_new_file_btn.setToolTip("创建新文件")
        self.local_new_folder_btn.setToolTip("创建新文件夹")
        self.local_rename_btn.setToolTip("重命名选中的文件或文件夹")
        self.local_upload_btn.setToolTip("上传文件到远程设备")
        
        self.local_back_btn.clicked.connect(self.go_to_parent_directory_local)
        self.local_new_file_btn.clicked.connect(self.create_local_file)
        self.local_new_folder_btn.clicked.connect(self.create_local_folder)
        self.local_rename_btn.clicked.connect(self.rename_local)
        self.local_upload_btn.clicked.connect(self.upload_files)
        
        top_toolbar.addWidget(QLabel("路径:"))
        top_toolbar.addWidget(self.local_path_input)
        top_toolbar.addWidget(self.local_back_btn)
        top_toolbar.addWidget(self.local_new_file_btn)
        top_toolbar.addWidget(self.local_new_folder_btn)
        top_toolbar.addWidget(self.local_rename_btn)
        top_toolbar.addWidget(self.local_upload_btn)
        top_toolbar.addStretch()  # 添加弹性空间
        layout.addLayout(top_toolbar)
        
        # 文件列表表格
        self.local_files_table = QTableWidget()
        self.local_files_table.setColumnCount(5)
        self.local_files_table.setHorizontalHeaderLabels([
            "文件名", "文件类型", "修改时间", "文件大小", "文件权限"
        ])
        
        # 隐藏行号列（垂直表头）
        self.local_files_table.verticalHeader().setVisible(False)
        
        # 设置多选模式 - 支持Ctrl键多选
        self.local_files_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.local_files_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # 设置列宽策略 - 支持拖拽调整
        local_header = self.local_files_table.horizontalHeader()
        local_header.setSectionsMovable(True)  # 允许列头拖拽移动
        local_header.setDragEnabled(True)  # 启用拖拽
        local_header.setDragDropMode(QHeaderView.DragDropMode.InternalMove)  # 内部移动模式
        local_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # 交互式调整模式
        local_header.setStretchLastSection(True)
        
        # 启用排序功能但隐藏排序指示器
        self.local_files_table.setSortingEnabled(True)
        # 使用样式表彻底隐藏排序指示器
        self.local_files_table.setStyleSheet("""
            QHeaderView::section {
                padding: 4px;
            }
            QHeaderView::down-arrow, QHeaderView::up-arrow {
                width: 0px;
                height: 0px;
            }
        """)
        
        # 设置具体列宽（使用常量）
        self.local_files_table.setColumnWidth(0, UIConstants.COLUMN_WIDTHS['file_name'])
        self.local_files_table.setColumnWidth(1, UIConstants.COLUMN_WIDTHS['file_type'])
        self.local_files_table.setColumnWidth(2, UIConstants.COLUMN_WIDTHS['mod_time'])
        self.local_files_table.setColumnWidth(3, UIConstants.COLUMN_WIDTHS['file_size'])
        self.local_files_table.setColumnWidth(4, UIConstants.COLUMN_WIDTHS['file_permissions'])
        
        self.local_files_table.doubleClicked.connect(self.local_file_double_click)
        local_layout.addWidget(self.local_files_table)
        local_group.setLayout(local_layout)
        layout.addWidget(local_group)
        
        # 初始化本地文件列表
        current_path = os.getcwd()
        self.load_local_files(current_path)
        
        panel.setLayout(layout)
        return panel
    
    def create_remote_files_panel(self):
        """创建远程文件面板"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(UIConstants.LAYOUT_CONFIG['layout_spacing'])
        layout.setContentsMargins(0, UIConstants.LAYOUT_CONFIG['panel_margin_top'], 0, 0)
        
        # 远程文件组框
        remote_group = QGroupBox("远程文件")
        remote_layout = QVBoxLayout()
        remote_layout.setSpacing(UIConstants.LAYOUT_CONFIG['layout_spacing'])
        
        # 顶部工具栏
        top_toolbar = QHBoxLayout()
        top_toolbar.setSpacing(UIConstants.LAYOUT_CONFIG['button_spacing'])
        
        # 路径输入框
        self.remote_path_input = QLineEdit()
        self.remote_path_input.setPlaceholderText("远程路径")
        self.remote_path_input.returnPressed.connect(self.on_remote_path_enter)
        
        # 操作按钮
        self.remote_back_btn = QPushButton("返回上层")
        self.remote_new_file_btn = QPushButton("新建文件")
        self.remote_new_folder_btn = QPushButton("新建文件夹")
        self.remote_rename_btn = QPushButton("重命名")
        self.remote_download_btn = QPushButton("下载文件")
        
        # 设置按钮固定高度和工具提示
        for btn in [self.remote_back_btn, self.remote_new_file_btn, self.remote_new_folder_btn, 
                   self.remote_rename_btn, self.remote_download_btn]:
            btn.setFixedHeight(UIConstants.LAYOUT_CONFIG['button_height'])
        
        self.remote_back_btn.setToolTip("返回上一层目录")
        self.remote_new_file_btn.setToolTip("创建远程文件")
        self.remote_new_folder_btn.setToolTip("创建远程文件夹")
        self.remote_rename_btn.setToolTip("重命名远程文件或文件夹")
        self.remote_download_btn.setToolTip("下载文件到本地")
        
        self.remote_back_btn.clicked.connect(self.go_to_parent_directory)
        self.remote_new_file_btn.clicked.connect(self.create_remote_file)
        self.remote_new_folder_btn.clicked.connect(self.create_remote_folder)
        self.remote_rename_btn.clicked.connect(self.rename_remote)
        self.remote_download_btn.clicked.connect(self.download_files)
        
        top_toolbar.addWidget(QLabel("路径:"))
        top_toolbar.addWidget(self.remote_path_input)
        top_toolbar.addWidget(self.remote_back_btn)
        top_toolbar.addWidget(self.remote_new_file_btn)
        top_toolbar.addWidget(self.remote_new_folder_btn)
        top_toolbar.addWidget(self.remote_rename_btn)
        top_toolbar.addWidget(self.remote_download_btn)
        top_toolbar.addStretch()  # 添加弹性空间
        layout.addLayout(top_toolbar)
        
        # 文件列表表格
        self.remote_files_table = QTableWidget()
        self.remote_files_table.setColumnCount(5)
        self.remote_files_table.setHorizontalHeaderLabels([
            "文件名", "文件类型", "修改时间", "文件大小", "文件权限"
        ])
        
        # 隐藏行号列（垂直表头）
        self.remote_files_table.verticalHeader().setVisible(False)
        
        # 设置多选模式 - 支持Ctrl键多选
        self.remote_files_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.remote_files_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # 设置列宽策略 - 支持拖拽调整
        remote_header = self.remote_files_table.horizontalHeader()
        remote_header.setSectionsMovable(True)  # 允许列头拖拽移动
        remote_header.setDragEnabled(True)  # 启用拖拽
        remote_header.setDragDropMode(QHeaderView.DragDropMode.InternalMove)  # 内部移动模式
        remote_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # 交互式调整模式
        remote_header.setStretchLastSection(True)
        
        # 启用排序功能但隐藏排序指示器
        self.remote_files_table.setSortingEnabled(True)
        # 使用样式表彻底隐藏排序指示器
        self.remote_files_table.setStyleSheet("""
            QHeaderView::section {
                padding: 4px;
            }
            QHeaderView::down-arrow, QHeaderView::up-arrow {
                width: 0px;
                height: 0px;
            }
        """)
        
        # 设置初始列宽，确保文件名能完整显示（使用常量）
        self.remote_files_table.setColumnWidth(0, UIConstants.COLUMN_WIDTHS['file_name'])
        self.remote_files_table.setColumnWidth(1, UIConstants.COLUMN_WIDTHS['file_type'])
        self.remote_files_table.setColumnWidth(2, UIConstants.COLUMN_WIDTHS['mod_time'])
        self.remote_files_table.setColumnWidth(3, UIConstants.COLUMN_WIDTHS['file_size'])
        self.remote_files_table.setColumnWidth(4, UIConstants.COLUMN_WIDTHS['file_permissions'])
        
        self.remote_files_table.doubleClicked.connect(self.remote_file_double_click)
        remote_layout.addWidget(self.remote_files_table)
        remote_group.setLayout(remote_layout)
        layout.addWidget(remote_group)
        
        panel.setLayout(layout)
        return panel
    
    def create_progress_panel(self):
        """创建传输进度面板"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(UIConstants.LAYOUT_CONFIG['layout_spacing'])
        
        # 传输进度显示
        progress_group = QGroupBox("传输进度")
        progress_layout = QVBoxLayout()
        
        # 设备传输进度表格
        self.device_progress_table = QTableWidget()
        self.device_progress_table.setColumnCount(12)
        self.device_progress_table.setHorizontalHeaderLabels([
            "设备名称", "传输状态", "传输文件", "传输进度", "平均速度", 
            "MD5校验", "MD5计算", "剩余时间", "本地MD5", "远程MD5",
            "已完成文件", "MD5历史"
        ])
        
        # 设置列宽策略 - 支持拖拽调整
        progress_header = self.device_progress_table.horizontalHeader()
        progress_header.setSectionsMovable(True)  # 允许列头拖拽移动
        progress_header.setDragEnabled(True)  # 启用拖拽
        progress_header.setDragDropMode(QHeaderView.DragDropMode.InternalMove)  # 内部移动模式
        progress_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # 交互式调整模式
        progress_header.setStretchLastSection(True)
        
        progress_layout.addWidget(self.device_progress_table)
        
        # 双击查看MD5历史详情
        self.device_progress_table.cellDoubleClicked.connect(self.show_md5_history_detail)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        control_layout.setSpacing(UIConstants.LAYOUT_CONFIG['button_spacing'])
        
        self.pause_btn = QPushButton("暂停")
        self.resume_btn = QPushButton("继续")
        self.cancel_btn = QPushButton("取消")
        
        # 设置按钮固定高度和工具提示
        for btn in [self.pause_btn, self.resume_btn, self.cancel_btn]:
            btn.setFixedHeight(UIConstants.LAYOUT_CONFIG['button_height'])
        
        self.pause_btn.setToolTip("暂停当前传输")
        self.resume_btn.setToolTip("继续暂停的传输")
        self.cancel_btn.setToolTip("取消所有传输")
        
        self.pause_btn.clicked.connect(self.pause_transfer)
        self.resume_btn.clicked.connect(self.resume_transfer)
        self.cancel_btn.clicked.connect(self.cancel_transfer)
        
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.resume_btn)
        control_layout.addWidget(self.cancel_btn)
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        panel.setLayout(layout)
        return panel
    
    # 设备管理相关方法
    def load_device_configs(self):
        """从设备管理页面加载设备配置，合并同设备的 SFTP/FTP 协议到一行"""
        try:
            with open('device_configs.json', 'r', encoding='utf-8') as f:
                all_configs = json.load(f)
            
            print(f"[DEBUG] 加载设备配置，共 {len(all_configs)} 个设备")
            
            self.device_configs = {}
            for device_id, device_data in all_configs.items():
                device_name = device_data.get("device_name", device_id)
                print(f"[DEBUG] 处理设备: {device_name} ({device_id})")
                
                # 收集该设备的 SFTP/FTP 协议
                protocols = []
                protocol_configs = []  # 保留每个协议的详细配置
                
                for i, proto_conf in enumerate(device_data.get("protocols", [])):
                    protocol_name = proto_conf.get("protocol", "")
                    print(f"[DEBUG]   协议 {i+1}: {protocol_name}")
                    
                    protocol_lower = protocol_name.lower()
                    if protocol_lower in ("ftp", "sftp"):
                        protocols.append(protocol_name.upper())
                        protocol_configs.append(proto_conf)
                        print(f"[DEBUG]      -> 匹配到协议: {protocol_name.upper()}")
                
                print(f"[DEBUG]   设备 {device_name} 找到 {len(protocols)} 个SFTP/FTP协议")
                
                if protocols:
                    # 用设备ID作为键，合并协议信息
                    unique_key = device_id
                    config = {
                        "name": device_name,
                        "protocols": protocols,  # ["SFTP", "FTP"]
                        "protocol_configs": protocol_configs,  # 原始配置列表
                        "last_refresh": device_data.get("last_refresh", "")
                    }
                    self.device_configs[unique_key] = config
                    print(f"[DEBUG]   设备 {device_name} 配置已添加")
                else:
                    print(f"[ERROR] 设备 {device_name} 没有SFTP/FTP协议配置")
            
            print(f"[DEBUG] 最终加载的设备数量: {len(self.device_configs)}")
            
            self.refresh_devices()
            
        except FileNotFoundError:
            self.device_configs = {}
            print("[ERROR] 设备配置文件不存在")
        except Exception as e:
            self.device_configs = {}
            print(f"[ERROR] 加载设备配置失败: {e}")
    
    def update_device_list(self):
        """更新设备列表（响应设备管理页面的更新通知）"""
        print("[传输数据页] 接收到设备列表更新通知，正在重新加载设备配置...")
        self.load_device_configs()
        print("[传输数据页] 设备列表已更新")
    
    def refresh_devices(self):
        """刷新设备列表"""
        self.device_table.setRowCount(0)
        # 清空 combobox 映射
        self.protocol_combos.clear()
        
        for device_id, config in self.device_configs.items():
            row = self.device_table.rowCount()
            self.device_table.insertRow(row)
            
            # 设备名称
            self.device_table.setItem(row, 0, QTableWidgetItem(config.get('name', device_id)))
            
            # 连接状态
            status_item = QTableWidgetItem("未连接")
            status_item.setForeground(Qt.GlobalColor.red)
            self.device_table.setItem(row, 1, status_item)
            
            # 协议类型（下拉选择）
            protocol_combo = QComboBox()
            protocol_combo.setStyleSheet("""
                QComboBox {
                    min-width: 60px;
                    padding: 2px 5px;
                    font-size: 11px;
                }
                QComboBox::drop-down {
                    width: 18px;
                }
            """)
            protocol_combo.setFixedHeight(20)
            protocol_combo.addItems(config.get('protocols', []))
            if config.get('protocols'):
                protocol_combo.setCurrentIndex(0)
            # 保存 combobox 引用
            self.protocol_combos[(device_id, row)] = protocol_combo
            # 连接信号，传入 device_id 和 row
            protocol_combo.currentTextChanged.connect(
                lambda text, d_id=device_id, r=row: self.update_device_protocol(d_id, text, r)
            )
            self.device_table.setCellWidget(row, 2, protocol_combo)
            
            # IP 地址（获取第一个FTP或SFTP协议的配置）
            protocol_configs = config.get('protocol_configs', [])
            ftp_sftp_configs = [pc for pc in protocol_configs if pc.get('protocol', '').lower() in ('ftp', 'sftp')]
            
            if ftp_sftp_configs:
                first_proto = ftp_sftp_configs[0]
                ip_text = first_proto.get('ip', '')
                port_text = str(first_proto.get('port', ''))
            else:
                ip_text = ''
                port_text = ''
            
            # 设置IP和端口项
            ip_item = QTableWidgetItem(ip_text)
            self.device_table.setItem(row, 3, ip_item)
            
            port_item = QTableWidgetItem(port_text)
            self.device_table.setItem(row, 4, port_item)
            
            # 操作按钮（第5列）
            button_layout = QHBoxLayout()
            button_layout.setContentsMargins(1, 1, 1, 1)
            button_layout.setSpacing(2)
            connect_btn = QPushButton("连接")
            connect_btn.setFixedHeight(22)  # 减小按钮高度
            connect_btn.setFixedWidth(60)  # 固定按钮宽度
            connect_btn.setStyleSheet("""
                QPushButton {
                    min-width: 60px;
                    max-width: 60px;
                    padding: 2px 4px;
                    font-size: 11px;
                }
            """)
            connect_btn.setToolTip("连接该设备")
            connect_btn.clicked.connect(lambda checked, d_id=device_id, r=row: self.connect_device_action(d_id, r))
            button_layout.addWidget(connect_btn)
            
            button_widget = QWidget()
            button_widget.setLayout(button_layout)
            # 保护：确保 widget 创建成功再设置到表格
            if button_widget is not None:
                button_widget.setFixedWidth(65)  # 固定按钮区域宽度
                self.device_table.setCellWidget(row, 5, button_widget)
            
            # 设置行高，保持紧凑
            self.device_table.setRowHeight(row, 28)
            
            # 刷新时间（第6列）
            self.device_table.setItem(row, 6, QTableWidgetItem(config.get('last_refresh', "从未刷新")))
        
        # 强制刷新表格显示
        self.device_table.viewport().update()
        self.device_table.repaint()
        self.device_table.show()
        
        # 强制刷新整个面板
        self.update()

    def update_device_protocol(self, device_id, protocol, row):
        """更新设备协议，并同步刷新表格中的 IP 和端口显示"""
        config = self.device_configs.get(device_id, {})
        # 找到该协议对应的配置
        proto_conf = None
        for pc in config.get('protocol_configs', []):
            if pc.get('protocol', '').lower() == protocol.lower():
                proto_conf = pc
                break
        if proto_conf:
            ip_item = self.device_table.item(row, 3)
            if ip_item:
                ip_item.setText(proto_conf.get('ip', ''))
            port_item = self.device_table.item(row, 4)
            if port_item:
                port_item.setText(str(proto_conf.get('port', '')))

    def new_device(self):
        """新建设备"""
        QMessageBox.information(self, "提示", "新建设备功能需要在设备管理页面实现")
    
    def login_device(self):
        """登录设备"""
        if not self.device_configs:
            QMessageBox.warning(self, "警告", "没有可用的设备配置")
            return
        QMessageBox.information(self, "提示", "请在设备列表中点击具体设备的连接按钮")
    
    def disconnect_device(self):
        """断开设备连接"""
        if self.current_device:
            self.transfer_engine.disconnect_device(self.current_device)
            self.current_device = None
        else:
            QMessageBox.warning(self, "警告", "没有已连接的设备")
    
    def edit_device(self):
        """修改设备参数"""
        if not self.device_configs:
            QMessageBox.warning(self, "警告", "没有可用的设备配置")
            return
        
        # 选择要修改的设备
        device_names = list(self.device_configs.keys())
        device_name, ok = QInputDialog.getItem(self, "选择设备", "选择要修改的设备:", device_names, 0, False)
        
        if ok and device_name:
            self.edit_device_parameters(device_name)
    
    def edit_device_parameters(self, device_id):
        """编辑设备参数 - 使用列对齐布局"""
        config = self.device_configs.get(device_id, {})
        
        # 创建参数编辑对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(f"编辑设备参数 - {device_id}")
        dialog.setModal(True)
        dialog.resize(400, 280)
        
        layout = QVBoxLayout(dialog)
        
        # 使用表单布局实现标签和输入框对齐
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(15)
        
        # IP地址
        lbl_ip = QLabel("IP地址:")
        le_ip = QLineEdit(config.get('host', ''))
        le_ip.setMinimumWidth(200)
        form_layout.addRow(lbl_ip, le_ip)
        
        # 端口
        lbl_port = QLabel("端口:")
        le_port = QLineEdit(str(config.get('port', 22)))
        le_port.setMinimumWidth(200)
        form_layout.addRow(lbl_port, le_port)
        
        # 用户名
        lbl_user = QLabel("用户名:")
        le_user = QLineEdit(config.get('username', ''))
        le_user.setMinimumWidth(200)
        form_layout.addRow(lbl_user, le_user)
        
        # 密码
        lbl_pass = QLabel("密码:")
        le_pass = QLineEdit(config.get('password', ''))
        le_pass.setEchoMode(QLineEdit.EchoMode.Password)
        le_pass.setMinimumWidth(200)
        form_layout.addRow(lbl_pass, le_pass)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(3)  # 按钮间距更小，与设备管理页面一致
        
        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")
        
        # 设置按钮固定高度和工具提示
        save_btn.setFixedHeight(25)
        cancel_btn.setFixedHeight(25)
        save_btn.setToolTip("保存参数设置")
        cancel_btn.setToolTip("取消编辑")
        
        def save_parameters():
            # 更新设备配置
            self.device_configs[device_id].update({
                'host': ip_input.text(),
                'port': int(port_input.text() or 22),
                'username': user_input.text(),
                'password': pwd_input.text()
            })
            
            # 保存到配置文件
            self.save_device_configs()
            dialog.accept()
        
        save_btn.clicked.connect(save_parameters)
        cancel_btn.clicked.connect(dialog.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        button_layout.addStretch()  # 添加弹性空间
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def connect_device_action(self, device_id, row):
        """连接特定设备（使用当前选择的协议）"""
        if device_id not in self.device_configs:
            return
        
        config = self.device_configs[device_id]
        # 获取当前选择的协议
        combo = self.protocol_combos.get((device_id, row))
        if not combo:
            QMessageBox.warning(self, "警告", "无法获取协议选择")
            return
        selected_protocol = combo.currentText()
        
        # 找到该协议对应的配置
        proto_conf = None
        for pc in config.get('protocol_configs', []):
            if pc.get('protocol', '').upper() == selected_protocol.upper():
                proto_conf = pc
                break
        if not proto_conf:
            QMessageBox.warning(self, "警告", f"找不到 {selected_protocol} 的配置")
            return
        
        # 构造连接所需配置 - 同时设置 host 和 ip 字段以确保兼容性
        conn_config = {
            "protocol": selected_protocol.upper(),
            "host": proto_conf.get('ip', ''),  # 使用 ip 字段的值作为 host
            "ip": proto_conf.get('ip', ''),      # 保留原始 ip 字段
            "port": int(proto_conf.get('port', 22 if selected_protocol.upper() == 'SFTP' else 21)),
            "username": proto_conf.get('username', ''),
            "password": proto_conf.get('password', '')
        }
        
        try:
            # 构造完整的设备配置，包含协议配置列表
            full_device_config = {
                "protocol_configs": [conn_config],  # 将单个配置包装成列表
                "protocols": [conn_config]  # 兼容性字段
            }
            
            # 连接设备
            success = self.transfer_engine.connect_device(device_id, full_device_config)
            
            if success:
                self.current_device = device_id
                print(f"[DEBUG] 设备连接成功，设置当前设备为: {self.current_device}")
                
                # 更新设备状态
                self.update_device_status(device_id, "已连接", Qt.GlobalColor.green)
                
                # 刷新远程文件列表
                self.refresh_remote_files()
                
                # 检查远程文件列表是否为空
                if self.remote_files_table.rowCount() == 0:
                    QMessageBox.warning(self, "连接警告", "设备连接成功，但无法获取远程文件列表，请检查网络和设备配置")
                else:
                    print(f"[DEBUG] 远程文件列表刷新成功，行数: {self.remote_files_table.rowCount()}")
            else:
                QMessageBox.warning(self, "连接失败", f"设备 {config.get('name', device_id)} 连接失败")
                
        except Exception as e:
            QMessageBox.warning(self, "连接失败", f"连接设备失败: {str(e)}")
    

    
    def update_device_status(self, device_id, status, color=Qt.GlobalColor.black):
        """更新设备状态显示"""
        for row in range(self.device_table.rowCount()):
            item = self.device_table.item(row, 0)
            if item and item.text() == device_id:
                status_item = self.device_table.item(row, 1)
                if status_item:
                    status_item.setText(status)
                    status_item.setForeground(color)
                
                # 更新刷新时间（第6列）
                time_item = self.device_table.item(row, 6)
                if time_item:
                    time_item.setText(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                break
    
    def save_device_configs(self):
        """保存设备配置到文件"""
        try:
            # 读取原始配置
            with open('device_configs.json', 'r', encoding='utf-8') as f:
                all_configs = json.load(f)
            
            # 更新SFTP/FTP设备的配置
            for device_id, config in self.device_configs.items():
                if device_id in all_configs:
                    all_configs[device_id].update(config)
            
            # 保存回文件
            with open('device_configs.json', 'w', encoding='utf-8') as f:
                json.dump(all_configs, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            pass
    
    # 文件操作相关方法
    def create_local_file(self):
        """创建本地文件"""
        file_name, ok = QInputDialog.getText(self, "新建文件", "请输入文件名:")
        if ok and file_name:
            current_path = self.local_path_input.text() or os.getcwd()
            file_path = os.path.join(current_path, file_name)
            
            try:
                with open(file_path, 'w') as f:
                    f.write('')
                self.refresh_local_files()
            except Exception as e:
                QMessageBox.critical(self, "创建文件失败", f"创建文件时出错: {str(e)}")
    
    def create_local_folder(self):
        """创建本地文件夹"""
        folder_name, ok = QInputDialog.getText(self, "新建文件夹", "请输入文件夹名称:")
        if ok and folder_name:
            current_path = self.local_path_input.text() or os.getcwd()
            folder_path = os.path.join(current_path, folder_name)
            
            try:
                os.makedirs(folder_path, exist_ok=True)
                self.refresh_local_files()
            except Exception as e:
                QMessageBox.critical(self, "创建文件夹失败", f"创建文件夹时出错: {str(e)}")
    
    def rename_local(self):
        """重命名本地文件"""
        selected_items = self.local_files_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请选择要重命名的文件")
            return
        
        current_name = selected_items[0].text()
        new_name, ok = QInputDialog.getText(self, "重命名", "请输入新名称:", text=current_name)
        
        if ok and new_name and new_name != current_name:
            current_path = self.local_path_input.text() or os.getcwd()
            old_path = os.path.join(current_path, current_name)
            new_path = os.path.join(current_path, new_name)
            
            try:
                os.rename(old_path, new_path)
                self.refresh_local_files()
            except Exception as e:
                QMessageBox.critical(self, "重命名失败", f"重命名文件时出错: {str(e)}")
    
    def upload_files(self):
        """上传文件 - 支持文件和目录"""
        if not self.current_device:
            QMessageBox.warning(self, "警告", "请先连接设备")
            return
        
        # 弹出选择对话框，让用户选择上传文件还是目录
        choice = QMessageBox.question(self, "上传", "是否要上传整个目录？",
                                     QMessageBox.StandardButton.Yes | 
                                     QMessageBox.StandardButton.No |
                                     QMessageBox.StandardButton.Cancel)
        
        if choice == QMessageBox.StandardButton.Cancel:
            return
        
        if choice == QMessageBox.StandardButton.Yes:
            # 上传目录
            local_dir = QFileDialog.getExistingDirectory(self, "选择要上传的目录",
                                                        self.local_path_input.text() or os.getcwd())
            if local_dir:
                remote_path = self.remote_path_input.text() or "/"
                dir_name = os.path.basename(local_dir)
                remote_dir_path = os.path.join(remote_path, dir_name).replace('\\', '/')
                
                try:
                    # 获取设备配置
                    conn_config = self.transfer_engine.get_device_config(self.current_device)
                    if not conn_config:
                        QMessageBox.warning(self, "错误", "无法获取设备连接配置")
                        return
                    
                    # 使用 upload_file 上传目录（会创建一个目录任务）
                    task_id = self.transfer_engine.upload_file(local_dir, remote_dir_path, conn_config)
                    
                    if task_id:
                        QMessageBox.information(self, "上传", f"已开始上传目录")
                        # 添加到传输进度表格
                        task = TransferTask(task_id, local_dir, remote_dir_path, 
                                         self.device_configs[self.current_device], "upload")
                        self.add_transfer_task_to_progress(task)
                    
                except Exception as e:
                    QMessageBox.warning(self, "上传失败", f"上传目录时出错: {str(e)}")
        else:
            # 上传文件
            files = QFileDialog.getOpenFileNames(self, "选择要上传的文件", 
                                               self.local_path_input.text() or os.getcwd())[0]
            
            if files:
                remote_path = self.remote_path_input.text() or "/"
                uploaded_count = 0
                failed_files = []
                
                for file_path in files:
                    try:
                        file_name = os.path.basename(file_path)
                        remote_file_path = os.path.join(remote_path, file_name).replace('\\', '/')
                        
                        # 跳过配置文件上传（防止系统文件被覆盖）
                        if file_name.lower() in ['device_configs.json', 'requirements.txt']:
                            failed_files.append(f"{file_name} (系统配置文件，跳过上传)")
                            continue
                        
                        # 获取设备配置并添加设备ID和协议信息
                        conn_config = self.transfer_engine.get_device_config(self.current_device)
                        if not conn_config:
                            failed_files.append(f"{file_name} (无法获取配置)")
                            continue
                        
                        # 复制配置并添加设备ID和协议信息
                        device_config = self.device_configs[self.current_device].copy()
                        device_config['id'] = self.current_device
                        device_config['protocol'] = conn_config.get('protocol', 'SFTP')
                        device_config['host'] = conn_config.get('host', '')
                        device_config['port'] = conn_config.get('port', 22)
                        device_config['username'] = conn_config.get('username', '')
                        device_config['password'] = conn_config.get('password', '')
                        
                        # 添加到传输队列
                        task_id = self.transfer_engine.upload_file(file_path, remote_file_path, device_config)
                        
                        if task_id:
                            uploaded_count += 1
                            # 添加到传输进度表格 - 创建基本任务信息
                            task = TransferTask(task_id, file_path, remote_file_path, 
                                             device_config, "upload")
                            self.add_transfer_task_to_progress(task)
                        else:
                            failed_files.append(file_name)
                            
                    except Exception as e:
                        failed_files.append(f"{os.path.basename(file_path)} ({str(e)})")
                
                # 显示上传结果
                if uploaded_count > 0:
                    QMessageBox.information(self, "上传", f"成功添加 {uploaded_count} 个文件到传输队列")
                    # 立即刷新远程文件列表（实时显示）
                    self.refresh_remote_files()
                
                if failed_files:
                    QMessageBox.warning(self, "上传失败", f"以下文件上传失败:\n" + "\n".join(failed_files))
    
    def create_remote_file(self):
        """创建远程文件"""
        if not self.current_device:
            QMessageBox.warning(self, "警告", "请先连接设备")
            return
        
        file_name, ok = QInputDialog.getText(self, "新建远程文件", "请输入文件名:")
        if ok and file_name:
            remote_path = self.remote_path_input.text() or "/"
            remote_file_path = os.path.join(remote_path, file_name).replace('\\', '/')
            
            # 这里实现远程文件创建逻辑
            QMessageBox.information(self, "提示", "远程文件创建功能待实现")
    
    def create_remote_folder(self):
        """创建远程文件夹"""
        if not self.current_device:
            QMessageBox.warning(self, "警告", "请先连接设备")
            return
        
        folder_name, ok = QInputDialog.getText(self, "新建远程文件夹", "请输入文件夹名称:")
        if ok and folder_name:
            remote_path = self.remote_path_input.text() or "/"
            remote_folder_path = os.path.join(remote_path, folder_name).replace('\\', '/')
            
            # 获取当前选择的协议
            protocol = self.get_current_protocol()
            
            try:
                if protocol.upper() == 'SFTP':
                    # 使用SFTP创建文件夹
                    success = self.create_remote_folder_sftp(remote_folder_path)
                elif protocol.upper() == 'FTP':
                    # 使用FTP创建文件夹
                    success = self.create_remote_folder_ftp(remote_folder_path)
                else:
                    QMessageBox.warning(self, "错误", f"不支持的协议类型: {protocol}")
                    return
                
                if success:
                    QMessageBox.information(self, "成功", f"文件夹 '{folder_name}' 创建成功！")
                    # 刷新远程文件列表
                    self.refresh_remote_files()
                else:
                    QMessageBox.warning(self, "失败", "文件夹创建失败")
                    
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建文件夹时出错: {str(e)}")
    
    def rename_remote(self):
        """重命名远程文件"""
        if not self.current_device:
            QMessageBox.warning(self, "警告", "请先连接设备")
            return
        
        selected_items = self.remote_files_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请选择要重命名的文件")
            return
        
        # 这里实现远程文件重命名逻辑
        QMessageBox.information(self, "提示", "远程文件重命名功能待实现")
    
    def download_files(self):
        """下载文件"""
        if not self.current_device:
            QMessageBox.warning(self, "警告", "请先连接设备")
            return
        
        selected_items = self.remote_files_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请选择要下载的文件")
            return
        
        # 获取下载目录
        local_dir = QFileDialog.getExistingDirectory(self, "选择下载目录", 
                                                   self.local_path_input.text() or os.getcwd())
        
        if local_dir:
            task_ids = []
            downloaded_count = 0
            failed_files = []
            
            for item in selected_items:
                if item.column() == 0:  # 文件名列
                    remote_file_name = item.text()
                    remote_path = self.remote_path_input.text() or "/"
                    remote_file_path = os.path.join(remote_path, remote_file_name).replace('\\', '/')
                    local_file_path = os.path.join(local_dir, remote_file_name)
                    
                    try:
                        # 获取设备配置并添加设备ID和协议信息
                        device_config = self.device_configs[self.current_device].copy()
                        device_config['id'] = self.current_device
                        
                        # 从已连接设备获取实际使用的协议配置
                        conn_config = self.transfer_engine.get_device_config(self.current_device)
                        if conn_config:
                            device_config['protocol'] = conn_config.get('protocol', 'SFTP')
                            device_config['host'] = conn_config.get('host', '')
                            device_config['port'] = conn_config.get('port', 22)
                            device_config['username'] = conn_config.get('username', '')
                            device_config['password'] = conn_config.get('password', '')
                        else:
                            # 如果没有连接配置，使用第一个协议配置
                            protocol_configs = device_config.get('protocol_configs', [])
                            if protocol_configs:
                                first_proto = protocol_configs[0]
                                device_config['protocol'] = first_proto.get('protocol', 'SFTP')
                                device_config['host'] = first_proto.get('ip', '')
                                device_config['port'] = first_proto.get('port', 22)
                                device_config['username'] = first_proto.get('username', '')
                                device_config['password'] = first_proto.get('password', '')
                        
                        # 添加到传输队列
                        task_id = self.transfer_engine.download_file(remote_file_path, local_file_path, device_config)
                        if task_id:
                            task_ids.append(task_id)
                            downloaded_count += 1
                            # 添加到传输进度表格 - 创建基本任务信息
                            task = TransferTask(task_id, local_file_path, remote_file_path, 
                                             device_config, "download")
                            self.add_transfer_task_to_progress(task)
                        else:
                            failed_files.append(remote_file_name)
                    except Exception as e:
                        failed_files.append(f"{remote_file_name} ({str(e)})")
            
            # 显示下载结果
            if downloaded_count > 0:
                QMessageBox.information(self, "下载", f"已开始下载 {downloaded_count} 个文件")
            
            if failed_files:
                QMessageBox.warning(self, "下载失败", f"以下文件下载失败:\n" + "\n".join(failed_files))
    
    def refresh_local_files(self):
        """刷新本地文件列表"""
        current_path = self.local_path_input.text() or os.getcwd()
        self.load_local_files(current_path)
    
    def load_local_files(self, path):
        """加载本地文件列表"""
        try:
            # 使用PathUtils进行路径标准化和验证
            path = PathUtils.normalize_path(path)
            
            # 验证路径有效性（只检查基本格式，不强制检查存在性）
            is_valid, error_msg = PathUtils.is_valid_path(path, check_exists=False, check_is_dir=False)
            if not is_valid:
                # 如果路径格式有问题，回退到当前目录
                valid_path = os.getcwd()
                path = valid_path
                self.local_path_input.setText(valid_path)
                
            # 检查路径是否存在
            if not os.path.exists(path):
                raise FileNotFoundError(f"路径不存在: {path}")
            
            self.local_files_table.setRowCount(0)
            self.local_path_input.setText(path)
            
            # 添加文件和目录
            try:
                items = os.listdir(path)
            except OSError as e:
                if e.errno == 22:  # Invalid argument
                    # 可能是根目录访问问题，尝试修复
                    if not path.endswith("\\"):
                        fixed_path = path + "\\"
                        if os.path.exists(fixed_path) and os.path.isdir(fixed_path):
                            items = os.listdir(fixed_path)
                            path = fixed_path
                            self.local_path_input.setText(path)
                        else:
                            raise e
                    else:
                        raise e
                else:
                    raise e
            for item in items:
                item_path = os.path.join(path, item)
                
                try:
                    if os.path.isdir(item_path):
                        item_type = "目录"
                        size = ""
                        permissions = self.get_file_permissions(item_path)
                    else:
                        item_type = "文件"
                        # 特殊处理C盘根目录下的特殊文件
                        try:
                            file_size = os.path.getsize(item_path)
                            size = self.format_file_size(file_size)
                        except OSError as e:
                            if e.errno == 22:  # Invalid argument
                                size = "未知"
                            else:
                                raise e
                        
                        permissions = self.get_file_permissions(item_path)
                    
                    # 处理修改时间
                    try:
                        mod_time = datetime.fromtimestamp(os.path.getmtime(item_path)).strftime('%Y-%m-%d %H:%M:%S')
                    except OSError as e:
                        if e.errno == 22:  # Invalid argument
                            mod_time = "未知"
                        else:
                            raise e
                    
                    row = self.local_files_table.rowCount()
                    self.local_files_table.insertRow(row)
                    self.local_files_table.setItem(row, 0, QTableWidgetItem(item))
                    self.local_files_table.setItem(row, 1, QTableWidgetItem(item_type))
                    self.local_files_table.setItem(row, 2, QTableWidgetItem(mod_time))
                    self.local_files_table.setItem(row, 3, QTableWidgetItem(size))
                    self.local_files_table.setItem(row, 4, QTableWidgetItem(permissions))
                    
                except OSError as e:
                    if e.errno == 22:  # Invalid argument
                        # 添加基本信息，但跳过无法访问的详细属性
                        row = self.local_files_table.rowCount()
                        self.local_files_table.insertRow(row)
                        self.local_files_table.setItem(row, 0, QTableWidgetItem(item))
                        self.local_files_table.setItem(row, 1, QTableWidgetItem("特殊文件"))
                        self.local_files_table.setItem(row, 2, QTableWidgetItem("未知"))
                        self.local_files_table.setItem(row, 3, QTableWidgetItem("未知"))
                        self.local_files_table.setItem(row, 4, QTableWidgetItem("---"))
                    else:
                        raise e
        
        except PermissionError as e:
            QMessageBox.warning(self, "权限错误", f"无法访问目录 {path}: {str(e)}")
        except (FileNotFoundError, NotADirectoryError, ValueError) as e:
            QMessageBox.warning(self, "路径错误", str(e))
            # 恢复到有效路径
            valid_path = os.getcwd()
            self.local_path_input.setText(valid_path)
            self.load_local_files(valid_path)
        except OSError as e:
            if e.errno == 22:  # Invalid argument
                QMessageBox.warning(self, "路径错误", f"无效的路径参数: {path}\n请检查路径是否包含特殊字符或格式不正确")
                # 恢复到有效路径
                valid_path = os.getcwd()
                self.local_path_input.setText(valid_path)
                self.load_local_files(valid_path)
            else:
                QMessageBox.warning(self, "系统错误", f"加载文件列表失败: {str(e)}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载文件列表失败: {str(e)}")
    
    def refresh_remote_files(self, remote_path=None):
        """刷新远程文件列表"""
        print(f"[界面刷新] 开始刷新远程文件列表，当前设备: {self.current_device}")
        
        if not self.current_device:
            print("[界面刷新] 错误：没有当前设备")
            QMessageBox.warning(self, "警告", "请先连接设备")
            return
        
        if remote_path is None:
            remote_path = self.remote_path_input.text() or "/"
        
        print(f"[界面刷新] 刷新路径: {remote_path}")
        
        try:
            # 从传输引擎获取当前连接设备的配置
            conn_config = self.transfer_engine.get_device_config(self.current_device)
            if not conn_config:
                QMessageBox.warning(self, "警告", "无法获取设备连接配置，请重新连接")
                return
            
            # 确保配置中有host字段
            if not conn_config.get('host'):
                conn_config['host'] = conn_config.get('ip', '')
            
            # 使用传输引擎获取远程文件列表
            file_list = self.transfer_engine.list_remote_files(remote_path, conn_config)
            
            # 调试：检查文件列表中的所有文件
            print(f"[DEBUG] 刷新远程文件列表，路径: {remote_path}")
            print(f"[DEBUG] 文件列表长度: {len(file_list)}")
            
            # 打印所有文件信息，特别是大文件
            for file_info in file_list:
                if file_info.get('name') == 'kali-linux-2025.1a-installer-amd64.iso':
                    print(f"[DEBUG] *** 目标大文件信息: {file_info} ***")
                elif file_info.get('size') and 'GB' in file_info.get('size', ''):
                    print(f"[DEBUG] 大文件: {file_info}")
                else:
                    print(f"[DEBUG] 文件: {file_info.get('name')}, 大小: {file_info.get('size')}")
            
            print(f"[界面刷新] 获取到 {len(file_list)} 个文件，开始加载到界面")
            self.load_remote_files(file_list, remote_path)
            print(f"[界面刷新] 界面刷新完成")
            
        except Exception as e:
            print(f"[界面刷新] 错误: {str(e)}")
            QMessageBox.warning(self, "错误", f"刷新远程文件列表失败: {str(e)}")
    
    def load_remote_files(self, file_list, remote_path):
        """加载远程文件列表"""
        print(f"[界面加载] 开始加载 {len(file_list)} 个文件到远程文件列表")
        
        # 加载数据前禁用排序，避免性能问题
        self.remote_files_table.setSortingEnabled(False)
        
        self.remote_files_table.setRowCount(0)
        self.remote_path_input.setText(remote_path)
        
        # 真正的系统保护文件列表 - 不在远程列表中显示和删除
        # 这些是应用程序运行必需的文件，用户不应该删除
        system_files = [
            '.gitignore', '*.pyc', '__pycache__'
        ]
        # 注意：device_configs.json, list_remote_files.py, main_app.py等是用户可能上传的合法文件
        # 不应该被过滤，用户有权删除自己上传的文件
        
        for file_info in file_list:
            name = file_info.get('name', '')
            
            # 跳过系统配置文件
            skip_file = False
            for sys_file in system_files:
                if sys_file.startswith('*'):
                    # 通配符匹配
                    import fnmatch
                    if fnmatch.fnmatch(name.lower(), sys_file.lower()):
                        skip_file = True
                        break
                elif name.lower() == sys_file.lower():
                    skip_file = True
                    break
            
            if skip_file:
                continue  # 跳过系统文件，不显示在列表中
            
            row = self.remote_files_table.rowCount()
            self.remote_files_table.insertRow(row)
            
            file_type = file_info.get('type', '')
            mod_time = file_info.get('mod_time', '')
            size = file_info.get('size', '')
            permissions = file_info.get('permissions', '')
            
            # 调试：检查UI显示的大小与文件信息中的大小是否一致
            print(f"[UI加载] 文件名: {name}, 文件信息中的大小: {size}")
            
            self.remote_files_table.setItem(row, 0, QTableWidgetItem(name))
            self.remote_files_table.setItem(row, 1, QTableWidgetItem(file_type if file_type else "未知"))
            self.remote_files_table.setItem(row, 2, QTableWidgetItem(mod_time))
            self.remote_files_table.setItem(row, 3, QTableWidgetItem(size))
            self.remote_files_table.setItem(row, 4, QTableWidgetItem(permissions))
        
        # 数据加载完成后重新启用排序
        self.remote_files_table.setSortingEnabled(True)
        print(f"[界面加载] 文件列表加载完成，共 {self.remote_files_table.rowCount()} 行")
    
    def local_file_double_click(self, index):
        """本地文件双击事件"""
        row = index.row()
        item_name = self.local_files_table.item(row, 0).text()
        current_path = self.local_path_input.text() or os.getcwd()
        
        item_path = os.path.join(current_path, item_name)
        if os.path.isdir(item_path):
            # 进入子目录
            self.load_local_files(item_path)
    
    def remote_file_double_click(self, index):
        """远程文件双击事件"""
        print(f"[DEBUG] 双击事件触发，当前设备: {self.current_device}")
        
        # 如果没有当前设备，检查是否有连接的设备
        if not self.current_device:
            print("[DEBUG] 没有当前设备，检查是否有连接的设备...")
            # 检查传输引擎中是否有连接的设备
            if self.transfer_engine.connected_devices:
                connected_device = list(self.transfer_engine.connected_devices.keys())[0]
                print(f"[DEBUG] 传输引擎中有连接的设备: {connected_device}")
                self.current_device = connected_device
                print(f"[DEBUG] 已更新当前设备为: {self.current_device}")
            else:
                print("[DEBUG] 没有当前设备，返回")
                QMessageBox.warning(self, "警告", "请先连接设备")
                return
        
        row = index.row()
        print(f"[DEBUG] 双击行号: {row}")
        
        item = self.remote_files_table.item(row, 0)
        item_type_item = self.remote_files_table.item(row, 1)
        item_time_item = self.remote_files_table.item(row, 2)
        permissions_item = self.remote_files_table.item(row, 4)
        
        print(f"[DEBUG] item (名称列): {item}")
        print(f"[DEBUG] item_type_item (类型列): {item_type_item}")
        print(f"[DEBUG] item_time_item (时间列): {item_time_item}")
        print(f"[DEBUG] permissions_item (权限列): {permissions_item}")
        
        if item is None:
            print("[DEBUG] 名称为空，返回")
            return
        
        item_name = item.text()
        item_type = item_type_item.text() if item_type_item else ""
        item_time = item_time_item.text() if item_time_item else ""
        permissions = permissions_item.text() if permissions_item else ""
        current_path = self.remote_path_input.text() or "/"
        
        print(f"[DEBUG] 名称: '{item_name}', 类型: '{item_type}', 时间: '{item_time}', 权限: '{permissions}'")
        print(f"[DEBUG] 当前路径: {current_path}")
        
        # 判断是否为目录：如果文件类型为"目录"，或者权限字符串以'd'开头（表示目录）
        is_directory = item_type == "目录" or (permissions and permissions.startswith("d"))
        print(f"[DEBUG] 是否为目录: {is_directory}")
        
        if is_directory:
            # 进入子目录
            new_path = os.path.join(current_path, item_name).replace('\\', '/')
            print(f"[DEBUG] 准备进入目录: {new_path}")
            # 使用新路径刷新文件列表
            self.refresh_remote_files(new_path)
            print(f"[DEBUG] 刷新完成")
        else:
            print("[DEBUG] 不是目录，不执行跳转")
    
    def go_to_parent_directory(self):
        """返回上一层目录"""
        if not self.current_device:
            return
        
        current_path = self.remote_path_input.text() or "/"
        
        # 如果是根目录，则不执行任何操作
        if current_path == "/":
            return
        
        # 计算父目录路径
        parent_path = os.path.dirname(current_path)
        
        # 确保路径以斜杠开头
        if not parent_path.startswith("/"):
            parent_path = "/" + parent_path
        
        # 如果父目录为空，设置为根目录
        if parent_path == "":
            parent_path = "/"
        
        # 标准化路径（移除多余的斜杠和点）
        parent_path = os.path.normpath(parent_path).replace("\\", "/")
        if not parent_path.startswith("/"):
            parent_path = "/" + parent_path
        
        # 刷新父目录的文件列表
        self.refresh_remote_files(parent_path)
    
    # 传输控制相关方法
    def start_progress_monitor(self):
        """启动进度监控线程"""
        self.progress_thread = TransferProgressThread(self.transfer_engine)
        self.progress_thread.progress_update.connect(self.update_progress_display)
        self.progress_thread.start()
    
    def update_progress_display(self, progress_info):
        """更新多设备进度显示"""
        # 获取所有设备的传输状态
        device_progress = self.transfer_engine.get_all_device_progress()
        
        # 更新设备传输进度表格
        self.update_device_progress_table(device_progress)
        
        # 进度信息处理
        pass
    
    def update_device_progress_table(self, device_progress):
        """更新设备传输进度表格"""
        # 保存进度数据供其他方法使用
        self._device_progress = device_progress
        
        # 清空表格
        self.device_progress_table.setRowCount(0)
        
        # 为每个有传输任务的设备添加行
        for device_id, progress_data in device_progress.items():
            row = self.device_progress_table.rowCount()
            self.device_progress_table.insertRow(row)
            
            # 设备名称
            device_name = self.device_configs.get(device_id, {}).get('name', device_id)
            self.device_progress_table.setItem(row, 0, QTableWidgetItem(device_name))
            
            # 传输状态
            status_text = ""
            status_color = Qt.GlobalColor.black
            
            if progress_data.get('status') == 'transferring':
                status_text = "传输中"
                status_color = Qt.GlobalColor.blue
            elif progress_data.get('status') == 'paused':
                status_text = "已暂停"
                status_color = Qt.GlobalColor.yellow
            elif progress_data.get('status') == 'completed':
                status_text = "已完成"
                status_color = Qt.GlobalColor.green
            elif progress_data.get('status') == 'error':
                status_text = "错误"
                status_color = Qt.GlobalColor.red
            else:
                status_text = "空闲"
            
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(status_color)
            self.device_progress_table.setItem(row, 1, status_item)
            
            # 当前文件
            current_file = progress_data.get('current_file', '')
            file_name = os.path.basename(current_file) if current_file else "无"
            self.device_progress_table.setItem(row, 2, QTableWidgetItem(file_name))
            
            # 进度
            progress_percent = progress_data.get('progress', 0)
            progress_item = QTableWidgetItem(f"{progress_percent:.1f}%")
            self.device_progress_table.setItem(row, 3, progress_item)
            
            # 速度
            speed = progress_data.get('speed', 0)
            speed_item = QTableWidgetItem(self.format_speed(speed))
            self.device_progress_table.setItem(row, 4, speed_item)
            
            # MD5校验状态
            md5_status = ""
            md5_color = Qt.GlobalColor.black
            
            if progress_data.get('md5_status') == "校验中":
                md5_status = "校验中"
                md5_color = Qt.GlobalColor.blue
            elif progress_data.get('md5_status') == "校验成功":
                md5_status = "校验成功"
                md5_color = Qt.GlobalColor.green
            elif progress_data.get('md5_status') == "校验失败":
                md5_status = "校验失败"
                md5_color = Qt.GlobalColor.red
            elif progress_data.get('md5_status') == "无法校验":
                md5_status = "无法校验"
                md5_color = Qt.GlobalColor.gray
            else:
                md5_status = ""
            
            md5_item = QTableWidgetItem(md5_status)
            md5_item.setForeground(md5_color)
            self.device_progress_table.setItem(row, 5, md5_item)
            
            # MD5计算时间 - 显示计算状态：计算中/已完成
            md5_status = progress_data.get('md5_status', '')
            if md5_status == "校验成功" or md5_status == "校验失败" or md5_status == "已完成":
                md5_time_text = "已完成"
            else:
                md5_time_text = "计算中"
            md5_time_item = QTableWidgetItem(md5_time_text)
            self.device_progress_table.setItem(row, 6, md5_time_item)
            
            # 剩余时间 - 大于60秒时按分钟显示，传输完成或进度100%时显示"已完成"
            remaining_time = progress_data.get('remaining_time', 0)
            status = progress_data.get('status', '')
            progress = progress_data.get('progress', 0)
            if status == 'completed' or progress == 100.0:
                remaining_time_text = "已完成"
            elif remaining_time > 0:
                if remaining_time >= 60:
                    remaining_minutes = int(remaining_time / 60)
                    remaining_seconds = int(remaining_time % 60)
                    remaining_time_text = f"{remaining_minutes}m{remaining_seconds}s"
                else:
                    remaining_time_text = f"{int(remaining_time)}s"
            else:
                remaining_time_text = ""
            remaining_time_item = QTableWidgetItem(remaining_time_text)
            self.device_progress_table.setItem(row, 7, remaining_time_item)
            
            # 本地MD5
            local_md5 = progress_data.get('local_md5', '')
            # 如果是文件夹传输完成，显示文件夹整体MD5
            folder_local_md5 = progress_data.get('folder_local_md5', '')
            if folder_local_md5 and progress_data.get('file_count', 0) > 1:
                display_local_md5 = folder_local_md5  # 直接显示完整MD5
            else:
                display_local_md5 = local_md5
            local_md5_item = QTableWidgetItem(display_local_md5)
            self.device_progress_table.setItem(row, 8, local_md5_item)
            
            # 远程MD5
            remote_md5 = progress_data.get('remote_md5', '')
            folder_remote_md5 = progress_data.get('folder_remote_md5', '')
            if folder_remote_md5 and progress_data.get('file_count', 0) > 1:
                display_remote_md5 = folder_remote_md5  # 直接显示完整MD5
            else:
                display_remote_md5 = remote_md5
            remote_md5_item = QTableWidgetItem(display_remote_md5)
            self.device_progress_table.setItem(row, 9, remote_md5_item)
            
            # 已完成文件数量
            completed_files = progress_data.get('completed_files', 0)
            file_count = progress_data.get('file_count', 0)
            if file_count > 0:
                files_text = f"{completed_files}/{file_count}"
            else:
                files_text = ""
            files_item = QTableWidgetItem(files_text)
            self.device_progress_table.setItem(row, 10, files_item)
            
            # MD5历史 - 显示简要信息
            md5_history = progress_data.get('md5_history', [])
            if md5_history:
                # 统计成功和失败数量
                success_count = sum(1 for r in md5_history if r.get('status') == '校验成功')
                fail_count = sum(1 for r in md5_history if r.get('status') == '校验失败')
                history_text = f"成功:{success_count}"
                if fail_count > 0:
                    history_text += f" 失败:{fail_count}"
                # 显示最近文件的校验结果
                if md5_history:
                    recent = md5_history[-1]
                    filename = recent.get('filename', '')[:10]
                    history_text += f" (最新:{filename}...)"
            else:
                history_text = ""
            history_item = QTableWidgetItem(history_text)
            self.device_progress_table.setItem(row, 11, history_item)
    
    def show_md5_history_detail(self, row, column):
        """显示MD5历史详细信息（双击MD5历史列时触发）"""
        # 只有点击MD5历史列（第11列）才显示详情
        if column != 11:
            return
        
        # 获取设备ID
        if not hasattr(self, '_device_progress') or row >= len(self._device_progress):
            return
        
        device_id = list(self._device_progress.keys())[row]
        progress_data = self._device_progress.get(device_id, {})
        
        md5_history = progress_data.get('md5_history', [])
        folder_local_md5 = progress_data.get('folder_local_md5', '')
        folder_remote_md5 = progress_data.get('folder_remote_md5', '')
        local_md5 = progress_data.get('local_md5', '')
        remote_md5 = progress_data.get('remote_md5', '')
        md5_status = progress_data.get('md5_status', '')
        file_count = progress_data.get('file_count', 0)
        current_file = progress_data.get('current_file', '')
        
        # 如果没有任何MD5信息，直接返回
        if not md5_history and not folder_local_md5 and not local_md5:
            return
        
        # 构建详细文本
        detail_lines = []
        detail_lines.append("=" * 60)
        detail_lines.append("文件MD5校验详情")
        detail_lines.append("=" * 60)
        
        # 文件夹传输：显示历史记录
        if md5_history:
            detail_lines.append(f"\n共 {len(md5_history)} 个文件:\n")
            for i, record in enumerate(md5_history, 1):
                detail_lines.append(f"{i}. {record.get('filename', '未知文件')}")
                detail_lines.append(f"   本地MD5: {record.get('local_md5', '')}")
                detail_lines.append(f"   远程MD5: {record.get('remote_md5', '')}")
                detail_lines.append(f"   校验结果: {record.get('status', '')}")
                detail_lines.append("")
            
            # 添加文件夹整体MD5
            if folder_local_md5:
                detail_lines.append("-" * 60)
                detail_lines.append("文件夹整体MD5（所有文件MD5合并计算）:")
                detail_lines.append(f"  本地: {folder_local_md5}")
                detail_lines.append(f"  远程: {folder_remote_md5}")
        else:
            # 单文件传输：显示单个文件信息
            detail_lines.append(f"\n当前文件: {current_file}")
            detail_lines.append(f"校验结果: {md5_status}")
            detail_lines.append(f"本地MD5: {local_md5}")
            detail_lines.append(f"远程MD5: {remote_md5}")
        
        # 使用QMessageBox显示
        from PyQt6.QtWidgets import QMessageBox
        detail_text = "\n".join(detail_lines)
        QMessageBox.information(self, "MD5校验详情", detail_text)
    
    # 注释掉日志方法，因为已删除日志区域
    # def log_progress(self, message):
    #     """记录进度日志"""
    #     timestamp = datetime.now().strftime('%H:%M:%S')
    #     self.progress_log.append(f"[{timestamp}] {message}")
    #     # 滚动到底部
    #     self.progress_log.verticalScrollBar().setValue(
    #         self.progress_log.verticalScrollBar().maximum()
    #     )
    
    def pause_transfer(self):
        """暂停传输"""
        self.transfer_engine.pause_all()
    
    def resume_transfer(self):
        """继续传输"""
        self.transfer_engine.resume_all()
    
    def cancel_transfer(self):
        """取消传输"""
        self.transfer_engine.cancel_all()
    

    
    # 工具方法
    def format_file_size(self, size_bytes):
        """格式化文件大小显示"""
        if size_bytes == 0:
            return "0 B"
        
        size = float(size_bytes)
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        
        # 计算应该使用哪个单位
        unit_index = 0
        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"
    
    def add_transfer_task_to_progress(self, task):
        """添加传输任务到进度表格"""
        row = self.device_progress_table.rowCount()
        self.device_progress_table.insertRow(row)
        
        # 设备名称
        device_name = self.current_device or "未知设备"
        self.device_progress_table.setItem(row, 0, QTableWidgetItem(device_name))
        
        # 状态
        status_item = QTableWidgetItem("等待中")
        status_item.setForeground(Qt.GlobalColor.blue)
        self.device_progress_table.setItem(row, 1, status_item)
        
        # 文件名
        file_name = os.path.basename(task.local_path) if hasattr(task, 'local_path') else "未知文件"
        self.device_progress_table.setItem(row, 2, QTableWidgetItem(file_name))
        
        # 进度
        progress_item = QTableWidgetItem("0.0%")
        self.device_progress_table.setItem(row, 3, progress_item)
        
        # 速度
        speed_item = QTableWidgetItem("0 B/s")
        self.device_progress_table.setItem(row, 4, speed_item)
    
    def format_speed(self, speed_bytes):
        """格式化速度显示"""
        if speed_bytes >= 1024 * 1024:
            return f"{speed_bytes / (1024 * 1024):.1f} MB/s"
        elif speed_bytes >= 1024:
            return f"{speed_bytes / 1024:.1f} KB/s"
        else:
            return f"{speed_bytes:.1f} B/s"
    
    def get_file_permissions(self, file_path):
        """获取文件权限字符串"""
        try:
            stat_info = os.stat(file_path)
            permissions = stat_info.st_mode
            
            # 转换为rwx格式
            perm_str = ''
            for who in "USR", "GRP", "OTH":
                for perm in "R", "W", "X":
                    if permissions & getattr(os, f"S_I{perm}{who}"):
                        perm_str += perm.lower()
                    else:
                        perm_str += '‐'
            
            return perm_str
        except:
            return "???"
    
    def delayed_load_device_list(self):
        """延迟加载设备列表（用于选项卡切换时的异步加载）"""
        QTimer.singleShot(100, self.refresh_devices)
    

    
    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.progress_thread:
            self.progress_thread.stop()
            self.progress_thread.wait()
        
        if self.transfer_engine:
            self.transfer_engine.shutdown()
        
        event.accept()

    def on_device_table_double_clicked(self, index):
        """双击设备列表行弹出修改连接参数对话框"""
        row = index.row()
        ip_item = self.device_table.item(row, 3)  # IP地址在第3列
        if not ip_item:
            return
        ip = ip_item.text().strip()
        # 根据IP查找设备配置
        device = None
        for config in self.device_configs.values():
            for proto_conf in config.get('protocol_configs', []):
                if proto_conf.get('ip', '').strip() == ip:
                    device = config
                    device['ip'] = ip  # 确保设备对象有当前IP
                    device['username'] = proto_conf.get('username', '')
                    device['password'] = proto_conf.get('password', '')
                    device['port'] = proto_conf.get('port', 22)
                    break
            if device:
                break
        
        if not device:
            return

        self.edit_connection_params(device)

    def edit_connection_params(self, device):
        """弹出对话框修改设备的IP、用户名、密码、端口 - 使用对齐布局"""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton, 
            QMessageBox, QHBoxLayout
        )

        dialog = QDialog(self)
        dialog.setWindowTitle(f"修改设备连接参数 - {device['name']}")
        dialog.resize(450, 300)
        layout = QVBoxLayout(dialog)

        # 使用表单布局实现标签和输入框对齐
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(15)

        # IP地址
        lbl_ip = QLabel("IP地址:")
        le_ip = QLineEdit(device.get('ip', ''))
        le_ip.setMinimumWidth(200)
        form_layout.addRow(lbl_ip, le_ip)

        # 用户名
        lbl_user = QLabel("用户名:")
        le_user = QLineEdit(device.get('username', ''))
        le_user.setMinimumWidth(200)
        form_layout.addRow(lbl_user, le_user)

        # 密码
        lbl_pass = QLabel("密码:")
        le_pass = QLineEdit(device.get('password', ''))
        le_pass.setEchoMode(QLineEdit.EchoMode.Password)
        le_pass.setMinimumWidth(200)
        form_layout.addRow(lbl_pass, le_pass)

        # 端口
        lbl_port = QLabel("端口:")
        le_port = QLineEdit(str(device.get('port', 22)))
        le_port.setMinimumWidth(200)
        form_layout.addRow(lbl_port, le_port)

        layout.addLayout(form_layout)

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_save = QPushButton("保存")
        btn_save.setFixedWidth(80)
        btn_cancel = QPushButton("取消")
        btn_cancel.setFixedWidth(80)
        
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        def save_and_close():
            new_ip = le_ip.text().strip()
            new_user = le_user.text().strip()
            new_pass = le_pass.text().strip()
            new_port_text = le_port.text().strip()
            
            if not new_ip:
                QMessageBox.warning(dialog, "错误", "IP地址不能为空")
                return
                
            try:
                new_port = int(new_port_text)
            except ValueError:
                QMessageBox.warning(dialog, "错误", "端口必须是数字")
                return

            # 这里可以添加保存配置的逻辑
            # 由于配置管理较复杂，目前只更新界面显示
            device['ip'] = new_ip
            device['username'] = new_user
            device['password'] = new_pass
            device['port'] = new_port
            
            # 刷新设备列表显示
            self.refresh_devices()
            QMessageBox.information(dialog, "成功", "设备参数已更新")
            dialog.accept()

        btn_save.clicked.connect(save_and_close)
        btn_cancel.clicked.connect(dialog.reject)

        dialog.exec()

    def go_to_parent_directory_local(self):
        """本地文件列表返回上一层目录"""
        current_path = self.local_path_input.text() or os.getcwd()
        
        # 如果是根目录，则不执行任何操作
        if current_path == os.path.abspath(os.sep):
            return
        
        # 计算父目录路径
        parent_path = os.path.dirname(current_path)
        
        # 如果父目录为空，设置为根目录
        if not parent_path:
            parent_path = os.path.abspath(os.sep)
        
        # 刷新父目录的文件列表
        self.load_local_files(parent_path)

    def on_local_path_enter(self):
        """本地路径输入框回车事件"""
        new_path = self.local_path_input.text().strip()
        
        # 如果输入为空，则保持当前路径
        if not new_path:
            return
        
        # 检查路径是否存在且是目录
        if os.path.exists(new_path) and os.path.isdir(new_path):
            self.load_local_files(new_path)
        else:
            QMessageBox.warning(self, "路径错误", f"路径不存在或不是目录: {new_path}")

    def on_remote_path_enter(self):
        """远程路径输入框回车事件"""
        if not self.current_device:
            QMessageBox.warning(self, "警告", "请先连接设备")
            return
        
        new_path = self.remote_path_input.text().strip()
        
        # 如果输入为空，则保持当前路径
        if not new_path:
            return
        
        # 确保路径以斜杠开头
        if not new_path.startswith("/"):
            new_path = "/" + new_path
        
        # 标准化路径
        new_path = os.path.normpath(new_path).replace("\\", "/")
        
        # 尝试刷新远程文件列表
        self.refresh_remote_files(new_path)
    
    def get_current_protocol(self):
        """获取当前设备选择的协议"""
        if not self.current_device:
            return None
        
        # 查找当前设备在表格中的行
        for row in range(self.device_table.rowCount()):
            device_name_item = self.device_table.item(row, 0)
            if device_name_item:
                config = self.device_configs.get(self.current_device, {})
                if device_name_item.text() == config.get('name', ''):
                    # 找到了对应的行，获取协议选择框
                    combo = self.protocol_combos.get((self.current_device, row))
                    if combo:
                        return combo.currentText()
        
        # 如果找不到，返回设备配置中的第一个协议
        config = self.device_configs.get(self.current_device, {})
        protocols = config.get('protocols', [])
        return protocols[0] if protocols else None
    
    def create_remote_folder_sftp(self, folder_path):
        """使用SFTP创建远程文件夹"""
        import paramiko
        
        if not self.current_device:
            return False
        
        # 获取设备配置
        config = self.device_configs.get(self.current_device, {})
        protocol_configs = config.get('protocol_configs', [])
        
        # 找到SFTP配置
        sftp_config = None
        for pc in protocol_configs:
            if pc.get('protocol', '').upper() == 'SFTP':
                sftp_config = pc
                break
        
        if not sftp_config:
            return False
        
        # 创建SSH连接
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            ssh.connect(
                hostname=sftp_config.get('ip', ''),
                port=int(sftp_config.get('port', 22)),
                username=sftp_config.get('username', ''),
                password=sftp_config.get('password', ''),
                timeout=30
            )
            
            sftp = ssh.open_sftp()
            
            # 创建文件夹
            sftp.mkdir(folder_path)
            
            sftp.close()
            ssh.close()
            
            return True
            
        except Exception as e:
            print(f"[ERROR] SFTP创建文件夹失败: {str(e)}")
            try:
                ssh.close()
            except:
                pass
            return False
    
    def create_remote_folder_ftp(self, folder_path):
        """使用FTP创建远程文件夹"""
        import ftplib
        
        if not self.current_device:
            return False
        
        # 获取设备配置
        config = self.device_configs.get(self.current_device, {})
        protocol_configs = config.get('protocol_configs', [])
        
        # 找到FTP配置
        ftp_config = None
        for pc in protocol_configs:
            if pc.get('protocol', '').upper() == 'FTP':
                ftp_config = pc
                break
        
        if not ftp_config:
            return False
        
        # 创建FTP连接
        ftp = ftplib.FTP()
        
        try:
            ftp.connect(
                ftp_config.get('ip', ''),
                int(ftp_config.get('port', 21)),
                timeout=30
            )
            ftp.login(
                ftp_config.get('username', ''),
                ftp_config.get('password', '')
            )
            
            # 创建文件夹
            ftp.mkd(folder_path)
            
            ftp.quit()
            
            return True
            
        except Exception as e:
            print(f"[ERROR] FTP创建文件夹失败: {str(e)}")
            try:
                ftp.quit()
            except:
                pass
            return False

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = EnhancedDataTransferPage()
    window.setWindowTitle("数据传输界面")
    window.resize(1600, 900)
    window.show()
    sys.exit(app.exec())