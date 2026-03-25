"""
夏天主题UI样式
清新、简洁、夏日风情
"""

# ==================== 夏天色调定义 ====================
# 主色调 - 清新夏日蓝
SUMMER_SKY_BLUE = "#87CEEB"       # 天空蓝
SUMMER_CLOUD_WHITE = "#F5F9FC"    # 云白/淡蓝白
SUMMER_SUN_YELLOW = "#FFD700"     # 阳光金黄
SUMMER_GRASS_GREEN = "#90EE90"    # 草地绿
SUMMER_SEA_BLUE = "#40E0D0"       # 海蓝绿

# 辅助色
SUMMER_PRIMARY = "#5BA3C6"         # 主蓝
SUMMER_SECONDARY = "#7EC8E3"      # 次蓝
SUMMER_WARM_ORANGE = "#FFA726"    # 暖橙
SUMMER_HOT_PINK = "#FF6B9D"      # 夏日粉

# 中性色
SUMMER_BG = "#F0F7FA"             # 背景淡蓝
SUMMER_PANEL = "#FFFFFF"          # 面板白
SUMMER_CARD = "#FAFCFD"           # 卡片白
SUMMER_TEXT = "#2C3E50"           # 文字深蓝灰
SUMMER_TEXT_DIM = "#7F8C8D"       # 文字灰
SUMMER_BORDER = "#E0E8ED"         # 边框浅灰

# 功能色
SUMMER_SUCCESS = "#27AE60"        # 成功绿
SUMMER_WARNING = "#F39C12"        # 警告橙
SUMMER_ERROR = "#E74C3C"          # 错误红
SUMMER_INFO = "#3498DB"           # 信息蓝

# 终端色
SUMMER_TERMINAL_BG = "#1E3A4C"    # 终端深蓝
SUMMER_TERMINAL_TEXT = "#A8E6CF"  # 终端翠绿

# 字体
FONT_FAMILY = '"Microsoft YaHei", "Segoe UI", sans-serif'
FONT_MONO = "'Consolas', 'Courier New', monospace"

# ==================== 样式函数 ====================

def get_summer_stylesheet():
    """获取夏天主题完整样式表"""
    return """
QWidget {
    font-family: Microsoft YaHei, Segoe UI, sans-serif;
    font-size: 13px;
    color: #2C3E50;
}

/* 主窗口背景 */
QMainWindow, QDialog {
    background-color: #F0F7FA;
}

/* 标签 */
QLabel {
    color: #2C3E50;
    background: transparent;
}

/* 下拉框 */
QComboBox {
    background-color: #FFFFFF;
    color: #2C3E50;
    border: 1px solid #E0E8ED;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
    font-size: 12px;
}
QComboBox:hover {
    border-color: #5BA3C6;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid #7F8C8D;
}
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #E0E8ED;
    selection-background-color: #87CEEB;
}

/* 输入框 */
QLineEdit {
    background-color: #FFFFFF;
    color: #2C3E50;
    border: 1px solid #E0E8ED;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
QLineEdit:focus {
    border-color: #5BA3C6;
}
QLineEdit::placeholder {
    color: #7F8C8D;
}

/* 文本编辑 */
QTextEdit, QPlainTextEdit {
    background-color: #FFFFFF;
    color: #2C3E50;
    border: 1px solid #E0E8ED;
    border-radius: 4px;
    padding: 6px;
    font-family: Consolas, Courier New, monospace;
    font-size: 11px;
}

/* 按钮 - 主样式 */
QPushButton {
    background-color: #5BA3C6;
    color: white;
    border: none;
    border-radius: 3px;
    padding: 2px 10px;
    min-height: 22px;
    min-width: 50px;
    font-size: 11px;
}
QPushButton:hover {
    background-color: #7EC8E3;
}
QPushButton:pressed {
    background-color: #4A8AB0;
}
QPushButton:disabled {
    background-color: #D0D8DD;
    color: #7F8C8D;
}

/* 复选框 */
QCheckBox {
    color: #2C3E50;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #E0E8ED;
    border-radius: 4px;
    background-color: #FFFFFF;
}
QCheckBox::indicator:checked {
    background-color: #5BA3C6;
    border-color: #5BA3C6;
}
QCheckBox::indicator:checked:after {
    content: "✓";
    color: white;
    font-size: 12px;
    font-weight: bold;
}

/* 数字选择框 */
QSpinBox {
    background-color: #FFFFFF;
    color: #2C3E50;
    border: 1px solid #E0E8ED;
    border-radius: 6px;
    padding: 4px 8px;
}
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #FAFCFD;
    border: none;
    width: 20px;
}

/* 列表 */
QListWidget {
    background-color: #FFFFFF;
    color: #2C3E50;
    border: 1px solid #E0E8ED;
    border-radius: 6px;
}
QListWidget::item:selected {
    background-color: #87CEEB;
    color: #2C3E50;
}
QListWidget::item:hover {
    background-color: #FAFCFD;
}

/* 组框 */
QGroupBox {
    color: #5BA3C6;
    border: 1px solid #E0E8ED;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    font-weight: 600;
    font-size: 13px;
    background-color: #FFFFFF;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #5BA3C6;
}

/* 表格 */
QTableWidget {
    background-color: #FFFFFF;
    color: #2C3E50;
    border: 1px solid #E0E8ED;
    border-radius: 4px;
    gridline-color: #E0E8ED;
    font-size: 12px;
}
QTableWidget::item {
    padding: 6px;
}
QTableWidget::item:selected {
    background-color: #87CEEB;
}
QHeaderView::section {
    background-color: #FAFCFD;
    color: #5BA3C6;
    border: 1px solid #E0E8ED;
    padding: 8px;
    font-weight: 600;
}

/* 选项卡 */
QTabWidget::pane {
    border: 1px solid #E0E8ED;
    border-radius: 6px;
    background-color: #FFFFFF;
}
QTabBar::tab {
    background-color: #FAFCFD;
    color: #7F8C8D;
    border: 1px solid #E0E8ED;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 10px 20px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #5BA3C6;
    font-weight: 600;
}
QTabBar::tab:hover {
    background-color: #F5F9FC;
}

/* 菜单 */
QMenuBar {
    background-color: #FFFFFF;
    color: #2C3E50;
    border-bottom: 1px solid #E0E8ED;
}
QMenuBar::item:selected {
    background-color: #87CEEB;
}
QMenu {
    background-color: #FFFFFF;
    color: #2C3E50;
    border: 1px solid #E0E8ED;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #87CEEB;
}

/* 工具栏 */
QToolBar {
    background-color: #FFFFFF;
    border: none;
    spacing: 8px;
    padding: 6px;
}
QToolButton {
    background-color: transparent;
    color: #2C3E50;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px 12px;
}
QToolButton:hover {
    background-color: #87CEEB;
}

/* 滚动条 */
QScrollBar:vertical {
    background-color: transparent;
    width: 10px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #E0E8ED;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #5BA3C6;
}
QScrollBar:horizontal {
    background-color: transparent;
    height: 10px;
    border: none;
}
QScrollBar::handle:horizontal {
    background-color: #E0E8ED;
    border-radius: 5px;
    min-width: 30px;
}

/* 进度条 */
QProgressBar {
    background-color: #E0E8ED;
    color: #2C3E50;
    border: none;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #27AE60;
    border-radius: 4px;
}

/* 框架 */
QFrame {
    background-color: #FFFFFF;
    border-radius: 8px;
}
    """


