import paramiko
import socket
import os
from typing import Optional, Dict, Any, Callable


class SFTPClient:
    """SFTP连接客户端类"""
    
    def __init__(self):
        self.client = None
        self.sftp = None
        self.connected = False
        self.connection_info = {}
    
    def connect(self, ip: str, username: str, password: str, port: int = 22, 
                timeout: int = 30) -> Dict[str, Any]:
        """
        连接到SFTP服务器
        
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
            self.sftp = self.client.open_sftp()
            
            self.connected = True
            self.connection_info = {
                'ip': ip,
                'username': username,
                'port': port,
                'status': 'connected'
            }
            
            return {
                'success': True,
                'message': f'SFTP连接成功: {ip}:{port}',
                'connection_info': self.connection_info
            }
            
        except paramiko.AuthenticationException:
            return {
                'success': False,
                'message': 'SFTP认证失败：用户名或密码错误',
                'error_type': 'authentication'
            }
        except paramiko.SSHException as e:
            return {
                'success': False,
                'message': f'SFTP连接异常: {str(e)}',
                'error_type': 'ssh_exception'
            }
        except socket.timeout:
            return {
                'success': False,
                'message': 'SFTP连接超时',
                'error_type': 'timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'SFTP连接失败: {str(e)}',
                'error_type': 'general'
            }
    
    def list_directory(self, remote_path: str = '.') -> Dict[str, Any]:
        """
        列出远程目录内容
        
        Args:
            remote_path: 远程目录路径，默认为当前目录
            
        Returns:
            目录内容字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
            }
        
        try:
            files = self.sftp.listdir(remote_path)
            print(f"[SFTP] listdir('{remote_path}') 原始返回: {files}")
            
            # 获取详细文件信息
            file_details = []
            for filename in files:
                print(f"[SFTP] 处理文件: '{filename}'")
                # 构建完整路径（使用原始文件名）
                full_path = remote_path + '/' + filename if remote_path != '.' else filename
                
                try:
                    stat = self.sftp.stat(full_path)
                    file_details.append({
                        'name': filename,  # 保留原始文件名（包含反斜杠）
                        'display_name': filename.replace('\\', '/'),  # 用于显示的友好名称
                        'size': stat.st_size,
                        'mode': stat.st_mode,
                        'is_directory': bool(stat.st_mode & 0o40000),
                        'modified_time': stat.st_mtime
                    })
                except:
                    file_details.append({
                        'name': filename,
                        'display_name': filename.replace('\\', '/'),
                        'size': 0,
                        'mode': 0,
                        'is_directory': False,
                        'modified_time': 0
                    })
            
            return {
                'success': True,
                'files': file_details,
                'directory': remote_path,
                'count': len(files)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'获取目录列表失败: {str(e)}'
            }
    
    def upload_file(self, local_path: str, remote_path: str,
                    progress_callback: Optional[Callable[[int, int], None]] = None,
                    should_cancel: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        上传文件到远程服务器

        Args:
            local_path: 本地文件路径
            remote_path: 远程文件路径
            progress_callback: 进度回调函数 callback(已传输字节数, 总字节数)
            should_cancel: 取消检查函数 callback() -> bool，返回True表示需要取消

        Returns:
            上传结果字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
            }

        try:
            # 获取文件大小
            try:
                total_size = os.path.getsize(local_path)
                print(f"[SFTP] 上传文件: {local_path}, 总大小: {total_size} bytes ({total_size / (1024*1024):.2f} MB)")
            except Exception as e:
                total_size = 0
                print(f"[SFTP] 获取文件大小失败: {e}")

            # 用于跟踪是否需要取消
            cancelled = False

            def callback(transferred: int, total: int):
                nonlocal cancelled
                # 检查是否需要取消
                if should_cancel and should_cancel():
                    cancelled = True
                    print(f"[SFTP] 检测到取消请求，中断传输")
                    raise Exception("用户取消传输")

                if progress_callback:
                    # 使用我们获取的total_size，而不是paramiko传入的total
                    print(f"[SFTP] 回调 - transferred: {transferred}, total_param: {total}, total_size: {total_size}")
                    progress_callback(transferred, total_size)

            self.sftp.put(local_path, remote_path, callback=callback)

            if cancelled:
                return {
                    'success': False,
                    'message': '传输已取消'
                }

            return {
                'success': True,
                'message': f'文件上传成功: {local_path} -> {remote_path}'
            }

        except Exception as e:
            if "用户取消传输" in str(e):
                print(f"[SFTP] 上传已取消")
                return {
                    'success': False,
                    'message': '传输已取消'
                }
            print(f"[SFTP] 上传文件异常: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'文件上传失败: {str(e)}'
            }

    def upload_directory(self, local_dir: str, remote_dir: str,
                        progress_callback: Optional[Callable[[int, int], None]] = None,
                        should_cancel: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        递归上传本地文件夹到远程服务器

        Args:
            local_dir: 本地文件夹路径
            remote_dir: 远程文件夹路径
            progress_callback: 进度回调函数 callback(已传输字节数, 总字节数)
            should_cancel: 取消检查函数 callback() -> bool，返回True表示需要取消

        Returns:
            上传结果字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
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

            print(f"[SFTP] 上传目录: {local_dir}, 文件数: {file_count}, 总大小: {total_size} bytes ({total_size / (1024*1024):.2f} MB)")

            transferred_size = 0

            def update_progress(size: int):
                nonlocal transferred_size
                transferred_size += size
                print(f"[SFTP] 目录上传进度 - 已传输: {transferred_size}, 本次增量: {size}, 总大小: {total_size}, 进度: {(transferred_size/total_size*100 if total_size > 0 else 0):.2f}%")
                if progress_callback:
                    progress_callback(transferred_size, total_size)

            # 确保远程目录存在
            try:
                self.sftp.mkdir(remote_dir)
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
                    self.sftp.mkdir(remote_path)
                except:
                    pass  # 目录可能已存在

                # 上传文件
                for file in files:
                    local_file = os.path.join(root, file)
                    remote_file = remote_path + '/' + file
                    file_size = os.path.getsize(local_file)

                    # 上传文件（SFTP是同步操作）
                    # 使用一个标志来跟踪该文件是否已经完成上传
                    file_done = {'transferred': 0, 'finished': False, 'last_callback_time': 0}

                    def file_callback(transferred: int, total: int):
                        import time
                        current_time = time.time()

                        # 防止在文件完成后还有回调
                        if not file_done['finished']:
                            # 只在transferred增加时才更新
                            if transferred > file_done['transferred']:
                                delta = transferred - file_done['transferred']
                                file_done['transferred'] = transferred

                                # 防止过于频繁的回调（至少间隔10ms）
                                if delta > 0 and progress_callback:
                                    progress_callback(delta)
                                    file_done['last_callback_time'] = current_time

                            # 如果传输完成，标记文件已完成
                            if transferred >= file_size and not file_done['finished']:
                                file_done['finished'] = True

                    self.sftp.put(local_file, remote_file, callback=file_callback)

            return {
                'success': True,
                'message': f'文件夹上传成功: {local_dir} -> {remote_dir}'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'文件夹上传失败: {str(e)}'
            }

    def download_file(self, remote_path: str, local_path: str,
                     progress_callback: Optional[Callable[[int, int], None]] = None,
                     should_cancel: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        从远程服务器下载文件

        Args:
            remote_path: 远程文件路径
            local_path: 本地文件路径
            progress_callback: 进度回调函数 callback(已传输字节数, 总字节数)
            should_cancel: 取消检查函数 callback() -> bool，返回True表示需要取消

        Returns:
            下载结果字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
            }

        try:
            # 确保本地目录存在
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # 获取文件大小
            try:
                total_size = self.sftp.stat(remote_path).st_size
                print(f"[SFTP] 下载文件: {remote_path}, 总大小: {total_size} bytes ({total_size / (1024*1024):.2f} MB)")
            except Exception as e:
                total_size = 0
                print(f"[SFTP] 获取文件大小失败: {e}")

            # 用于跟踪是否需要取消
            cancelled = False

            def callback(transferred: int, total: int):
                nonlocal cancelled
                # 检查是否需要取消
                if should_cancel and should_cancel():
                    cancelled = True
                    print(f"[SFTP] 检测到取消请求，中断传输")
                    raise Exception("用户取消传输")

                if progress_callback:
                    # 使用我们获取的total_size，而不是paramiko传入的total
                    print(f"[SFTP] 回调 - transferred: {transferred}, total_param: {total}, total_size: {total_size}")
                    progress_callback(transferred, total_size)

            self.sftp.get(remote_path, local_path, callback=callback)

            if cancelled:
                return {
                    'success': False,
                    'message': '传输已取消'
                }

            return {
                'success': True,
                'message': f'文件下载成功: {remote_path} -> {local_path}'
            }

        except Exception as e:
            if "用户取消传输" in str(e):
                print(f"[SFTP] 下载已取消")
                return {
                    'success': False,
                    'message': '传输已取消'
                }
            print(f"[SFTP] 下载文件异常: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'文件下载失败: {str(e)}'
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
            should_cancel: 取消检查函数 callback() -> bool，返回True表示需要取消

        Returns:
            下载结果字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
            }

        try:
            import os

            # 计算总大小
            total_size = self._calculate_directory_size(remote_dir)
            transferred_size = 0
            print(f"[SFTP] 下载目录: {remote_dir}, 总大小: {total_size} bytes ({total_size / (1024*1024):.2f} MB)")

            def update_progress(size: int):
                nonlocal transferred_size
                transferred_size += size
                progress_pct = (transferred_size/total_size*100 if total_size > 0 else 0)
                print(f"[SFTP] 目录下载进度 - 已传输: {transferred_size}, 本次增量: {size}, 总大小: {total_size}, 进度: {progress_pct:.2f}%")
                if progress_callback:
                    # 注意：这里的progress_callback期望接收 (transferred, total) 两个参数
                    progress_callback(transferred_size, total_size)

            # 确保本地目录存在
            os.makedirs(local_dir, exist_ok=True)

            # 递归下载
            self._recursive_download(remote_dir, local_dir, update_progress)

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
            items = self.sftp.listdir_attr(remote_path)
            print(f"[SFTP] 计算目录大小: {remote_path}, 项目数: {len(items)}")

            for item in items:
                item_name = item.filename
                remote_item_path = f"{remote_path}/{item_name}"

                if item.st_mode & 0o40000:  # 是目录
                    sub_size = self._calculate_directory_size(remote_item_path)
                    total_size += sub_size
                    print(f"[SFTP] 子目录: {item_name}, 大小: {sub_size} bytes ({sub_size/(1024*1024):.2f} MB)")
                else:  # 是文件
                    file_size = item.st_size
                    # 检查文件大小是否为负数（32位整数溢出）
                    if file_size < 0:
                        print(f"[SFTP] 警告: 文件大小为负数，可能是32位溢出: {item_name}, st_size={file_size}")
                        # 尝试转换为无符号32位整数
                        file_size = file_size & 0xFFFFFFFF
                        print(f"[SFTP] 修正后大小: {file_size} bytes ({file_size/(1024*1024):.2f} MB)")
                    total_size += file_size
                    print(f"[SFTP] 文件: {item_name}, 大小: {file_size} bytes ({file_size/(1024*1024):.2f} MB), 类型: {type(file_size)}")
        except Exception as e:
            print(f"[SFTP] 计算目录大小异常: {remote_path}, 错误: {e}")
            import traceback
            traceback.print_exc()
        print(f"[SFTP] 目录总大小: {remote_path} = {total_size} bytes ({total_size/(1024*1024):.2f} MB)")
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
        for item in self.sftp.listdir_attr(remote_path):
            item_name = item.filename
            remote_item_path = f"{remote_path}/{item_name}"
            local_item_path = os.path.join(local_path, item_name)

            if item.st_mode & 0o40000:  # 是目录
                # 创建本地目录
                os.makedirs(local_item_path, exist_ok=True)
                # 递归下载子目录
                self._recursive_download(remote_item_path, local_item_path, progress_callback)
            else:  # 是文件
                # 下载文件
                file_size = item.st_size

                # 使用字典来跟踪该文件是否已经完成下载
                file_done = {'transferred': 0, 'finished': False, 'last_callback_time': 0}

                def file_callback(transferred: int, total: int):
                    import time
                    current_time = time.time()

                    # 防止在文件完成后还有回调
                    if not file_done['finished']:
                        # 只在transferred增加时才更新
                        if transferred > file_done['transferred']:
                            delta = transferred - file_done['transferred']
                            file_done['transferred'] = transferred

                            # 防止过于频繁的回调（至少间隔10ms）
                            if delta > 0 and progress_callback:
                                progress_callback(delta)
                                file_done['last_callback_time'] = current_time

                        # 如果传输完成，标记文件已完成
                        if transferred >= file_size and not file_done['finished']:
                            file_done['finished'] = True

                self.sftp.get(remote_item_path, local_item_path, callback=file_callback)
    
    def delete_file(self, remote_path: str) -> Dict[str, Any]:
        """
        删除远程文件
        
        Args:
            remote_path: 远程文件路径
            
        Returns:
            删除结果字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
            }
        
        try:
            self.sftp.remove(remote_path)
            
            return {
                'success': True,
                'message': f'文件删除成功: {remote_path}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'文件删除失败: {str(e)}'
            }
    
    def create_directory(self, remote_path: str) -> Dict[str, Any]:
        """
        创建远程目录
        
        Args:
            remote_path: 远程目录路径
            
        Returns:
            创建结果字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
            }
        
        try:
            self.sftp.mkdir(remote_path)
            
            return {
                'success': True,
                'message': f'目录创建成功: {remote_path}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'目录创建失败: {str(e)}'
            }
    
    def delete_directory(self, remote_path: str) -> Dict[str, Any]:
        """
        删除远程目录（递归删除所有内容）
        
        Args:
            remote_path: 远程目录路径
            
        Returns:
            删除结果字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
            }
        
        try:
            # 递归删除目录及其所有内容
            self._recursive_delete(remote_path)
            
            return {
                'success': True,
                'message': f'目录删除成功: {remote_path}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'目录删除失败: {str(e)}'
            }
    
    def _recursive_delete(self, remote_path: str):
        """
        递归删除目录及其所有内容
        
        Args:
            remote_path: 远程目录路径
        """
        # 获取目录中的所有文件和子目录
        for item in self.sftp.listdir_attr(remote_path):
            item_path = f"{remote_path}/{item.filename}"
            
            if item.st_mode & 0o40000:  # 检查是否是目录
                # 递归删除子目录
                self._recursive_delete(item_path)
            else:
                # 删除文件
                self.sftp.remove(item_path)
        
        # 删除空目录
        self.sftp.rmdir(remote_path)
    
    def change_directory(self, remote_path: str) -> Dict[str, Any]:
        """
        切换远程目录
        
        Args:
            remote_path: 远程目录路径
            
        Returns:
            切换结果字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
            }
        
        try:
            self.sftp.chdir(remote_path)
            current_dir = self.sftp.getcwd()
            
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
    
    def path_exists(self, remote_path: str) -> bool:
        """
        检查远程路径是否存在
        
        Args:
            remote_path: 远程路径
            
        Returns:
            True if exists, False otherwise
        """
        if not self.connected or not self.sftp:
            return False
        
        try:
            self.sftp.stat(remote_path)
            return True
        except:
            return False
    
    def get_current_directory(self) -> Dict[str, Any]:
        """
        获取当前工作目录
        
        Returns:
            当前目录字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
            }
        
        try:
            current_dir = self.sftp.getcwd()
            
            return {
                'success': True,
                'current_directory': current_dir
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'获取当前目录失败: {str(e)}'
            }
    
    def get_file_info(self, remote_path: str) -> Dict[str, Any]:
        """
        获取文件信息
        
        Args:
            remote_path: 远程文件路径
            
        Returns:
            文件信息字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
            }
        
        try:
            stat = self.sftp.stat(remote_path)
            
            return {
                'success': True,
                'filename': remote_path,
                'size': stat.st_size,
                'mode': stat.st_mode,
                'uid': stat.st_uid,
                'gid': stat.st_gid,
                'modified_time': stat.st_mtime,
                'access_time': stat.st_atime,
                'is_directory': bool(stat.st_mode & 0o40000),
                'is_file': bool(stat.st_mode & 0o100000)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'获取文件信息失败: {str(e)}'
            }
    
    def rename_file(self, old_path: str, new_path: str) -> Dict[str, Any]:
        """
        重命名文件或目录
        
        Args:
            old_path: 原路径
            new_path: 新路径
            
        Returns:
            重命名结果字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
            }
        
        try:
            self.sftp.rename(old_path, new_path)
            
            return {
                'success': True,
                'message': f'重命名成功: {old_path} -> {new_path}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'重命名失败: {str(e)}'
            }
    
    def disconnect(self) -> Dict[str, Any]:
        """
        断开SFTP连接
        
        Returns:
            断开连接结果字典
        """
        try:
            if self.sftp:
                self.sftp.close()
                self.sftp = None
            
            if self.client:
                self.client.close()
                self.client = None
            
            self.connected = False
            self.connection_info = {}
            
            return {
                'success': True,
                'message': 'SFTP连接已断开'
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
        测试SFTP连接
        
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
        test_sftp = None
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
            
            test_sftp = test_client.open_sftp()
            
            return {
                'success': True,
                'message': f'SFTP连接测试成功: {ip}:{port}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'SFTP连接测试失败: {str(e)}'
            }
        finally:
            if test_sftp:
                test_sftp.close()
            if test_client:
                test_client.close()

    def create_file(self, remote_path: str) -> Dict[str, Any]:
        """
        创建远程文件
        
        Args:
            remote_path: 远程文件路径
            
        Returns:
            创建结果字典
        """
        if not self.connected or not self.sftp:
            return {
                'success': False,
                'message': 'SFTP未连接，请先建立连接'
            }
        
        try:
            # 使用open方法创建空文件
            with self.sftp.file(remote_path, 'w') as f:
                pass
            
            return {
                'success': True,
                'message': f'文件创建成功: {remote_path}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'文件创建失败: {str(e)}'
            }