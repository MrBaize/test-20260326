from typing import Dict, Any, Optional
try:
    # 作为包导入时使用相对导入
    from .ssh_client import SSHClient
    from .telnet_client import TelnetClient
    from .serial_client import SerialClient
    from .ftp_client import FTPClient
    from .sftp_client import SFTPClient
except ImportError:
    # 直接运行时使用绝对导入
    from ssh_client import SSHClient
    from telnet_client import TelnetClient
    from serial_client import SerialClient
    from ftp_client import FTPClient
    from sftp_client import SFTPClient


class ConnectionManager:
    """连接协议管理器类"""
    
    def __init__(self):
        self.protocols = {
            'ssh': SSHClient(),
            'telnet': TelnetClient(),
            'serial': SerialClient(),
            'ftp': FTPClient(),
            'sftp': SFTPClient()
        }
        
        self.active_connections = {}
    
    def connect(self, protocol: str, **kwargs) -> Dict[str, Any]:
        """
        建立连接
        
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
        if protocol in self.active_connections:
            self.disconnect(protocol)
        
        # 建立连接
        client = self.protocols[protocol]
        result = client.connect(**kwargs)
        
        if result['success']:
            self.active_connections[protocol] = client
        
        return result
    
    def disconnect(self, protocol: str) -> Dict[str, Any]:
        """
        断开连接
        
        Args:
            protocol: 协议类型
            
        Returns:
            断开结果字典
        """
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
    
    def disconnect_all(self) -> Dict[str, Any]:
        """
        断开所有连接
        
        Returns:
            断开结果字典
        """
        results = {}
        
        for protocol in list(self.active_connections.keys()):
            result = self.disconnect(protocol)
            results[protocol] = result
        
        return {
            'success': True,
            'message': '所有连接已断开',
            'results': results
        }
    
    def execute_command(self, protocol: str, command: str, **kwargs) -> Dict[str, Any]:
        """
        执行命令（适用于SSH和Telnet）
        
        Args:
            protocol: 协议类型
            command: 要执行的命令
            **kwargs: 额外参数
            
        Returns:
            执行结果字典
        """
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
    
    def send_data(self, protocol: str, data: str, **kwargs) -> Dict[str, Any]:
        """
        发送数据（适用于Serial）
        
        Args:
            protocol: 协议类型
            data: 要发送的数据
            **kwargs: 额外参数
            
        Returns:
            发送结果字典
        """
        if protocol not in self.active_connections:
            return {
                'success': False,
                'message': f'{protocol}未连接，请先建立连接'
            }
        
        if protocol == 'serial':
            client = self.active_connections[protocol]
            return client.send_data(data, **kwargs)
        else:
            return {
                'success': False,
                'message': f'{protocol}协议不支持数据发送'
            }
    
    def upload_file(self, protocol: str, local_path: str, remote_path: str) -> Dict[str, Any]:
        """
        上传文件（适用于FTP和SFTP）
        
        Args:
            protocol: 协议类型
            local_path: 本地文件路径
            remote_path: 远程文件路径
            
        Returns:
            上传结果字典
        """
        if protocol not in self.active_connections:
            return {
                'success': False,
                'message': f'{protocol}未连接，请先建立连接'
            }
        
        if protocol in ['ftp', 'sftp']:
            client = self.active_connections[protocol]
            return client.upload_file(local_path, remote_path)
        else:
            return {
                'success': False,
                'message': f'{protocol}协议不支持文件上传'
            }
    
    def download_file(self, protocol: str, remote_path: str, local_path: str) -> Dict[str, Any]:
        """
        下载文件（适用于FTP和SFTP）
        
        Args:
            protocol: 协议类型
            remote_path: 远程文件路径
            local_path: 本地文件路径
            
        Returns:
            下载结果字典
        """
        if protocol not in self.active_connections:
            return {
                'success': False,
                'message': f'{protocol}未连接，请先建立连接'
            }
        
        if protocol in ['ftp', 'sftp']:
            client = self.active_connections[protocol]
            return client.download_file(remote_path, local_path)
        else:
            return {
                'success': False,
                'message': f'{protocol}协议不支持文件下载'
            }
    
    def list_files(self, protocol: str, remote_path: str = '.') -> Dict[str, Any]:
        """
        列出文件（适用于FTP和SFTP）
        
        Args:
            protocol: 协议类型
            remote_path: 远程路径
            
        Returns:
            文件列表字典
        """
        if protocol not in self.active_connections:
            return {
                'success': False,
                'message': f'{protocol}未连接，请先建立连接'
            }
        
        if protocol == 'ftp':
            client = self.active_connections[protocol]
            return client.list_files(remote_path)
        elif protocol == 'sftp':
            client = self.active_connections[protocol]
            return client.list_directory(remote_path)
        else:
            return {
                'success': False,
                'message': f'{protocol}协议不支持文件列表'
            }
    
    def get_connection_status(self, protocol: Optional[str] = None) -> Dict[str, Any]:
        """
        获取连接状态
        
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
    
    def test_connection(self, protocol: str, **kwargs) -> Dict[str, Any]:
        """
        测试连接
        
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
    
    def get_available_ports(self) -> Dict[str, Any]:
        """
        获取可用的串口列表
        
        Returns:
            串口列表字典
        """
        return self.protocols['serial'].get_available_ports()
    
    def get_supported_protocols(self) -> Dict[str, Any]:
        """
        获取支持的协议列表
        
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