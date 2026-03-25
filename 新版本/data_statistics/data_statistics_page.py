from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit

# 导入统一UI样式
from themes.ui_styles import get_common_stylesheet, COLOR_TEXT, COLOR_PRIMARY_BG


class DataStatisticsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(get_common_stylesheet())  # 应用统一UI样式
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题
        title_label = QLabel("📊 数据统计")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #eaeaea;
                margin-bottom: 15px;
            }
        """)
        layout.addWidget(title_label)
        
        # 数据统计区域
        statistics_area = QTextEdit("数据统计功能待实现...")
        statistics_area.setReadOnly(True)
        statistics_area.setStyleSheet("""
            QTextEdit {
                background-color: #16213e;
                border: 2px solid #2d4a6f;
                border-radius: 6px;
                padding: 20px;
                font-size: 14px;
                color: #eaeaea;
                text-align: center;
            }
        """)
        layout.addWidget(statistics_area)
        
        self.setLayout(layout)
