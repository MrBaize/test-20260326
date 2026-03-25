"""
路径处理工具类
统一路径标准化和验证逻辑
"""

import os
import sys


class PathUtils:
    """路径处理工具类"""
    
    @staticmethod
    def normalize_path(path):
        """
        标准化路径处理
        
        Args:
            path: 原始路径
            
        Returns:
            str: 标准化后的路径
        """
        if not path or not isinstance(path, str):
            return os.getcwd()
        
        # 规范化路径
        path = os.path.normpath(path)
        
        # 特殊处理Windows根目录
        if path == "C:" or path == "C:\\":
            return "C:\\"
        
        return path
    
    @staticmethod
    def is_valid_path(path, check_exists=True, check_is_dir=True):
        """
        验证路径是否有效
        
        Args:
            path: 待验证路径
            check_exists: 是否检查路径存在性
            check_is_dir: 是否检查是否为目录
            
        Returns:
            tuple: (是否有效, 错误消息)
        """
        if not path:
            return False, "路径不能为空"
        
        if not isinstance(path, str):
            return False, "路径必须是字符串"
        
        # 检查路径长度（Windows路径长度限制）
        if len(path) > 260:
            return False, "路径过长"
        
        # 检查是否包含非法字符（只检查文件名部分，不检查完整路径）
        invalid_chars = ['<', '>', '"', '|', '?', '*']
        filename = os.path.basename(path)
        for char in invalid_chars:
            if char in filename:
                return False, f"文件名包含非法字符: {char}"
        
        # 检查路径存在性（可选）
        if check_exists and not os.path.exists(path):
            return False, "路径不存在"
        
        # 检查是否为目录（可选）
        if check_exists and check_is_dir and not os.path.isdir(path):
            return False, "路径不是目录"
        
        return True, ""
    
    @staticmethod
    def get_parent_directory(path):
        """
        获取父目录路径
        
        Args:
            path: 当前路径
            
        Returns:
            str: 父目录路径
        """
        path = PathUtils.normalize_path(path)
        
        # 如果是根目录，不执行操作
        if path == os.path.abspath(os.sep) or path == "/":
            return path
        
        # 计算父目录路径
        parent_path = os.path.dirname(path)
        
        # 如果父目录为空，设置为根目录
        if not parent_path:
            parent_path = os.path.abspath(os.sep)
        
        return parent_path
    
    @staticmethod
    def is_root_directory(path):
        """
        判断是否为根目录
        
        Args:
            path: 路径
            
        Returns:
            bool: 是否为根目录
        """
        path = PathUtils.normalize_path(path)
        return path == os.path.abspath(os.sep) or path == "/"
    
    @staticmethod
    def join_paths(base_path, *paths):
        """
        安全的路径拼接，支持跨平台
        
        Args:
            base_path: 基础路径
            *paths: 要拼接的路径部分
            
        Returns:
            str: 拼接后的路径
        """
        if not base_path:
            base_path = os.getcwd()
        
        result = os.path.join(base_path, *paths)
        
        # 如果是远程路径，确保使用正斜杠
        if base_path.startswith('/'):
            result = result.replace('\\', '/').replace('//', '/')
        
        return result
    
    @staticmethod
    def ensure_directory_exists(path):
        """
        确保目录存在，如果不存在则创建
        
        Args:
            path: 目录路径
            
        Returns:
            bool: 是否成功
        """
        try:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            return True
        except Exception:
            return False
    
    @staticmethod
    def format_remote_path(path):
        """
        格式化远程路径
        
        Args:
            path: 远程路径
            
        Returns:
            str: 格式化后的远程路径
        """
        if not path:
            return "/"
        
        # 确保路径以斜杠开头
        if not path.startswith("/"):
            path = "/" + path
        
        # 标准化路径
        path = os.path.normpath(path).replace("\\", "/")
        
        # 如果路径为空，设置为根目录
        if not path:
            path = "/"
        
        return path
    
    @staticmethod
    def get_file_basename(path):
        """
        获取文件名（跨平台安全）
        
        Args:
            path: 文件路径
            
        Returns:
            str: 文件名
        """
        try:
            return os.path.basename(path)
        except Exception:
            return "未知文件"
    
    @staticmethod
    def is_system_file(filename):
        """
        判断是否为系统文件
        
        Args:
            filename: 文件名
            
        Returns:
            bool: 是否为系统文件
        """
        import fnmatch
        
        system_files = [
            '.gitignore', '*.pyc', '__pycache__'
        ]
        
        for sys_file in system_files:
            if sys_file.startswith('*'):
                # 通配符匹配
                if fnmatch.fnmatch(filename.lower(), sys_file.lower()):
                    return True
            elif filename.lower() == sys_file.lower():
                return True
        
        return False