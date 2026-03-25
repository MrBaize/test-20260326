from PyQt6.QtWidgets import QApplication, QStyleFactory
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt
from .ui_styles import get_summer_stylesheet


class ThemeManager:
    def __init__(self, app):
        self.app = app
        self.current_theme = "Summer"
        self.apply_summer_theme()
    
    def get_available_themes(self):
        """获取可用的主题列表"""
        return ["Summer"]
    
    def get_all_themes(self):
        """获取所有主题"""
        return self.get_available_themes()
    
    def get_current_theme(self):
        """获取当前主题"""
        return self.current_theme
    
    def apply_theme(self, theme_name):
        """应用指定的主题"""
        if theme_name == "Summer":
            return self.apply_summer_theme()
        return False
    
    def apply_summer_theme(self):
        """应用夏天主题"""
        try:
            self.app.setStyle("Fusion")
            
            # 设置清新的调色板
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(240, 247, 250))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(44, 62, 80))
            palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(250, 252, 253))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(44, 62, 80))
            palette.setColor(QPalette.ColorRole.Text, QColor(44, 62, 80))
            palette.setColor(QPalette.ColorRole.Button, QColor(91, 163, 198))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.BrightText, QColor(231, 76, 60))
            palette.setColor(QPalette.ColorRole.Link, QColor(52, 152, 219))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(135, 206, 235))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(44, 62, 80))
            
            self.app.setPalette(palette)
            self.app.setStyleSheet(get_summer_stylesheet())
            self.current_theme = "Summer"
            
            # 刷新所有窗口
            for widget in self.app.allWidgets():
                widget.update()
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            
            return True
        except Exception as e:
            print(f"应用夏天主题失败: {e}")
            return False