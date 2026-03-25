"""
真正非阻塞的连接管理器

关键改进:
- 不等待连接完成就返回
- 连接在后台线程执行
- 主线程立即返回,可以继续处理UI
"""

import socket
import threading
from typing import Dict, Any, Optional, Callable

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

socket.setdefaulttimeout(30)


class NonBlockingConnectionManager:
    """
    真正非阻塞的连接管理器

    使用方法:
        manager = NonBlockingConnectionManager()

        # 方式1: 使用回调 (推荐)
        manager.test_connection(
            'ssh',
            ip='192.168.1.100',
            username='root',
            password='password',
            callback=lambda result: print(result)
        )

        # 方式2: 后台执行,不等待
        manager.test_connection('ssh', ip='...', username='...', password='...')
    """

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

    def _run_in_thread(self, func: Callable, args: tuple = (), kwargs: dict = {},
                       callback: Optional[Callable] = None) -> threading.Thread:
        """
        在后台线程执行函数

        Args:
            func: 要执行的函数
            args: 位置参数
            kwargs: 关键字参数
            callback: 完成回调 callback(result)

        Returns:
            后台线程对象
        """
        def worker():
            try:
                result = func(*args, **kwargs)
                if callback:
                    try:
                        callback(result)
                    except Exception as e:
                        print(f"回调函数执行失败: {e}")
            except Exception as e:
                error_result = {
                    'success': False,
                    'message': f'操作异常: {str(e)}',
                    'error_type': 'exception'
                }
                if callback:
                    try:
                        callback(error_result)
                    except Exception as e2:
                        print(f"回调函数执行失败: {e2}")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread

    def test_connection(self, protocol: str, callback: Optional[Callable] = None, **kwargs) -> threading.Thread:
        """
        测试连接（非阻塞）

        Args:
            protocol: 协议类型
            callback: 完成回调函数
            **kwargs: 连接参数

        Returns:
            后台线程对象
        """
        if protocol not in self.protocols:
            error_result = {
                'success': False,
                'message': f'不支持的协议类型: {protocol}'
            }
            if callback:
                callback(error_result)
            return None

        client = self.protocols[protocol]
        return self._run_in_thread(
            client.test_connection,
            kwargs=kwargs,
            callback=callback
        )

    def connect(self, protocol: str, callback: Optional[Callable] = None, **kwargs) -> threading.Thread:
        """
        建立连接（非阻塞）

        Args:
            protocol: 协议类型
            callback: 完成回调函数
            **kwargs: 连接参数

        Returns:
            后台线程对象
        """
        if protocol not in self.protocols:
            error_result = {
                'success': False,
                'message': f'不支持的协议类型: {protocol}'
            }
            if callback:
                callback(error_result)
            return None

        def connect_worker():
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

        return self._run_in_thread(connect_worker, kwargs=kwargs, callback=callback)

    def disconnect(self, protocol: str, callback: Optional[Callable] = None) -> threading.Thread:
        """
        断开连接（非阻塞）

        Args:
            protocol: 协议类型
            callback: 完成回调函数

        Returns:
            后台线程对象
        """
        def disconnect_worker():
            with self._lock:
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

        return self._run_in_thread(disconnect_worker, callback=callback)

    def execute_command(self, protocol: str, command: str,
                       callback: Optional[Callable] = None, **kwargs) -> threading.Thread:
        """
        执行命令（非阻塞）

        Args:
            protocol: 协议类型
            command: 要执行的命令
            callback: 完成回调函数
            **kwargs: 额外参数

        Returns:
            后台线程对象
        """
        def command_worker():
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

        return self._run_in_thread(command_worker, kwargs=kwargs, callback=callback)

    def upload_file(self, protocol: str, local_path: str, remote_path: str,
                   callback: Optional[Callable] = None, **kwargs) -> threading.Thread:
        """
        上传文件（非阻塞）

        Args:
            protocol: 协议类型
            local_path: 本地文件路径
            remote_path: 远程文件路径
            callback: 完成回调函数
            **kwargs: 额外参数

        Returns:
            后台线程对象
        """
        def upload_worker():
            with self._lock:
                if protocol not in self.active_connections:
                    return {
                        'success': False,
                        'message': f'{protocol}未连接，请先建立连接'
                    }

                client = self.active_connections[protocol]

            if protocol in ['ftp', 'sftp']:
                if protocol == 'ftp':
                    return client.put_file(local_path, remote_path, **kwargs)
                else:
                    return client.upload_file(local_path, remote_path, **kwargs)
            else:
                return {
                    'success': False,
                    'message': f'{protocol}协议不支持文件上传'
                }

        return self._run_in_thread(upload_worker, callback=callback)

    def download_file(self, protocol: str, remote_path: str, local_path: str,
                     callback: Optional[Callable] = None, **kwargs) -> threading.Thread:
        """
        下载文件（非阻塞）

        Args:
            protocol: 协议类型
            remote_path: 远程文件路径
            local_path: 本地文件路径
            callback: 完成回调函数
            **kwargs: 额外参数

        Returns:
            后台线程对象
        """
        def download_worker():
            with self._lock:
                if protocol not in self.active_connections:
                    return {
                        'success': False,
                        'message': f'{protocol}未连接，请先建立连接'
                    }

                client = self.active_connections[protocol]

            if protocol in ['ftp', 'sftp']:
                if protocol == 'ftp':
                    return client.get_file(remote_path, local_path, **kwargs)
                else:
                    return client.download_file(remote_path, local_path, **kwargs)
            else:
                return {
                    'success': False,
                    'message': f'{protocol}协议不支持文件下载'
                }

        return self._run_in_thread(download_worker, callback=callback)

    def get_connection_status(self, protocol: Optional[str] = None) -> Dict[str, Any]:
        """
        获取连接状态（同步，只读操作）

        Args:
            protocol: 协议类型

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

    def get_supported_protocols(self) -> Dict[str, Any]:
        """获取支持的协议列表"""
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
