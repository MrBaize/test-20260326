"""
数据传输模块
包含数据文件传输相关的功能
"""

from .enhanced_data_transfer_page import EnhancedDataTransferPage
from .file_transfer_engine import FileTransferEngine, TransferTask, TransferStatus

__all__ = ['EnhancedDataTransferPage', 'DataTransferPage', 'FileTransferEngine', 'TransferTask', 'TransferStatus']

# 向后兼容
DataTransferPage = EnhancedDataTransferPage
FileTransferManager = FileTransferEngine