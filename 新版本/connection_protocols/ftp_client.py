import ftplib
import socket
import os
from typing import Optional, Dict, Any, Callable


class FTPClient:
    """FTP连接客户端类"""
    
    def __init__(self):
        self.ftp = None
        self.connected = False
        self.connection_info = {}
    
    def connect(self, ip: str, username: str, password: str, port: int = 21, 
                timeout: int = 30) -> Dict[str, Any]:
        """
        连接到FTP服务器
        
        Args:
            ip: 服务器IP地址
            username: 用户名
            password: 密码
            port: 端口号，默认21
            timeout: 连接超时时间，默认30秒
            
        Returns:
            连接结果字典
        """
        try:
            # 创建FTP连接
            self.ftp = ftplib.FTP()
            
            # 设置超时
            self.ftp.connect(ip, port, timeout)
            
            # 登录
            self.ftp.login(username, password)
            
            # 设置被动模式
            self.ftp.set_pasv(True)
            
            self.connected = True
            self.connection_info = {
                'ip': ip,
                'username': username,
                'port': port,
                'status': 'connected'
            }
            
            return {
                'success': True,
                'message': f'FTP连接成功: {ip}:{port}',
                'connection_info': self.connection_info,
                'welcome_message': self.ftp.getwelcome()
            }
            
        except ftplib.error_perm as e:
            return {
                'success': False,
                'message': f'FTP认证失败: {str(e)}',
                'error_type': 'authentication'
            }
        except ftplib.error_temp as e:
            return {
                'success': False,
                'message': f'FTP临时错误: {str(e)}',
                'error_type': 'temporary_error'
            }
        except ftplib.error_reply as e:
            return {
                'success': False,
                'message': f'FTP回复错误: {str(e)}',
                'error_type': 'reply_error'
            }
        except socket.timeout:
            return {
                'success': False,
                'message': 'FTP连接超时',
                'error_type': 'timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'FTP连接失败: {str(e)}',
                'error_type': 'general'
            }
    
    def list_files(self, directory: str = '.') -> Dict[str, Any]:
        """
        列出目录中的文件
        
        Args:
            directory: 目录路径，默认为当前目录
            
        Returns:
            文件列表字典
        """
        if not self.connected or not self.ftp:
            return {
                'success': False,
                'message': 'FTP未连接，请先建立连接'
            }
        
        try:
            # 切换到指定目录
            original_dir = self.ftp.pwd()
            self.ftp.cwd(directory)
            
            # 获取文件列表
            files = []
            self.ftp.retrlines('LIST', lambda x: files.append(x))
            
            # 返回原目录
            self.ftp.cwd(original_dir)
            
            return {
                'success': True,
                'files': files,
                'directory': directory,
                'count': len(files)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'获取文件列表失败: {str(e)}'
            }
    
    def get_file(self, remote_filename: str, local_filename: str,
                progress_callback: Optional[Callable[[int, int], None]] = None,
                should_cancel: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        下载文件从FTP服务器

        Args:
            remote_filename: 远程文件名
            local_filename: 本地文件名
            progress_callback: 进度回调函数 callback(已传输字节数, 总字节数)
            should_cancel: 取消检查函数 callback() -> bool，返回True表示需要取消

        Returns:
            下载结果字典
        """
        if not self.connected or not self.ftp:
            return {
                'success': False,
                'message': 'FTP未连接，请先建立连接'
            }

        local_file = None
        try:
            # 获取文件大小
            total_size = 0
            try:
                total_size = self.ftp.size(remote_filename)
            except:
                pass

            transferred_size = 0

            def write_callback(data: bytes):
                nonlocal transferred_size
                # 检查是否需要取消
                if should_cancel and should_cancel():
                    print(f"[FTP] 检测到取消请求，中断下载")
                    raise Exception("用户取消传输")

                transferred_size += len(data)
                local_file.write(data)
                if progress_callback and total_size > 0:
                    progress_callback(transferred_size, total_size)

            # 确保本地目录存在
            os.makedirs(os.path.dirname(local_filename), exist_ok=True)

            local_file = open(local_filename, 'wb')
            self.ftp.retrbinary(f'RETR {remote_filename}', write_callback)

            return {
                'success': True,
                'message': f'文件下载成功: {remote_filename} -> {local_filename}'
            }

        except Exception as e:
            if "用户取消传输" in str(e):
                print(f"[FTP] 下载已取消")
                return {
                    'success': False,
                    'message': '传输已取消'
                }
            return {
                'success': False,
                'message': f'文件下载失败: {str(e)}'
            }
        finally:
            if local_file is not None:
                local_file.close()
    
    def put_file(self, local_filename: str, remote_filename: str,
                progress_callback: Optional[Callable[[int, int], None]] = None,
                should_cancel: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        上传文件到FTP服务器

        Args:
            local_filename: 本地文件名
            remote_filename: 远程文件名
            progress_callback: 进度回调函数 callback(已传输字节数, 总字节数)
            should_cancel: 取消检查函数 callback() -> bool，返回True表示需要取消

        Returns:
            上传结果字典
        """
        if not self.connected or not self.ftp:
            return {
                'success': False,
                'message': 'FTP未连接，请先建立连接'
            }

        try:
            # 获取文件大小
            total_size = os.path.getsize(local_filename)
            transferred_size = 0

            def read_callback(data: bytes):
                nonlocal transferred_size
                # 检查是否需要取消
                if should_cancel and should_cancel():
                    print(f"[FTP] 检测到取消请求，中断上传")
                    raise Exception("用户取消传输")

                transferred_size += len(data)
                if progress_callback:
                    progress_callback(transferred_size, total_size)
                return data

            with open(local_filename, 'rb') as local_file:
                self.ftp.storbinary(f'STOR {remote_filename}', local_file, callback=read_callback)

            return {
                'success': True,
                'message': f'文件上传成功: {local_filename} -> {remote_filename}'
            }

        except Exception as e:
            if "用户取消传输" in str(e):
                print(f"[FTP] 上传已取消")
                return {
                    'success': False,
                    'message': '传输已取消'
                }
            return {
                'success': False,
                'message': f'文件上传失败: {str(e)}'
            }

    def upload_directory(self, local_dir: str, remote_dir: str,
                       progress_callback: Optional[Callable[[int, int], None]] = None,
                       should_cancel: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        递归上传本地文件夹到FTP服务器

        Args:
            local_dir: 本地文件夹路径
            remote_dir: 远程文件夹路径
            progress_callback: 进度回调函数 callback(已传输字节数, 总字节数)

        Returns:
            上传结果字典
        """
        if not self.connected or not self.ftp:
            return {
                'success': False,
                'message': 'FTP未连接，请先建立连接'
            }

        try:
            # 计算总大小
            total_size = 0
            file_count = 0
            for root, dirs, files in os.walk(local_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
                        file_count += 1

            print(f"[FTP] 上传目录: {local_dir}, 文件数: {file_count}, 总大小: {total_size} bytes ({total_size / (1024*1024):.2f} MB)")

            transferred_size = 0

            def update_progress(size: int):
                nonlocal transferred_size
                transferred_size += size
                print(f"[FTP] 目录上传进度 - 已传输: {transferred_size}, 本次增量: {size}, 总大小: {total_size}, 进度: {(transferred_size/total_size*100 if total_size > 0 else 0):.2f}%")
                if progress_callback:
                    progress_callback(transferred_size, total_size)

            # 保存当前远程目录
            original_dir = self.ftp.pwd()

            # 确保远程目录存在
            try:
                self.ftp.mkd(remote_dir)
            except:
                pass  # 目录可能已存在

            # 遍历本地文件夹
            for root, dirs, files in os.walk(local_dir):
                # 计算相对路径
                rel_path = os.path.relpath(root, local_dir)
                if rel_path == '.':
                    remote_path = remote_dir
                else:
                    remote_path = remote_dir + '/' + rel_path.replace('\\', '/')

                # 创建远程子目录
                try:
                    self.ftp.cwd(remote_path)
                except:
                    try:
                        # 尝试逐级创建目录
                        parts = remote_path.split('/')
                        current_path = ''
                        for part in parts:
                            if part:
                                current_path += '/' + part
                                try:
                                    self.ftp.cwd(current_path)
                                except:
                                    self.ftp.mkd(current_path)
                                    self.ftp.cwd(current_path)
                    except:
                        pass

                # 上传文件
                for file in files:
                    local_file = os.path.join(root, file)
                    file_size = os.path.getsize(local_file)

                    # 使用列表来跟踪每个文件的上传进度
                    transferred_for_file = [0]

                    def read_callback(data: bytes):
                        delta = len(data)
                        transferred_for_file[0] += delta
                        if delta > 0:
                            update_progress(delta)
                        return data

                    with open(local_file, 'rb') as f:
                        self.ftp.storbinary(f'STOR {file}', f, callback=read_callback)

            # 返回原目录
            self.ftp.cwd(original_dir)

            return {
                'success': True,
                'message': f'文件夹上传成功: {local_dir} -> {remote_dir}'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'文件夹上传失败: {str(e)}'
            }

    def download_directory(self, remote_dir: str, local_dir: str,
                         progress_callback: Optional[Callable[[int, int], None]] = None,
                         should_cancel: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        递归下载远程文件夹到本地

        Args:
            remote_dir: 远程文件夹路径
            local_dir: 本地文件夹路径
            progress_callback: 进度回调函数 callback(已传输字节数, 总字节数)

        Returns:
            下载结果字典
        """
        if not self.connected or not self.ftp:
            return {
                'success': False,
                'message': 'FTP未连接，请先建立连接'
            }

        try:
            # 计算总大小
            total_size = self._calculate_directory_size(remote_dir)
            transferred_size = 0
            print(f"[FTP] 下载目录: {remote_dir}, 总大小: {total_size} bytes ({total_size / (1024*1024):.2f} MB)")

            def update_progress(size: int):
                nonlocal transferred_size
                transferred_size += size
                print(f"[FTP] 目录下载进度 - 已传输: {transferred_size}, 本次增量: {size}, 总大小: {total_size}, 进度: {(transferred_size/total_size*100 if total_size > 0 else 0):.2f}%")
                if progress_callback:
                    progress_callback(transferred_size, total_size)

            # 确保本地目录存在
            os.makedirs(local_dir, exist_ok=True)

            # 保存当前远程目录
            original_dir = self.ftp.pwd()

            # 切换到远程目录
            self.ftp.cwd(remote_dir)

            # 递归下载
            self._recursive_download(remote_dir, local_dir, update_progress)

            # 返回原目录
            self.ftp.cwd(original_dir)

            return {
                'success': True,
                'message': f'文件夹下载成功: {remote_dir} -> {local_dir}'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'文件夹下载失败: {str(e)}'
            }

    def _calculate_directory_size(self, remote_path: str) -> int:
        """
        计算远程目录的总大小

        Args:
            remote_path: 远程路径

        Returns:
            总大小（字节）
        """
        total_size = 0
        try:
            # 先切换到目标目录
            original_dir = self.ftp.pwd()
            self.ftp.cwd(remote_path)

            files = []
            dirs = []
            self.ftp.retrlines('LIST', lambda line: self._parse_ftp_list(line, files, dirs))

            print(f"[FTP] 计算目录大小: {remote_path}, 文件数: {len(files)}, 目录数: {len(dirs)}")

            for file_name in files:
                try:
                    file_size = self.ftp.size(file_name)
                    # 检查文件大小是否为负数（32位整数溢出）
                    if file_size < 0:
                        print(f"[FTP] 警告: 文件大小为负数，可能是32位溢出: {file_name}, size={file_size}")
                        # 尝试转换为无符号32位整数
                        file_size = file_size & 0xFFFFFFFF
                        print(f"[FTP] 修正后大小: {file_size} bytes ({file_size/(1024*1024):.2f} MB)")
                    total_size += file_size
                    print(f"[FTP] 文件: {file_name}, 大小: {file_size} bytes ({file_size/(1024*1024):.2f} MB), 类型: {type(file_size)}")
                except Exception as e:
                    print(f"[FTP] 获取文件大小失败: {file_name}, 错误: {e}")

            for dir_name in dirs:
                if dir_name not in ['.', '..']:
                    # 递归计算子目录大小
                    try:
                        total_size += self._calculate_directory_size(f"{remote_path}/{dir_name}")
                    except Exception as e:
                        print(f"[FTP] 计算子目录大小失败: {dir_name}, 错误: {e}")

            # 切换回原来的目录
            self.ftp.cwd(original_dir)
        except Exception as e:
            print(f"[FTP] 计算目录大小异常: {remote_path}, 错误: {e}")
            import traceback
            traceback.print_exc()
        print(f"[FTP] 目录总大小: {remote_path} = {total_size} bytes ({total_size/(1024*1024):.2f} MB)")
        return total_size

    def _recursive_download(self, remote_path: str, local_path: str,
                           progress_callback: Optional[Callable[[int], None]] = None):
        """
        递归下载辅助函数

        Args:
            remote_path: 远程路径
            local_path: 本地路径
            progress_callback: 进度回调函数 callback(文件大小)
        """
        # 获取远程目录内容
        files = []
        dirs = []
        try:
            self.ftp.retrlines('LIST', lambda line: self._parse_ftp_list(line, files, dirs))
        except:
            return

        # 下载文件
        for file_name in files:
            remote_file = f"{remote_path}/{file_name}"
            local_file = os.path.join(local_path, file_name)
            try:
                file_size = 0
                try:
                    file_size = self.ftp.size(f"{remote_path}/{file_name}")
                except:
                    pass

                # 使用列表来跟踪每个文件的下载进度
                transferred_size = [0]

                def write_callback(data: bytes):
                    transferred_size[0] += len(data)
                    f.write(data)
                    if progress_callback and len(data) > 0:
                        progress_callback(len(data))

                with open(local_file, 'wb') as f:
                    self.ftp.retrbinary(f'RETR {file_name}', write_callback)
            except:
                pass

        # 递归处理子目录
        for dir_name in dirs:
            if dir_name not in ['.', '..']:
                remote_subdir = f"{remote_path}/{dir_name}"
                local_subdir = os.path.join(local_path, dir_name)
                os.makedirs(local_subdir, exist_ok=True)

                # 切换到子目录并递归下载
                self.ftp.cwd(dir_name)
                self._recursive_download(remote_subdir, local_subdir)
                # 返回父目录
                self.ftp.cwd('..')
    
    def delete_file(self, remote_filename: str) -> Dict[str, Any]:
        """
        删除FTP服务器上的文件
        
        Args:
            remote_filename: 远程文件名
            
        Returns:
            删除结果字典
        """
        if not self.connected or not self.ftp:
            return {
                'success': False,
                'message': 'FTP未连接，请先建立连接'
            }
        
        try:
            self.ftp.delete(remote_filename)
            
            return {
                'success': True,
                'message': f'文件删除成功: {remote_filename}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'文件删除失败: {str(e)}'
            }
    
    def create_directory(self, directory_name: str) -> Dict[str, Any]:
        """
        在FTP服务器上创建目录
        
        Args:
            directory_name: 目录名
            
        Returns:
            创建结果字典
        """
        if not self.connected or not self.ftp:
            return {
                'success': False,
                'message': 'FTP未连接，请先建立连接'
            }
        
        try:
            self.ftp.mkd(directory_name)
            
            return {
                'success': True,
                'message': f'目录创建成功: {directory_name}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'目录创建失败: {str(e)}'
            }
    
    def change_directory(self, directory: str) -> Dict[str, Any]:
        """
        切换FTP服务器目录
        
        Args:
            directory: 目录路径
            
        Returns:
            切换结果字典
        """
        if not self.connected or not self.ftp:
            return {
                'success': False,
                'message': 'FTP未连接，请先建立连接'
            }
        
        try:
            self.ftp.cwd(directory)
            current_dir = self.ftp.pwd()
            
            return {
                'success': True,
                'message': f'目录切换成功: {current_dir}',
                'current_directory': current_dir
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'目录切换失败: {str(e)}'
            }
    
    def get_current_directory(self) -> Dict[str, Any]:
        """
        获取当前工作目录
        
        Returns:
            当前目录字典
        """
        if not self.connected or not self.ftp:
            return {
                'success': False,
                'message': 'FTP未连接，请先建立连接'
            }
        
        try:
            current_dir = self.ftp.pwd()
            
            return {
                'success': True,
                'current_directory': current_dir
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'获取当前目录失败: {str(e)}'
            }
    
    def get_file_size(self, remote_filename: str) -> Dict[str, Any]:
        """
        获取远程文件大小
        
        Args:
            remote_filename: 远程文件名
            
        Returns:
            文件大小字典
        """
        if not self.connected or not self.ftp:
            return {
                'success': False,
                'message': 'FTP未连接，请先建立连接'
            }
        
        try:
            size = self.ftp.size(remote_filename)
            
            return {
                'success': True,
                'filename': remote_filename,
                'size': size,
                'size_human': f'{size} bytes'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'获取文件大小失败: {str(e)}'
            }
    
    def disconnect(self) -> Dict[str, Any]:
        """
        断开FTP连接
        
        Returns:
            断开连接结果字典
        """
        try:
            if self.ftp:
                self.ftp.quit()
                self.ftp = None
            
            self.connected = False
            self.connection_info = {}
            
            return {
                'success': True,
                'message': 'FTP连接已断开'
            }
            
        except Exception as e:
            try:
                if self.ftp:
                    self.ftp.close()
            except:
                pass
            
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
                       port: int = 21, timeout: int = 10) -> Dict[str, Any]:
        """
        测试FTP连接
        
        Args:
            ip: 服务器IP地址
            username: 用户名
            password: 密码
            port: 端口号，默认21
            timeout: 连接超时时间，默认10秒
            
        Returns:
            测试结果字典
        """
        test_ftp = None
        try:
            test_ftp = ftplib.FTP()
            test_ftp.connect(ip, port, timeout)
            test_ftp.login(username, password)
            
            return {
                'success': True,
                'message': f'FTP连接测试成功: {ip}:{port}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'FTP连接测试失败: {str(e)}'
            }
        finally:
            if test_ftp:
                try:
                    test_ftp.quit()
                except:
                    test_ftp.close()

    def create_file(self, remote_filename: str) -> Dict[str, Any]:
        """
        在FTP服务器上创建文件

        Args:
            remote_filename: 远程文件名

        Returns:
            创建结果字典
        """
        if not self.connected or not self.ftp:
            return {
                'success': False,
                'message': 'FTP未连接，请先建立连接'
            }

        try:
            # 创建空文件（使用临时文件方式）
            import io
            empty_file = io.BytesIO(b'')
            self.ftp.storbinary(f'STOR {remote_filename}', empty_file)

            return {
                'success': True,
                'message': f'文件创建成功: {remote_filename}'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'文件创建失败: {str(e)}'
            }

    def delete_directory(self, directory_name: str) -> Dict[str, Any]:
        """
        删除FTP服务器上的目录（递归删除所有内容）
        
        Args:
            directory_name: 目录名
            
        Returns:
            删除结果字典
        """
        if not self.connected or not self.ftp:
            return {
                'success': False,
                'message': 'FTP未连接，请先建立连接'
            }
        
        try:
            # 保存当前目录
            original_dir = self.ftp.pwd()
            
            # 切换到目标目录
            self.ftp.cwd(directory_name)
            
            # 获取目录内容
            files = []
            dirs = []
            self.ftp.retrlines('LIST', lambda line: self._parse_ftp_list(line, files, dirs))
            
            # 递归删除所有子目录
            for dir_name in dirs:
                if dir_name not in ['.', '..']:
                    subdir_result = self.delete_directory(dir_name)
                    if not subdir_result['success']:
                        return subdir_result
            
            # 删除所有文件
            for file_name in files:
                file_result = self.delete_file(file_name)
                if not file_result['success']:
                    return file_result
            
            # 返回上级目录
            self.ftp.cwd(original_dir)
            
            # 删除空目录
            self.ftp.rmd(directory_name)
            
            return {
                'success': True,
                'message': f'目录删除成功: {directory_name}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'目录删除失败: {str(e)}'
            }
    
    def _parse_ftp_list(self, line: str, files: list, dirs: list):
        """
        解析FTP LIST命令的输出
        
        Args:
            line: LIST命令的一行输出
            files: 文件列表
            dirs: 目录列表
        """
        if not line:
            return
            
        # 解析FTP LIST格式 (类似 "drwxr-xr-x 2 user group 4096 Jan 1 00:00 dirname")
        parts = line.split()
        if len(parts) < 9:
            return
            
        # 检查是否是目录（以d开头）
        is_dir = parts[0].startswith('d')
        name = parts[-1]
        
        if is_dir:
            dirs.append(name)
        else:
            files.append(name)