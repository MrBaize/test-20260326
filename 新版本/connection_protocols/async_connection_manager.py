"""
异步连接管理器 - 解决界面卡顿问题
使用线程池执行网络操作，避免阻塞主线程
"""

import socket
import threading
import concurrent.futures
from typing import Dict, Any, Optional, Callable
from functools import wraps

# 导入原有客户端
try:
    from .ssh_client import SSHClient
    from .telnet_client import TelnetClient
    from .serial_client import SerialClient
    from .ftp_client import FTPClient
    from .sftp_client import SFTPClient
except ImportError:
    from ssh_client import SSHClient
    from telnet_client import TelnetClient
    from serial_client import SerialClient
    from ftp_client import FTPClient
    from sftp_client import SFTPClient


# 设置全局socket超时，防止DNS解析等操作卡住
socket.setdefaulttimeout(30)


def run_in_thread(timeout: int = 30):
    """
    装饰器：在后台线程中运行函数，防止阻塞主线程
    
    Args:
        timeout: 最大等待时间（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    return {
                        'success': False,
                        'message': f'操作超时（超过{timeout}秒），请检查网络连接或服务器状态',
                        'error_type': 'timeout'
                    }
        return wrapper
    return decorator


class AsyncConnectionManager:
    """异步连接协议管理器 - 非阻塞版本"""
    
    def __init__(self):
        self.protocols = {
            'ssh': SSHClient(),
            'telnet': TelnetClient(),
            'serial': SerialClient(),
            'ftp': FTPClient(),
            'sftp': SFTPClient()
        }
        self.active_connections = {}
        self._lock = threading.Lock()
    
    @run_in_thread(timeout=35)
    def connect(self, protocol: str, **kwargs) -> Dict[str, Any]:
        """
        建立连接（异步版本）
        
        Args:
            protocol: 协议类型 (ssh, telnet, serial, ftp, sftp)
            **kwargs: 连接参数
            
        Returns:
            连接结果字典
        """
        if protocol not in self.protocols:
            return {
                'success': False,
                'message': f'不支持的协议类型: {protocol}'
            }
        
        # 如果已有连接，先断开
        with self._lock:
            if protocol in self.active_connections:
                self._disconnect_sync(protocol)
        
        # 建立连接
        client = self.protocols[protocol]
        result = client.connect(**kwargs)
        
        if result['success']:
            with self._lock:
                self.active_connections[protocol] = client
        
        return result
    
    def _disconnect_sync(self, protocol: str) -> Dict[str, Any]:
        """同步断开连接（内部使用）"""
        if protocol not in self.active_connections:
            return {
                'success': False,
                'message': f'未找到活跃的{protocol}连接'
            }
        
        client = self.active_connections[protocol]
        result = client.disconnect()
        
        if result['success']:
            del self.active_connections[protocol]
        
        return result
    
    @run_in_thread(timeout=10)
    def disconnect(self, protocol: str) -> Dict[str, Any]:
        """
        断开连接（异步版本）
        
        Args:
            protocol: 协议类型
            
        Returns:
            断开结果字典
        """
        with self._lock:
            return self._disconnect_sync(protocol)
    
    @run_in_thread(timeout=15)
    def disconnect_all(self) -> Dict[str, Any]:
        """
        断开所有连接（异步版本）
        
        Returns:
            断开结果字典
        """
        results = {}
        
        with self._lock:
            for protocol in list(self.active_connections.keys()):
                result = self._disconnect_sync(protocol)
                results[protocol] = result
        
        return {
            'success': True,
            'message': '所有连接已断开',
            'results': results
        }
    
    @run_in_thread(timeout=60)
    def execute_command(self, protocol: str, command: str, **kwargs) -> Dict[str, Any]:
        """
        执行命令（异步版本）
        
        Args:
            protocol: 协议类型
            command: 要执行的命令
            **kwargs: 额外参数
            
        Returns:
            执行结果字典
        """
        with self._lock:
            if protocol not in self.active_connections:
                return {
                    'success': False,
                    'message': f'{protocol}未连接，请先建立连接'
                }
            
            client = self.active_connections[protocol]
        
        if protocol == 'ssh':
            return client.execute_command(command)
        elif protocol == 'telnet':
            return client.send_command(command, **kwargs)
        else:
            return {
                'success': False,
                'message': f'{protocol}协议不支持命令执行'
            }
    
    @run_in_thread(timeout=300)
    def upload_file(self, protocol: str, local_path: str, remote_path: str,
                   progress_callback: Optional[Callable[[int, int], None]] = None,
                   should_cancel: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        上传文件（异步版本）
        
        Args:
            protocol: 协议类型
            local_path: 本地文件路径
            remote_path: 远程文件路径
            progress_callback: 进度回调函数
            should_cancel: 取消检查函数
            
        Returns:
            上传结果字典
        """
        with self._lock:
            if protocol not in self.active_connections:
                return {
                    'success': False,
                    'message': f'{protocol}未连接，请先建立连接'
                }
            
            client = self.active_connections[protocol]
        
        if protocol in ['ftp', 'sftp']:
            if protocol == 'ftp':
                return client.put_file(local_path, remote_path, progress_callback, should_cancel)
            else:
                return client.upload_file(local_path, remote_path, progress_callback, should_cancel)
        else:
            return {
                'success': False,
                'message': f'{protocol}协议不支持文件上传'
            }
    
    @run_in_thread(timeout=300)
    def download_file(self, protocol: str, remote_path: str, local_path: str,
                     progress_callback: Optional[Callable[[int, int], None]] = None,
                     should_cancel: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        下载文件（异步版本）
        
        Args:
            protocol: 协议类型
            remote_path: 远程文件路径
            local_path: 本地文件路径
            progress_callback: 进度回调函数
            should_cancel: 取消检查函数
            
        Returns:
            下载结果字典
        """
        with self._lock:
            if protocol not in self.active_connections:
                return {
                    'success': False,
                    'message': f'{protocol}未连接，请先建立连接'
                }
            
            client = self.active_connections[protocol]
        
        if protocol in ['ftp', 'sftp']:
            if protocol == 'ftp':
                return client.get_file(remote_path, local_path, progress_callback, should_cancel)
            else:
                return client.download_file(remote_path, local_path, progress_callback, should_cancel)
        else:
            return {
                'success': False,
                'message': f'{protocol}协议不支持文件下载'
            }
    
    @run_in_thread(timeout=30)
    def list_files(self, protocol: str, remote_path: str = '.') -> Dict[str, Any]:
        """
        列出文件（异步版本）
        
        Args:
            protocol: 协议类型
            remote_path: 远程路径
            
        Returns:
            文件列表字典
        """
        with self._lock:
            if protocol not in self.active_connections:
                return {
                    'success': False,
                    'message': f'{protocol}未连接，请先建立连接'
                }
            
            client = self.active_connections[protocol]
        
        if protocol == 'ftp':
            return client.list_files(remote_path)
        elif protocol == 'sftp':
            return client.list_directory(remote_path)
        else:
            return {
                'success': False,
                'message': f'{protocol}协议不支持文件列表'
            }
    
    def get_connection_status(self, protocol: Optional[str] = None) -> Dict[str, Any]:
        """
        获取连接状态（同步，因为只是读取状态）
        
        Args:
            protocol: 协议类型，None表示获取所有连接状态
            
        Returns:
            连接状态字典
        """
        if protocol:
            if protocol not in self.protocols:
                return {
                    'success': False,
                    'message': f'不支持的协议类型: {protocol}'
                }
            
            client = self.protocols[protocol]
            return client.get_connection_status()
        else:
            status = {}
            for proto, client in self.protocols.items():
                status[proto] = client.get_connection_status()
            
            return {
                'success': True,
                'status': status,
                'active_connections': list(self.active_connections.keys())
            }
    
    @run_in_thread(timeout=15)
    def test_connection(self, protocol: str, **kwargs) -> Dict[str, Any]:
        """
        测试连接（异步版本）
        
        Args:
            protocol: 协议类型
            **kwargs: 连接参数
            
        Returns:
            测试结果字典
        """
        if protocol not in self.protocols:
            return {
                'success': False,
                'message': f'不支持的协议类型: {protocol}'
            }
        
        client = self.protocols[protocol]
        return client.test_connection(**kwargs)
    
    @run_in_thread(timeout=10)
    def get_available_ports(self) -> Dict[str, Any]:
        """
        获取可用的串口列表（异步版本）
        
        Returns:
            串口列表字典
        """
        return self.protocols['serial'].get_available_ports()
    
    def get_supported_protocols(self) -> Dict[str, Any]:
        """
        获取支持的协议列表（同步）
        
        Returns:
            协议列表字典
        """
        protocols_info = {
            'ssh': {
                'description': 'SSH协议 - 安全的远程登录协议',
                'required_params': ['ip', 'username', 'password'],
                'optional_params': ['port', 'timeout'],
                'capabilities': ['command_execution', 'file_transfer']
            },
            'telnet': {
                'description': 'Telnet协议 - 远程登录协议',
                'required_params': ['ip', 'username', 'password'],
                'optional_params': ['port', 'baud_rate', 'timeout'],
                'capabilities': ['command_execution']
            },
            'serial': {
                'description': '串口通信协议',
                'required_params': ['com_port', 'baud_rate'],
                'optional_params': ['bytesize', 'parity', 'stopbits', 'timeout'],
                'capabilities': ['data_transmission']
            },
            'ftp': {
                'description': 'FTP协议 - 文件传输协议',
                'required_params': ['ip', 'username', 'password'],
                'optional_params': ['port', 'timeout'],
                'capabilities': ['file_transfer', 'directory_operations']
            },
            'sftp': {
                'description': 'SFTP协议 - 安全的文件传输协议',
                'required_params': ['ip', 'username', 'password'],
                'optional_params': ['port', 'timeout'],
                'capabilities': ['file_transfer', 'directory_operations']
            }
        }
        
        return {
            'success': True,
            'protocols': protocols_info
        }


# 为了保持向后兼容，保留原类名
ConnectionManager = AsyncConnectionManager
