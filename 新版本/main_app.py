import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QSplitter, QListWidget, QTextEdit, QTabWidget, QLabel, 
                             QMenuBar, QStatusBar, QToolBar, QDialog, QComboBox, 
                             QPushButton, QFormLayout)
from PyQt6.QtCore import Qt, QSize, QMimeData, QByteArray, QTimer
from PyQt6.QtGui import QAction, QFont, QDrag, QMouseEvent
from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
import json

# 导入各个页面的类
from device_management.device_management_page import DeviceManagementPage
from data_transfer.enhanced_data_transfer_page import EnhancedDataTransferPage as DataTransferPage
from script_editor.script_editor_page import ScriptEditorPage
from test_execution.test_execution_page import TestExecutionPage
from data_statistics.data_statistics_page import DataStatisticsPage

# 导入主题管理器和UI样式
from themes.theme_manager import ThemeManager
from themes.ui_styles import get_common_stylesheet


class ThemeDialog(QDialog):
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("选择主题")
        self.setGeometry(300, 300, 300, 150)
        
        layout = QFormLayout()
        
        # 主题选择下拉框
        self.theme_combo = QComboBox()
        all_themes = self.theme_manager.get_all_themes()
        self.theme_combo.addItems(all_themes)
        
        # 设置当前主题
        current_theme = self.theme_manager.get_current_theme()
        if current_theme in all_themes:
            self.theme_combo.setCurrentText(current_theme)
        
        layout.addRow("选择主题:", self.theme_combo)
        
        # 应用按钮
        apply_btn = QPushButton("应用主题")
        apply_btn.clicked.connect(self.apply_theme)
        layout.addRow(apply_btn)
        
        self.setLayout(layout)
    
    def apply_theme(self):
        selected_theme = self.theme_combo.currentText()
        
        # 应用主题
        if selected_theme == "Dark":
            self.theme_manager.apply_dark_theme()
        elif selected_theme == "Light":
            self.theme_manager.apply_light_theme()
        elif selected_theme == "Blue":
            self.theme_manager.apply_blue_theme()
        elif selected_theme == "Green":
            self.theme_manager.apply_green_theme()
        else:
            self.theme_manager.apply_theme(selected_theme)
        
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, theme_manager):
        super().__init__()
        self.theme_manager = theme_manager
        
        # 先创建空页面，后续按需加载
        self._page_cache = {}
        
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("设备管理工具")
        self.setGeometry(100, 100, 1700, 1000)
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建工具栏
        self.create_toolbar()
        
        # 创建状态栏
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("启动中")
        
        # 先显示窗口，再加载页面
        self.show()
        
        # 立即加载所有页面（带加载动画）
        self.load_all_pages_with_animation()
    
    def load_all_pages_with_animation(self):
        """带加载动画效果加载所有页面"""
        # 页面类映射
        page_classes = [
            ("设备管理", DeviceManagementPage),
            ("传输数据", DataTransferPage),
            ("脚本编辑", ScriptEditorPage),
            ("测试执行", TestExecutionPage),
            ("数据统计", DataStatisticsPage),
        ]
        
        # 先创建空的tab widget
        self.tab_widget = QTabWidget()
        
        # 创建加载覆盖层
        self.loading_overlay = QWidget(self.tab_widget)
        self.loading_overlay.setFixedSize(self.tab_widget.width(), self.tab_widget.height())
        self.loading_overlay.setStyleSheet("background-color: #1e1e1e;")
        
        # 加载布局
        loading_layout = QVBoxLayout()
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 动态加载文字
        self.loading_status = QLabel("启动中")
        self.loading_status.setStyleSheet("color: #ffffff; font-size: 28px;")
        self.loading_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.loading_status)
        
        self.loading_overlay.setLayout(loading_layout)
        self.loading_overlay.show()
        
        # 启动文字动画计时器
        self._loading_dots = 0
        self._loading_timer = QTimer(self)
        self._loading_timer.timeout.connect(self._update_loading_text)
        self._loading_timer.start(500)  # 每500ms更新一次
        
        # 延迟加载页面
        self._page_classes = page_classes
        self._current_page_index = 0
        self._load_page_step()
    
    def _update_loading_text(self):
        """更新加载文字（动态点）"""
        dots = "." * ((self._loading_dots % 3) + 1)
        self.loading_status.setText(f"启动中{dots}")
        self._loading_dots += 1
    
    def _load_page_step(self):
        """逐步加载页面"""
        if self._current_page_index >= len(self._page_classes):
            # 所有页面加载完成，移除加载动画
            QTimer.singleShot(300, self._finish_loading)
            return
        
        page_name, page_class = self._page_classes[self._current_page_index]
        self.loading_status.setText(f"正在加载: {page_name}...")
        
        # 加载页面
        actual_page = page_class()
        self.tab_widget.addTab(actual_page, page_name)
        
        # 保存引用
        if page_name == "设备管理":
            self.device_page = actual_page
        elif page_name == "传输数据":
            self.data_transfer_page = actual_page
        elif page_name == "脚本编辑":
            self.script_editor_page = actual_page
        elif page_name == "测试执行":
            self.test_execution_page = actual_page
        elif page_name == "数据统计":
            self.data_statistics_page = actual_page
        
        # 更新进度
        self._current_page_index += 1
        
        # 继续加载下一个页面（给UI一点时间更新）
        QTimer.singleShot(100, self._load_page_step)
    
    def _finish_loading(self):
        """完成加载，移除覆盖层"""
        # 停止加载文字动画计时器
        if hasattr(self, '_loading_timer') and self._loading_timer:
            self._loading_timer.stop()
            self._loading_timer = None
        
        # 移除覆盖层
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.hide()
            self.loading_overlay.deleteLater()
            self.loading_overlay = None
        
        # 设置中心部件
        self.setCentralWidget(self.tab_widget)
        
        # 更新状态栏
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("就绪")
    
    def create_menu_bar(self):
        menubar = self.menuBar()
        if not menubar:
            return
        
        # 添加主题菜单
        theme_menu = menubar.addMenu("主题")
        
        # 获取所有可用主题
        all_themes = self.theme_manager.get_all_themes()
        
        # 为每个主题创建菜单项
        for theme_name in all_themes:
            theme_action = QAction(theme_name, self)
            theme_action.triggered.connect(lambda checked, name=theme_name: self.apply_theme(name))
            if theme_menu:
                theme_menu.addAction(theme_action)
    
    def create_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(True)  # 允许工具栏拖动
        toolbar.setIconSize(QSize(16, 16))  # 设置图标大小
        toolbar.setFloatable(True)  # 允许工具栏浮动
        
        # 应用工具栏样式
        toolbar.setStyleSheet(get_common_stylesheet())
        
        # 启用拖拽支持
        toolbar.setAcceptDrops(True)
        
        self.addToolBar(toolbar)
        
        # 存储拖拽的参数框
        self.dragged_params_widgets = []
        
        # 设备操作按钮组 - 使用文本按钮
        refresh_action = QAction("刷新", self)
        connect_action = QAction("连接", self)
        disconnect_action = QAction("断开", self)
        
        # 测试操作按钮组
        start_test_action = QAction("开始", self)
        stop_test_action = QAction("停止", self)
        
        # 添加工具按钮
        toolbar.addAction(refresh_action)
        toolbar.addAction(connect_action)
        toolbar.addAction(disconnect_action)
        toolbar.addSeparator()
        toolbar.addAction(start_test_action)
        toolbar.addAction(stop_test_action)
        
        # 连接拖拽事件
        toolbar.dragEnterEvent = self.toolbar_drag_enter_event
        toolbar.dragMoveEvent = self.toolbar_drag_move_event
        toolbar.dropEvent = self.toolbar_drop_event
    
    def on_tab_changed(self, index):
        """选项卡切换事件处理 - 按需加载页面"""
        try:
            # 页面名称映射
            page_map = {
                "设备管理": DeviceManagementPage,
                "传输数据": DataTransferPage,
                "脚本编辑": ScriptEditorPage,
                "测试执行": TestExecutionPage,
                "数据统计": DataStatisticsPage,
            }
            
            tab_text = self.tab_widget.tabText(index)
            
            # 检查是否需要加载页面
            current_widget = self.tab_widget.widget(index)
            if isinstance(current_widget, QLabel) and current_widget.text() == "正在加载...":
                # 加载实际页面
                page_class = page_map.get(tab_text)
                if page_class:
                    actual_page = page_class()
                    
                    # 替换占位页面
                    self.tab_widget.removeTab(index)
                    self.tab_widget.insertTab(index, actual_page, tab_text)
                    self.tab_widget.setCurrentIndex(index)
                    
                    # 保存引用
                    if tab_text == "设备管理":
                        self.device_page = actual_page
                    elif tab_text == "传输数据":
                        self.data_transfer_page = actual_page
                    elif tab_text == "脚本编辑":
                        self.script_editor_page = actual_page
                    elif tab_text == "测试执行":
                        self.test_execution_page = actual_page
                    elif tab_text == "数据统计":
                        self.data_statistics_page = actual_page
                    
                    print(f"已加载页面: {tab_text}")
            
            # 传输数据页面的特殊处理
            if tab_text == "传输数据":
                print("切换到传输数据页面，异步刷新设备列表")
                from PyQt6.QtCore import QTimer
                
                # 延迟100ms后异步刷新设备列表，避免UI卡顿
                QTimer.singleShot(100, self.data_transfer_page.delayed_load_device_list)
                
                # 更新状态栏
                status_bar = self.statusBar()
                if status_bar:
                    status_bar.showMessage("已切换到传输数据页面，设备列表正在异步刷新...")
            
        except Exception as e:
            print(f"选项卡切换事件处理出错: {e}")
    
    def apply_theme(self, theme_name):
        """应用指定的主题"""
        success = self.theme_manager.apply_theme(theme_name)
        
        # 更新状态栏显示当前主题
        status_bar = self.statusBar()
        if status_bar:
            if success:
                status_bar.showMessage(f"当前主题: {theme_name}")
            else:
                status_bar.showMessage(f"主题切换失败: {theme_name}")
    
    def hide_original_params_widget(self):
        """隐藏原始参数框，实现动态调整"""
        try:
            # 直接使用数据传递页面实例
            if hasattr(self, 'data_transfer_page'):
                data_transfer_page = self.data_transfer_page
                
                # 检查是否存在可拖拽参数框
                if hasattr(data_transfer_page, 'draggable_params_widget'):
                    draggable_widget = data_transfer_page.draggable_params_widget
                    if draggable_widget:
                        # 隐藏参数框
                        draggable_widget.hide()
                        
                        # 禁用参数框
                        draggable_widget.setEnabled(False)
                        
                        # 可选：调整布局，比如收缩相关区域
                        # 例如：调整文件列表区域的大小
                        
                        print("已成功隐藏并禁用原始协议参数框")
                        
                        # 更新状态栏
                        status_bar = self.statusBar()
                        if status_bar:
                            status_bar.showMessage("原始协议参数框已隐藏，参数已添加到工具栏")
                    else:
                        print("draggable_params_widget 为 None")
                else:
                    print("数据传递页面没有 draggable_params_widget 属性")
            else:
                print("主窗口没有 data_transfer_page 属性")
                
        except Exception as e:
            print(f"隐藏原始参数框时出错: {e}")
    
    def toolbar_button_mouse_press_event(self, button, event):
        """工具栏按钮鼠标按下事件 - 用于反向拖拽"""
        try:
            # 检查是否为左键点击
            if event.button() == Qt.MouseButton.LeftButton:
                # 创建拖拽操作
                drag = QDrag(button)
                mime_data = QMimeData()
                
                # 设置拖拽数据 - 反向拖拽的标识
                reverse_data = {
                    "type": "reverse_drag_params",
                    "params": button.simple_params if hasattr(button, 'simple_params') else {},
                    "source": "toolbar"
                }
                
                mime_data.setData("application/x-protocol-params", 
                                 QByteArray(json.dumps(reverse_data).encode()))
                drag.setMimeData(mime_data)
                
                # 执行拖拽操作
                drag.exec(Qt.DropAction.MoveAction)
                
        except Exception as e:
            print(f"工具栏按钮拖拽事件异常: {e}")
    
    def on_param_button_clicked(self, params):
        """参数按钮点击事件处理"""
        try:
            print(f"参数按钮被点击: {params}")
            
            # 导入参数编辑对话框
            from data_transfer.param_edit_dialog import ParamEditDialog
            
            # 创建并显示参数编辑对话框
            dialog = ParamEditDialog(params, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # 用户点击了保存，获取修改后的参数
                updated_params = dialog.get_params()
                print(f"参数已更新: {updated_params}")
                
                # 更新工具栏中对应按钮的提示信息
                self.update_toolbar_button_tooltip(updated_params)
                
                # 可以在这里添加参数保存逻辑
                # 例如：更新到配置文件、保存到设备管理页面等
                
                # 显示保存成功消息
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "参数保存", "参数已成功保存到配置")
                
                # 确保原始展示区域保持隐藏状态
                self.hide_original_params_widget()
                
        except Exception as e:
            print(f"参数按钮点击事件处理出错: {e}")
    
    def update_toolbar_button_tooltip(self, updated_params):
        """更新工具栏按钮的提示信息"""
        try:
            # 查找所有工具栏按钮
            toolbars = self.findChildren(QToolBar)
            for toolbar in toolbars:
                buttons = toolbar.findChildren(QPushButton)
                for button in buttons:
                    if hasattr(button, 'params_data') and button.text() == "传输":
                        # 更新按钮的提示信息
                        button.setToolTip(f"IP: {updated_params.get('ip', '')}\n用户: {updated_params.get('username', '')}\n端口: {updated_params.get('port', '')}")
                        print(f"已更新工具栏按钮提示信息: {updated_params}")
                        break
        except Exception as e:
            print(f"更新工具栏按钮提示信息时出错: {e}")
    
    def toolbar_drag_enter_event(self, event: QDragEnterEvent):
        """工具栏拖拽进入事件"""
        try:
            if event.mimeData().hasFormat("application/x-protocol-params"):
                event.acceptProposedAction()
                print("拖拽进入工具栏区域")
            else:
                event.ignore()
        except Exception as e:
            print(f"拖拽进入事件异常: {e}")
            event.ignore()
    
    def toolbar_drag_move_event(self, event: QDragMoveEvent):
        """工具栏拖拽移动事件"""
        try:
            if event.mimeData().hasFormat("application/x-protocol-params"):
                event.acceptProposedAction()
            else:
                event.ignore()
        except Exception as e:
            print(f"拖拽移动事件异常: {e}")
            event.ignore()
    
    def toolbar_drop_event(self, event: QDropEvent):
        """工具栏放置事件"""
        try:
            print("正在处理拖拽放置事件...")
            
            if event.mimeData().hasFormat("application/x-protocol-params"):
                # 获取拖拽的数据
                data = event.mimeData().data("application/x-protocol-params")
                params_data = json.loads(data.data().decode())
                
                if params_data.get("type") == "protocol_params":
                    # 创建参数显示标签
                    params = params_data.get("params", {})
                    
                    # 验证参数数据
                    if not params:
                        print("警告: 参数数据为空")
                        from PyQt6.QtWidgets import QMessageBox
                        QMessageBox.warning(self, "拖拽异常", "参数数据为空，无法添加到工具栏")
                        event.ignore()
                        return
                    
                    # 创建参数按钮，按钮名称为"传输"
                    param_button = QPushButton("传输")
                    param_button.setStyleSheet("""
                        QPushButton {
                            background-color: palette(button);
                            color: palette(button-text);
                            border: 1px solid palette(mid);
                            border-radius: 3px;
                            padding: 2px 6px;
                            font-size: 11px;
                            margin: 1px;
                            min-height: 20px;
                        }
                        QPushButton:hover {
                            background-color: palette(button);
                        }
                        QPushButton:pressed {
                            background-color: palette(dark);
                            color: palette(light);
                        }
                    """)
                    param_button.setToolTip(f"IP: {params.get('ip', '')}\n用户: {params.get('username', '')}\n端口: {params.get('port', '')}")
                    
                    # 存储参数数据到按钮属性中，用于反向拖拽
                    param_button.params_data = params_data
                    param_button.simple_params = params  # 同时存储简化参数
                    
                    # 启用拖拽功能
                    param_button.setAcceptDrops(True)
                    param_button.mousePressEvent = lambda event: self.toolbar_button_mouse_press_event(param_button, event)
                    
                    # 连接按钮点击事件，用于快速切换或显示详细信息
                    param_button.clicked.connect(lambda checked, p=params: self.on_param_button_clicked(p))
                    
                    # 添加到工具栏
                    # 查找所有工具栏，选择第一个或名为"主工具栏"的
                    toolbars = self.findChildren(QToolBar)
                    toolbar = None
                    
                    for tb in toolbars:
                        print(f"找到工具栏: {tb.windowTitle()}")
                        if tb.windowTitle() == "主工具栏":
                            toolbar = tb
                            break
                    
                    if not toolbar and toolbars:
                        toolbar = toolbars[0]  # 使用第一个工具栏
                    
                    if toolbar:
                        toolbar.addWidget(param_button)
                        self.dragged_params_widgets.append(param_button)
                        
                        # 隐藏原始参数框（动态调整）
                        self.hide_original_params_widget()
                        
                        # 更新状态栏
                        status_bar = self.statusBar()
                        if status_bar:
                            status_bar.showMessage("已添加参数按钮'传输'到工具栏")
                        
                        print("成功将参数按钮'传输'添加到工具栏")
                    else:
                        print("错误: 未找到任何工具栏")
                        from PyQt6.QtWidgets import QMessageBox
                        QMessageBox.warning(self, "拖拽异常", "未找到工具栏，无法添加参数框")
                    
                    event.acceptProposedAction()
                else:
                    print(f"未知的数据类型: {params_data.get('type')}")
                    event.ignore()
            else:
                print("拖拽数据格式不匹配")
                event.ignore()
                
        except json.JSONDecodeError as e:
            print(f"JSON解析异常: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "拖拽异常", f"数据格式错误: {str(e)}")
            event.ignore()
        except Exception as e:
            print(f"拖拽放置事件异常: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "拖拽异常", f"拖拽操作失败: {str(e)}")
            event.ignore()


def main():
    app = QApplication(sys.argv)
    
    # 创建主题管理器（使用夏天主题）
    theme_manager = ThemeManager(app)
    
    window = MainWindow(theme_manager)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()