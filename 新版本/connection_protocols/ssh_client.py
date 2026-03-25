import paramiko
import socket
from typing import Optional, Dict, Any


class SSHClient:
    """SSH连接客户端类"""
    
    def __init__(self):
        self.client = None
        self.sftp_client = None
        self.connected = False
        self.connection_info = {}
    
    def connect(self, ip: str, username: str, password: str, port: int = 22, 
                timeout: int = 30) -> Dict[str, Any]:
        """
        连接到SSH服务器
        
        Args:
            ip: 服务器IP地址
            username: 用户名
            password: 密码
            port: 端口号，默认22
            timeout: 连接超时时间，默认30秒
            
        Returns:
            连接结果字典
        """
        try:
            # 创建SSH客户端
            self.client = paramiko.SSHClient()
            
            # 自动添加主机密钥（生产环境应使用更安全的方式）
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接到服务器
            self.client.connect(
                hostname=ip,
                username=username,
                password=password,
                port=port,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False
            )
            
            # 创建SFTP客户端
            self.sftp_client = self.client.open_sftp()
            
            self.connected = True
            self.connection_info = {
                'ip': ip,
                'username': username,
                'port': port,
                'status': 'connected'
            }
            
            return {
                'success': True,
                'message': f'SSH连接成功: {ip}:{port}',
                'connection_info': self.connection_info
            }
            
        except paramiko.AuthenticationException:
            return {
                'success': False,
                'message': 'SSH认证失败：用户名或密码错误',
                'error_type': 'authentication'
            }
        except paramiko.SSHException as e:
            return {
                'success': False,
                'message': f'SSH连接异常: {str(e)}',
                'error_type': 'ssh_exception'
            }
        except socket.timeout:
            return {
                'success': False,
                'message': 'SSH连接超时',
                'error_type': 'timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'SSH连接失败: {str(e)}',
                'error_type': 'general'
            }
    
    def execute_command(self, command: str) -> Dict[str, Any]:
        """
        执行远程命令
        
        Args:
            command: 要执行的命令
            
        Returns:
            命令执行结果字典
        """
        if not self.connected or not self.client:
            return {
                'success': False,
                'message': 'SSH未连接，请先建立连接'
            }
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            
            # 读取输出
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')
            
            return {
                'success': True,
                'output': output,
                'error': error,
                'exit_status': stdout.channel.recv_exit_status()
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'命令执行失败: {str(e)}'
            }
    
    def upload_file(self, local_path: str, remote_path: str) -> Dict[str, Any]:
        """
        上传文件到远程服务器
        
        Args:
            local_path: 本地文件路径
            remote_path: 远程文件路径
            
        Returns:
            上传结果字典
        """
        if not self.connected or not self.sftp_client:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立SSH连接'
            }
        
        try:
            self.sftp_client.put(local_path, remote_path)
            return {
                'success': True,
                'message': f'文件上传成功: {local_path} -> {remote_path}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'文件上传失败: {str(e)}'
            }
    
    def download_file(self, remote_path: str, local_path: str) -> Dict[str, Any]:
        """
        从远程服务器下载文件
        
        Args:
            remote_path: 远程文件路径
            local_path: 本地文件路径
            
        Returns:
            下载结果字典
        """
        if not self.connected or not self.sftp_client:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立SSH连接'
            }
        
        try:
            self.sftp_client.get(remote_path, local_path)
            return {
                'success': True,
                'message': f'文件下载成功: {remote_path} -> {local_path}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'文件下载失败: {str(e)}'
            }
    
    def disconnect(self) -> Dict[str, Any]:
        """
        断开SSH连接
        
        Returns:
            断开连接结果字典
        """
        try:
            if self.sftp_client:
                self.sftp_client.close()
                self.sftp_client = None
            
            if self.client:
                self.client.close()
                self.client = None
            
            self.connected = False
            self.connection_info = {}
            
            return {
                'success': True,
                'message': 'SSH连接已断开'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'断开连接失败: {str(e)}'
            }
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        获取连接状态
        
        Returns:
            连接状态字典
        """
        return {
            'connected': self.connected,
            'connection_info': self.connection_info
        }
    
    def test_connection(self, ip: str, username: str, password: str, 
                       port: int = 22, timeout: int = 10) -> Dict[str, Any]:
        """
        测试SSH连接
        
        Args:
            ip: 服务器IP地址
            username: 用户名
            password: 密码
            port: 端口号，默认22
            timeout: 连接超时时间，默认10秒
            
        Returns:
            测试结果字典
        """
        test_client = None
        try:
            test_client = paramiko.SSHClient()
            test_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            test_client.connect(
                hostname=ip,
                username=username,
                password=password,
                port=port,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False
            )
            
            return {
                'success': True,
                'message': f'SSH连接测试成功: {ip}:{port}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'SSH连接测试失败: {str(e)}'
            }
        finally:
            # 确保测试连接被正确关闭
            if test_client:
                try:
                    test_client.close()
                except:
                    pass