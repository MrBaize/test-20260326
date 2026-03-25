"""
增强版 SSH 客户端 - 解决连接卡住问题
添加了更完善的超时控制和异常处理
"""

import paramiko
import socket
import threading
from typing import Optional, Dict, Any


class SSHClientEnhanced:
    """增强版 SSH连接客户端类 - 带超时保护"""
    
    def __init__(self):
        self.client = None
        self.sftp_client = None
        self.connected = False
        self.connection_info = {}
    
    def _create_connection_with_timeout(self, ip: str, username: str, password: str, 
                                        port: int, timeout: int) -> Optional[paramiko.SSHClient]:
        """
        创建SSH连接，带完整的超时控制
        
        解决 paramiko.connect() timeout 只控制TCP握手的问题
        """
        # 先尝试TCP连接，设置socket级别超时
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        try:
            # 尝试建立TCP连接（包括DNS解析）
            sock.connect((ip, port))
        except socket.timeout:
            raise socket.timeout(f"连接 {ip}:{port} 超时")
        except socket.gaierror as e:
            raise Exception(f"无法解析主机地址 {ip}: {str(e)}")
        except Exception as e:
            raise Exception(f"TCP连接失败: {str(e)}")
        
        # TCP连接成功后，创建SSH客户端
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 使用已连接的socket进行SSH握手，这样可以更好地控制超时
        try:
            client.connect(
                hostname=ip,
                username=username,
                password=password,
                port=port,
                sock=sock,  # 使用已连接的socket
                timeout=timeout,
                banner_timeout=timeout,  # SSH banner等待超时
                auth_timeout=timeout,    # 认证超时
                allow_agent=False,
                look_for_keys=False
            )
            return client
        except Exception:
            sock.close()
            raise
    
    def connect(self, ip: str, username: str, password: str, port: int = 22, 
                timeout: int = 30) -> Dict[str, Any]:
        """
        连接到SSH服务器（增强版，带完整超时控制）
        
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
            # 使用增强的连接方法
            self.client = self._create_connection_with_timeout(
                ip, username, password, port, timeout
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
                'message': f'SSH连接超时（超过{timeout}秒）',
                'error_type': 'timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'SSH连接失败: {str(e)}',
                'error_type': 'general'
            }
    
    def execute_command(self, command: str, timeout: int = 60) -> Dict[str, Any]:
        """
        执行远程命令（带超时）
        
        Args:
            command: 要执行的命令
            timeout: 命令执行超时时间，默认60秒
            
        Returns:
            命令执行结果字典
        """
        if not self.connected or not self.client:
            return {
                'success': False,
                'message': 'SSH未连接，请先建立连接'
            }
        
        try:
            # 设置通道超时
            transport = self.client.get_transport()
            if transport:
                transport.set_keepalive(30)  # 保持连接活跃
            
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            
            # 读取输出
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')
            
            exit_status = stdout.channel.recv_exit_status()
            
            return {
                'success': True,
                'output': output,
                'error': error,
                'exit_status': exit_status
            }
            
        except socket.timeout:
            return {
                'success': False,
                'message': f'命令执行超时（超过{timeout}秒）',
                'error_type': 'timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'命令执行失败: {str(e)}'
            }
    
    def upload_file(self, local_path: str, remote_path: str) -> Dict[str, Any]:
        """上传文件到远程服务器"""
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
        """从远程服务器下载文件"""
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
        """断开SSH连接"""
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
        """获取连接状态"""
        # 检查连接是否仍然活跃
        is_alive = False
        if self.connected and self.client:
            try:
                transport = self.client.get_transport()
                is_alive = transport is not None and transport.is_active()
            except:
                is_alive = False
        
        return {
            'connected': self.connected and is_alive,
            'connection_info': self.connection_info
        }
    
    def test_connection(self, ip: str, username: str, password: str, 
                       port: int = 22, timeout: int = 10) -> Dict[str, Any]:
        """
        测试SSH连接（增强版，带完整超时控制）
        
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
        sock = None
        try:
            # 先尝试TCP连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))
            
            # TCP连接成功，再进行SSH握手
            test_client = paramiko.SSHClient()
            test_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            test_client.connect(
                hostname=ip,
                username=username,
                password=password,
                port=port,
                sock=sock,
                timeout=timeout,
                banner_timeout=timeout,
                auth_timeout=timeout,
                allow_agent=False,
                look_for_keys=False
            )
            
            return {
                'success': True,
                'message': f'SSH连接测试成功: {ip}:{port}'
            }
            
        except socket.timeout:
            return {
                'success': False,
                'message': f'SSH连接测试超时（超过{timeout}秒）',
                'error_type': 'timeout'
            }
        except socket.gaierror as e:
            return {
                'success': False,
                'message': f'无法解析主机地址 {ip}: {str(e)}',
                'error_type': 'dns_error'
            }
        except paramiko.AuthenticationException:
            return {
                'success': False,
                'message': 'SSH认证失败：用户名或密码错误',
                'error_type': 'authentication'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'SSH连接测试失败: {str(e)}'
            }
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass
            if test_client:
                try:
                    test_client.close()
                except:
                    pass


# 保持向后兼容
SSHClient = SSHClientEnhanced
