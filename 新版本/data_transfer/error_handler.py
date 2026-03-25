"""
错误处理工具类
统一错误处理和消息显示
"""

import logging
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt

from .ui_constants import UIConstants


class ErrorHandler:
    """错误处理工具类"""
    
    @staticmethod
    def handle_file_operation_error(operation, path, error, parent=None):
        """
        统一文件操作错误处理
        
        Args:
            operation: 操作类型（upload/download/delete等）
            path: 文件路径
            error: 异常对象
            parent: 父窗口（用于QMessageBox）
        """
        operation_names = {
            'upload': '上传',
            'download': '下载',
            'delete': '删除',
            'rename': '重命名',
            'create': '创建',
        }
        
        op_name = operation_names.get(operation, '操作')
        error_msg = f"{op_name}失败: {path}\n错误: {str(error)}"
        
        # 记录错误日志
        ErrorHandler._log_error(f"{op_name}错误", error)
        
        # 显示错误消息
        ErrorHandler.show_error_message(parent, f"{op_name}失败", error_msg)
    
    @staticmethod
    def handle_connection_error(device_name, error, parent=None):
        """
        处理连接错误
        
        Args:
            device_name: 设备名称
            error: 异常对象
            parent: 父窗口
        """
        error_msg = f"设备 {device_name} 连接失败\n错误: {str(error)}"
        
        # 记录错误日志
        ErrorHandler._log_error("连接错误", error)
        
        # 显示错误消息
        ErrorHandler.show_error_message(parent, "连接失败", error_msg)
    
    @staticmethod
    def handle_path_error(path, error, parent=None):
        """
        处理路径相关错误
        
        Args:
            path: 路径
            error: 异常对象
            parent: 父窗口
        """
        error_type = type(error).__name__
        
        if error_type == 'FileNotFoundError':
            error_msg = UIConstants.ERROR_MESSAGES['file_not_found'].format(path)
        elif error_type == 'PermissionError':
            error_msg = UIConstants.ERROR_MESSAGES['permission_denied'].format(path)
        elif error_type == 'NotADirectoryError':
            error_msg = f"路径不是目录: {path}"
        elif error_type == 'ValueError':
            error_msg = f"无效路径: {path}"
        else:
            error_msg = f"路径错误: {path}\n错误: {str(error)}"
        
        # 记录错误日志
        ErrorHandler._log_error("路径错误", error)
        
        # 显示错误消息
        ErrorHandler.show_error_message(parent, "路径错误", error_msg)
    
    @staticmethod
    def handle_transfer_error(task_id, error, parent=None):
        """
        处理传输错误
        
        Args:
            task_id: 任务ID
            error: 异常对象
            parent: 父窗口
        """
        error_msg = f"传输任务 {task_id} 失败\n错误: {str(error)}"
        
        # 记录错误日志
        ErrorHandler._log_error("传输错误", error)
        
        # 显示错误消息
        ErrorHandler.show_warning_message(parent, "传输失败", error_msg)
    
    @staticmethod
    def show_error_message(parent, title, message):
        """
        显示错误消息框
        
        Args:
            parent: 父窗口
            title: 标题
            message: 消息内容
        """
        QMessageBox.critical(parent, title, message)
    
    @staticmethod
    def show_warning_message(parent, title, message):
        """
        显示警告消息框
        
        Args:
            parent: 父窗口
            title: 标题
            message: 消息内容
        """
        QMessageBox.warning(parent, title, message)
    
    @staticmethod
    def show_info_message(parent, title, message):
        """
        显示信息消息框
        
        Args:
            parent: 父窗口
            title: 标题
            message: 消息内容
        """
        QMessageBox.information(parent, title, message)
    
    @staticmethod
    def ask_confirmation(parent, title, question):
        """
        显示确认对话框
        
        Args:
            parent: 父窗口
            title: 标题
            question: 问题内容
            
        Returns:
            bool: 用户是否确认
        """
        reply = QMessageBox.question(
            parent, title, question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes
    
    @staticmethod
    def _log_error(context, error):
        """
        记录错误日志
        
        Args:
            context: 错误上下文
            error: 异常对象
        """
        try:
            # 配置日志
            logging.basicConfig(
                level=logging.ERROR,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                filename='app_error.log',
                filemode='a'
            )
            
            logger = logging.getLogger('EnhancedDataTransfer')
            logger.error(f"{context}: {str(error)}", exc_info=True)
            
        except Exception:
            # 如果日志记录失败，打印到控制台
            print(f"[{context}] 错误: {str(error)}")
            import traceback
            traceback.print_exc()
    
    @staticmethod
    def get_error_summary(error):
        """
        获取错误摘要
        
        Args:
            error: 异常对象
            
        Returns:
            str: 错误摘要
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        # 根据错误类型提供更友好的错误消息
        if error_type == 'ConnectionError':
            return "网络连接失败，请检查网络设置"
        elif error_type == 'TimeoutError':
            return "操作超时，请重试"
        elif error_type == 'PermissionError':
            return "权限不足，请检查文件权限"
        elif error_type == 'FileNotFoundError':
            return "文件不存在，请检查文件路径"
        elif error_type == 'IOError':
            return "文件读写错误"
        else:
            return f"{error_type}: {error_message}"
    
    @staticmethod
    def is_recoverable_error(error):
        """
        判断错误是否可恢复
        
        Args:
            error: 异常对象
            
        Returns:
            bool: 是否可恢复
        """
        recoverable_errors = [
            'ConnectionError',
            'TimeoutError',
            'TemporaryError',
        ]
        
        error_type = type(error).__name__
        return error_type in recoverable_errors
    
    @staticmethod
    def handle_operation_result(parent, operation, success_count, failed_items):
        """
        处理操作结果并显示
        
        Args:
            parent: 父窗口
            operation: 操作类型
            success_count: 成功数量
            failed_items: 失败项目列表
        """
        operation_names = {
            'upload': '上传',
            'download': '下载',
            'delete': '删除',
            'rename': '重命名',
        }
        
        op_name = operation_names.get(operation, '操作')
        
        if failed_items:
            # 有失败项目
            message = f"成功{op_name} {success_count} 个项目\n失败项目:\n" + "\n".join(failed_items)
            ErrorHandler.show_warning_message(parent, f"{op_name}结果", message)
        else:
            # 全部成功
            message = UIConstants.SUCCESS_MESSAGES[f'{operation}_success'].format(success_count)
            ErrorHandler.show_info_message(parent, f"{op_name}成功", message)