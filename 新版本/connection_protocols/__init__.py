# 连接协议包初始化文件

# 导入基础连接管理器
from .connection_manager import ConnectionManager

# 导入异步连接管理器（推荐用于GUI/Web应用）
from .async_connection_manager import AsyncConnectionManager

# 导入增强版客户端
from .ssh_client_enhanced import SSHClientEnhanced
from .telnet_client_enhanced import TelnetClientEnhanced

# 导入快速修复工具
from .quick_fix import ConnectionManagerWrapper, create_async_manager

# 导入原始客户端
from .ssh_client import SSHClient
from .telnet_client import TelnetClient
from .serial_client import SerialClient
from .ftp_client import FTPClient
from .sftp_client import SFTPClient

__all__ = [
    # 连接管理器
    'ConnectionManager',        # 原始管理器（同步）
    'AsyncConnectionManager',    # 异步管理器（推荐）
    'ConnectionManagerWrapper',  # 包装器（快速修复）
    'create_async_manager',      # 便捷函数

    # 增强版客户端
    'SSHClientEnhanced',
    'TelnetClientEnhanced',

    # 原始客户端
    'SSHClient',
    'TelnetClient',
    'SerialClient',
    'FTPClient',
    'SFTPClient',
]

__version__ = '2.0.0'

# 全局配置
import socket
socket.setdefaulttimeout(30)  # 设置默认socket超时为30秒