def get_success_button_style():
    """成功/开始按钮 - 夏天绿"""
    return """
        QPushButton {
            background-color: #27AE60;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 4px 12px;
            min-height: 22px;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #2ECC71;
        }
        QPushButton:pressed {
            background-color: #229954;
        }
        QPushButton:disabled {
            background-color: #D0D8DD;
            color: #7F8C8D;
        }
    """


def get_danger_button_style():
    """危险/停止按钮 - 夏天红"""
    return """
        QPushButton {
            background-color: #E74C3C;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 4px 12px;
            min-height: 22px;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #EC7063;
        }
        QPushButton:pressed {
            background-color: #C0392B;
        }
        QPushButton:disabled {
            background-color: #D0D8DD;
            color: #7F8C8D;
        }
    """


def get_compact_button_style():
    """紧凑按钮"""
    return """
        QPushButton {
            background-color: #FAFCFD;
            color: #2C3E50;
            border: 1px solid #E0E8ED;
            border-radius: 3px;
            padding: 2px 8px;
            min-height: 20px;
            font-size: 11px;
        }
        QPushButton:hover {
            background-color: #87CEEB;
            border-color: #5BA3C6;
            color: white;
        }
    """


def get_icon_button_style(size=24):
    """图标按钮"""
    return """
        QPushButton {
            background-color: #FAFCFD;
            color: #2C3E50;
            border: 1px solid #E0E8ED;
            border-radius: 3px;
            padding: 2px;
            font-size: 12px;
            min-width: 24px;
            min-height: 20px;
        }
        QPushButton:hover {
            background-color: #87CEEB;
            border-color: #5BA3C6;
            color: white;
        }
    """


def get_group_style():
    """组框样式"""
    return f"""
        QGroupBox {{
            color: {SUMMER_PRIMARY};
            border: 1px solid {SUMMER_BORDER};
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 12px;
            font-weight: 600;
            font-size: 14px;
            background-color: {SUMMER_PANEL};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 10px;
            color: {SUMMER_PRIMARY};
        }}
    """


def get_terminal_style():
    """终端样式"""
    return f"""
        QPlainTextEdit {{
            background-color: {SUMMER_TERMINAL_BG};
            color: {SUMMER_TERMINAL_TEXT};
            border: 1px solid {SUMMER_BORDER};
            border-radius: 6px;
            font-family: {FONT_MONO};
            font-size: 12px;
            padding: 8px;
        }}
    """


def get_panel_style():
    """面板样式"""
    return f"""
        QFrame {{
            background-color: {SUMMER_PANEL};
            border: 1px solid {SUMMER_BORDER};
            border-radius: 8px;
        }}
    """


# 兼容旧代码的颜色别名
COLOR_PRIMARY_BG = SUMMER_BG
COLOR_PANEL_BG = SUMMER_PANEL
COLOR_INPUT_BG = SUMMER_CARD
COLOR_ACCENT = SUMMER_PRIMARY
COLOR_SUCCESS = SUMMER_SUCCESS
COLOR_WARNING = SUMMER_WARNING
COLOR_ERROR = SUMMER_ERROR
COLOR_TEXT = SUMMER_TEXT
COLOR_TEXT_DIM = SUMMER_TEXT_DIM
COLOR_BORDER = SUMMER_BORDER
COLOR_TERMINAL_BG = SUMMER_TERMINAL_BG
COLOR_TERMINAL_TEXT = SUMMER_TERMINAL_TEXT

# 兼容旧代码的函数别名
get_common_stylesheet = get_summer_stylesheet