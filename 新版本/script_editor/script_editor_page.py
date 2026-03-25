from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit

# 导入统一UI样式
from themes.ui_styles import get_common_stylesheet


class ScriptEditorPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(get_common_stylesheet())  # 应用统一UI样式
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题
        title_label = QLabel("📝 脚本编辑器")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #eaeaea;
                margin-bottom: 15px;
            }
        """)
        layout.addWidget(title_label)
        
        # 脚本编辑器
        script_editor = QTextEdit()
        script_editor.setPlaceholderText("在此处编写您的脚本代码...")
        script_editor.setStyleSheet("""
            QTextEdit {
                background-color: #0a0a0a;
                color: #00ff00;
                border: 2px solid #2d4a6f;
                border-radius: 6px;
                padding: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border-color: #e94560;
            }
        """)
        layout.addWidget(script_editor)
        
        self.setLayout(layout)
