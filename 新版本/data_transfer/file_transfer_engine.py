"""
文件传输引擎
实现SFTP/FTP协议的大文件传输和文件夹传输功能
支持断点续传、多线程并发传输
"""

import os
import threading
import queue
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import paramiko
import ftplib
from datetime import datetime
import json
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal


class TransferStatus(Enum):
    """传输状态枚举"""
    PENDING = "等待中"
    RUNNING = "传输中"
    PAUSED = "已暂停"
    COMPLETED = "已完成"
    FAILED = "失败"
    CANCELLED = "已取消"


class TransferTask:
    """传输任务类"""
    
    def __init__(self, task_id, local_path, remote_path, device_config, task_type="upload"):
        self.task_id = task_id
        self.local_path = local_path
        self.remote_path = remote_path
        self.device_config = device_config
        self.task_type = task_type  # "upload" 或 "download"
        self.status = TransferStatus.PENDING
        self.progress = 0.0  # 0-100
        self.total_size = 0
        self.transferred_size = 0
        self.start_time = None
        self.end_time = None
        self.transmission_start_time = None  # 传输开始时间（不包括MD5计算）
        self.transmission_end_time = None    # 传输结束时间（不包括MD5计算）
        self.error_message = ""
        self.current_file = ""
        self.is_directory = False
        self.file_count = 0
        self.completed_files = 0
        self.local_md5 = ""  # 当前文件本地MD5
        self.remote_md5 = ""  # 当前文件远程MD5
        self.md5_check_status = ""  # MD5校验状态：空/校验中/校验成功/校验失败
        self.md5_start_time = None  # MD5计算开始时间
        self.md5_elapsed_time = 0.0  # MD5计算耗时（秒）
        self.md5_history = []  # MD5历史记录列表，每个元素包含 {filename, local_md5, remote_md5, status}
        self.folder_local_md5 = ""  # 文件夹整体本地MD5（所有文件MD5合并计算）
        self.folder_remote_md5 = ""  # 文件夹整体远程MD5
    
    def start(self):
        """开始传输"""
        self.status = TransferStatus.RUNNING
        self.start_time = datetime.now()
    
    def update_progress(self, transferred, total):
        """更新进度"""
        self.transferred_size = transferred
        self.total_size = total
        if total > 0:
            # 计算进度，但不超过100%
            progress = (transferred / total) * 100
            self.progress = min(progress, 100.0)
    
    def complete(self):
        """完成传输"""
        self.status = TransferStatus.COMPLETED
        self.progress = 100.0
        self.end_time = datetime.now()
    
    def fail(self, error_message):
        """传输失败"""
        self.status = TransferStatus.FAILED
        self.error_message = error_message
        self.end_time = datetime.now()
    
    def pause(self):
        """暂停传输"""
        self.status = TransferStatus.PAUSED
    
    def resume(self):
        """继续传输"""
        self.status = TransferStatus.RUNNING
    
    def cancel(self):
        """取消传输"""
        self.status = TransferStatus.CANCELLED
        self.end_time = datetime.now()


class FileTransferEngine(QObject):
    """文件传输引擎"""
    
    # 定义刷新信号
    refresh_signal = pyqtSignal()
    
    def __init__(self, max_workers=3, chunk_size=8192 * 1024):  # 8MB chunks
        super().__init__()
        self.task_queue = queue.Queue()
        self.tasks = {}  # task_id -> TransferTask
        self.running = False
        self.paused = False
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.Lock()
        self.task_counter = 0
        self.chunk_size = chunk_size
        self.connected_devices = {}  # device_id -> connection object
        self.refresh_callback = None  # 刷新回调函数
        self.log_dir = "log/传输日志"  # 日志目录
        self._init_log_directory()  # 初始化日志目录
    
    def _trigger_progress_refresh(self):
        """触发进度表刷新"""
        if self.refresh_callback:
            self.refresh_callback()
        elif hasattr(self, 'refresh_signal'):
            self.refresh_signal.emit()
    
    def _init_log_directory(self):
        """初始化日志目录"""
        try:
            # 确保日志目录存在
            Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[ERROR] 初始化日志目录失败: {str(e)}")
    
    def _log_transfer_start(self, task):
        """记录传输开始"""
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        log_data = {
            "task_id": task.task_id,
            "device_id": task.device_config.get('id', 'unknown'),
            "device_name": task.device_config.get('name', 'unknown'),
            "start_time": timestamp,
            "file": os.path.basename(task.local_path if task.task_type == "upload" else task.remote_path),
            "size": task.total_size
        }
        
        # 确保日志目录存在
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        
        # 写入日志
        log_filename = f"{timestamp}_{task.task_id}_start.log"
        with open(Path(self.log_dir) / log_filename, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
            
        print(f"[日志] 记录传输开始: {log_filename}")
    
    def _log_transfer_complete(self, task, success, error=None):
        """记录传输完成"""
        # 设置传输结束时间
        task.end_time = datetime.now()
        task.transmission_end_time = task.end_time  # 设置传输结束时间
        
        timestamp = task.end_time.strftime("%Y-%m-%d-%H-%M-%S")
        log_data = {
            "task_id": task.task_id,
            "success": success,
            "end_time": timestamp,
            "md5_local": task.local_md5,
            "md5_remote": task.remote_md5,
            "md5_status": task.md5_check_status,
            "error": error
        }
        
        # 确保日志目录存在
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        
        # 写入日志
        log_filename = f"{timestamp}_{task.task_id}_complete.log"
        with open(Path(self.log_dir) / log_filename, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
            
        print(f"[日志] 记录传输完成: {log_filename}")
    
    def connect_device(self, device_id, device_config):
        """连接设备"""
        try:
            # 兼容新旧配置格式：优先使用protocol_configs，如果没有则使用protocols
            protocol_configs = device_config.get('protocol_configs', device_config.get('protocols', []))
            if not protocol_configs:
                print(f"[ERROR] 设备 {device_id} 没有协议配置")
                return False
            
            # 过滤出FTP/SFTP协议配置
            ftp_sftp_configs = [pc for pc in protocol_configs if pc.get('protocol', '').lower() in ('ftp', 'sftp')]
            if not ftp_sftp_configs:
                print(f"[ERROR] 设备 {device_id} 没有FTP/SFTP协议配置")
                return False
            
            # 使用第一个FTP/SFTP协议配置进行连接
            first_config = ftp_sftp_configs[0]
            protocol = first_config.get('protocol', '').upper()
            
            print(f"[INFO] 连接设备 {device_id}, 使用协议: {protocol}")
            
            if protocol == 'SFTP':
                connection = self._connect_sftp(first_config)
            elif protocol == 'FTP':
                connection = self._connect_ftp(first_config)
            else:
                raise ValueError(f"不支持的协议: {protocol}")
            
            # 保存完整的设备配置和连接信息
            with self.lock:
                self.connected_devices[device_id] = {
                    'connection': connection,
                    'config': first_config,  # 保存实际使用的协议配置
                    'device_config': device_config  # 保存完整设备配置
                }
            
            print(f"[DEBUG] 设备 {device_id} 连接成功")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] 连接设备 {device_id} 失败: {error_msg}")
            
            # 提供详细的错误诊断信息
            if "WinError 10060" in error_msg or "timed out" in error_msg.lower():
                print(f"[诊断] 连接超时，可能的原因：")
                print(f"  1. 服务器 {first_config.get('host', first_config.get('ip', ''))}:{first_config.get('port', 22)} 未响应")
                print(f"  2. 网络连接不稳定或防火墙阻止了连接")
                print(f"  3. 服务器负载过高或SSH服务未运行")
                print(f"  建议：检查服务器地址、端口、网络连接和SSH服务状态")
            elif "WinError 10061" in error_msg:
                print(f"[诊断] 连接被拒绝，可能的原因：")
                print(f"  1. 服务器 {first_config.get('host', first_config.get('ip', ''))}:{first_config.get('port', 22)} 没有运行SSH服务")
                print(f"  2. 端口 {first_config.get('port', 22)} 被阻止或错误")
                print(f"  建议：检查SSH服务是否运行，确认端口号正确")
            elif "Authentication failed" in error_msg or "权限" in error_msg:
                print(f"[诊断] 认证失败，可能的原因：")
                print(f"  1. 用户名或密码错误")
                print(f"  2. 用户没有SSH登录权限")
                print(f"  建议：检查用户名和密码，确认用户有SSH登录权限")
            
            import traceback
            traceback.print_exc()
            return False
    
    def disconnect_device(self, device_id):
        """断开设备连接"""
        try:
            with self.lock:
                if device_id in self.connected_devices:
                    device_info = self.connected_devices[device_id]
                    connection = device_info['connection']
                    if hasattr(connection, 'close'):
                        connection.close()
                    del self.connected_devices[device_id]
                    return True
            return False
        except Exception:
            return False
    
    def get_connected_devices(self):
        """获取已连接设备的信息"""
        with self.lock:
            return list(self.connected_devices.keys())
    
    def get_device_config(self, device_id):
        """获取已连接设备的配置"""
        with self.lock:
            if device_id in self.connected_devices:
                return self.connected_devices[device_id].get('config')
            return None
    
    def set_refresh_callback(self, callback):
        """设置刷新回调函数"""
        self.refresh_callback = callback
    
    def _trigger_refresh(self):
        """触发界面刷新 - 使用Qt信号确保在主线程中执行"""
        try:
            # 发射刷新信号，确保在主线程中执行
            self.refresh_signal.emit()
            print("[传输引擎] 已发射刷新信号")
        except Exception as e:
            print(f"[传输引擎] 发射刷新信号失败: {str(e)}")

    def delete_remote_file(self, remote_path, device_config, device_id=None):
        """删除远程文件"""
        try:
            # 优先使用传入的设备ID，如果没有则从配置中获取
            if device_id is None:
                device_id = device_config.get('device_id', 'unknown')
            
            # 确保设备已连接
            if device_id not in self.connected_devices:
                if not self.connect_device(device_id, device_config):
                    print(f"[ERROR] 设备连接失败: {device_id}")
                    return False
            
            device_info = self.connected_devices[device_id]
            connection = device_info['connection']
            # 使用已连接设备的实际协议配置，而不是传入的完整设备配置
            actual_config = device_info.get('config', {})
            protocol = actual_config.get('protocol', '').upper()
            
            print(f"[DEBUG] 删除文件协议: {protocol}, 路径: {remote_path}")
            print(f"[DEBUG] 连接类型: {type(connection)}")
            print(f"[DEBUG] 实际使用配置: {actual_config}")
            
            if protocol == 'SFTP':
                result = self._delete_sftp_file(connection, remote_path)
                print(f"[DEBUG] SFTP删除结果: {result}")
                return result
            elif protocol == 'FTP':
                result = self._delete_ftp_file(connection, remote_path)
                print(f"[DEBUG] FTP删除结果: {result}")
                return result
            else:
                print(f"[ERROR] 不支持的协议: {protocol}")
                return False
                
        except Exception as e:
            print(f"[ERROR] 删除远程文件失败: {str(e)}, 类型: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            return False

    def delete_remote_directory(self, remote_path, device_config, device_id=None):
        """删除远程目录"""
        try:
            # 优先使用传入的设备ID，如果没有则从配置中获取
            if device_id is None:
                device_id = device_config.get('device_id', 'unknown')
            
            # 确保设备已连接
            if device_id not in self.connected_devices:
                if not self.connect_device(device_id, device_config):
                    return False
            
            device_info = self.connected_devices[device_id]
            connection = device_info['connection']
            # 使用已连接设备的实际协议配置，而不是传入的完整设备配置
            actual_config = device_info.get('config', {})
            protocol = actual_config.get('protocol', '').upper()
            
            if protocol == 'SFTP':
                return self._delete_sftp_directory(connection, remote_path)
            elif protocol == 'FTP':
                return self._delete_ftp_directory(connection, remote_path)
            else:
                return False
                
        except Exception as e:
            print(f"删除远程目录失败: {str(e)}")
            return False

    def _delete_sftp_file(self, sftp_client, remote_path):
        """使用SFTP删除文件"""
        try:
            print(f"[DEBUG] SFTP尝试删除文件: {remote_path}")
            print(f"[DEBUG] SFTP客户端类型: {type(sftp_client)}")
            print(f"[DEBUG] SFTP客户端属性: {dir(sftp_client)}")
            
            # 检查文件是否存在
            try:
                file_attr = sftp_client.stat(remote_path)
                print(f"[DEBUG] 文件存在，大小: {file_attr.st_size}")
            except Exception as stat_e:
                print(f"[DEBUG] 文件不存在或无法访问: {str(stat_e)}")
                return False
            
            sftp_client.remove(remote_path)
            print(f"[DEBUG] SFTP文件删除成功: {remote_path}")
            return True
        except Exception as e:
            print(f"[ERROR] SFTP删除文件失败: {str(e)}, 类型: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            return False

    def _delete_sftp_directory(self, sftp_client, remote_path):
        """使用SFTP删除目录"""
        try:
            # 先删除目录中的所有内容
            for item in sftp_client.listdir_attr(remote_path):
                item_path = os.path.join(remote_path, item.filename).replace('\\', '/')
                if item.longname.startswith('d'):  # 目录
                    self._delete_sftp_directory(sftp_client, item_path)
                else:  # 文件
                    sftp_client.remove(item_path)
            
            # 删除空目录
            sftp_client.rmdir(remote_path)
            return True
        except Exception as e:
            print(f"SFTP删除目录失败: {str(e)}")
            return False

    def _delete_ftp_file(self, ftp_client, remote_path):
        """使用FTP删除文件"""
        try:
            ftp_client.delete(remote_path)
            return True
        except Exception as e:
            print(f"FTP删除文件失败: {str(e)}")
            return False

    def _delete_ftp_directory(self, ftp_client, remote_path):
        """使用FTP删除目录"""
        try:
            # FTP删除目录比较复杂，这里简化处理
            # 实际实现可能需要递归删除或使用FTP的RMD命令
            ftp_client.rmd(remote_path)
            return True
        except Exception as e:
            print(f"FTP删除目录失败: {str(e)}")
            return False

    def upload_file(self, local_path, remote_path, device_config):
        """上传单个文件"""
        task_id = self._generate_task_id()
        task = TransferTask(task_id, local_path, remote_path, device_config, "upload")
        
        # 检查是否是目录
        if os.path.isdir(local_path):
            task.is_directory = True
            task.file_count = self._count_files_in_directory(local_path)
        else:
            task.total_size = os.path.getsize(local_path)
        
        with self.lock:
            self.tasks[task_id] = task
        
        self.task_queue.put(task)
        self._start_worker_if_needed()
        
        return task_id
    
    def download_file(self, remote_path, local_path, device_config):
        """下载单个文件或目录"""
        print(f"[下载] 创建下载任务: {remote_path} -> {local_path}")
        task_id = self._generate_task_id()
        task = TransferTask(task_id, local_path, remote_path, device_config, "download")
        
        # 检查远程路径是否是目录
        is_dir = self._is_remote_directory(remote_path, device_config)
        print(f"[下载] 是否是目录: {is_dir}")
        if is_dir:
            task.is_directory = True
            # 计算远程目录中的文件数量
            task.file_count = self._count_remote_files(remote_path, device_config)
            print(f"[下载] 设置文件数量: {task.file_count}")
        
        with self.lock:
            self.tasks[task_id] = task
        
        self.task_queue.put(task)
        self._start_worker_if_needed()
        
        return task_id
    
    def _is_remote_directory(self, remote_path, device_config):
        """检查远程路径是否是目录"""
        protocol = device_config.get('protocol', '').upper()
        print(f"[检查目录] 检查远程路径: {remote_path}, 协议: {protocol}")
        
        try:
            if protocol == 'SFTP':
                sftp = self._connect_sftp(device_config)
                try:
                    import stat
                    file_stat = sftp.stat(remote_path)
                    is_dir = stat.S_ISDIR(file_stat.st_mode)
                    print(f"[检查目录] SFTP结果: {is_dir}")
                    return is_dir
                finally:
                    sftp.close()
            elif protocol == 'FTP':
                ftp = self._connect_ftp(device_config)
                try:
                    # 尝试切换到该路径，如果成功则是目录
                    current_dir = ftp.pwd()
                    try:
                        ftp.cwd(remote_path)
                        ftp.cwd(current_dir)  # 切回原目录
                        print(f"[检查目录] FTP结果: True")
                        return True
                    except:
                        print(f"[检查目录] FTP结果: False")
                        return False
                finally:
                    ftp.quit()
        except Exception as e:
            print(f"[检查目录] 无法检查远程路径类型: {e}")
            return False
        
        return False
    
    def _count_remote_files(self, remote_path, device_config):
        """计算远程目录中的文件数量"""
        try:
            print(f"[计算文件数] 开始计算远程目录文件数: {remote_path}")
            files = self._list_remote_files_recursive(remote_path, device_config)
            count = len(files)
            print(f"[计算文件数] 远程目录文件数: {count}")
            return count
        except Exception as e:
            print(f"[计算文件数] 无法计算远程文件数量: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def upload_directory(self, local_dir, remote_dir, device_config):
        """上传整个目录"""
        task_ids = []
        
        for root, dirs, files in os.walk(local_dir):
            for file in files:
                local_file_path = os.path.join(root, file)
                # 计算相对路径
                rel_path = os.path.relpath(local_file_path, local_dir)
                remote_file_path = os.path.join(remote_dir, rel_path).replace('\\', '/')
                
                task_id = self.upload_file(local_file_path, remote_file_path, device_config)
                task_ids.append(task_id)
        
        return task_ids
    
    def download_directory(self, remote_dir, local_dir, device_config):
        """下载整个目录"""
        # 这里需要先获取远程目录的文件列表
        # 然后为每个文件创建下载任务
        task_ids = []
        
        # 获取远程文件列表的逻辑需要根据具体协议实现
        # 这里先返回空列表，实际实现需要完善
        return task_ids
    
    def list_remote_files(self, remote_path, device_config):
        """列出远程文件"""
        try:
            protocol = device_config.get('protocol', '').upper()
            if protocol == 'SFTP':
                return self._list_sftp_files(remote_path, device_config)
            elif protocol == 'FTP':
                return self._list_ftp_files(remote_path, device_config)
            else:
                return []
                
        except Exception:
            return []
    
    def pause_all(self):
        """暂停所有传输"""
        self.paused = True
        with self.lock:
            for task in self.tasks.values():
                if task.status == TransferStatus.RUNNING:
                    task.pause()
    
    def resume_all(self):
        """继续所有传输"""
        self.paused = False
        with self.lock:
            for task in self.tasks.values():
                if task.status == TransferStatus.PAUSED:
                    task.resume()
    
    def cancel_all(self):
        """取消所有传输"""
        self.paused = True
        self.running = False
        with self.lock:
            for task in self.tasks.values():
                if task.status in [TransferStatus.PENDING, TransferStatus.RUNNING, TransferStatus.PAUSED]:
                    task.cancel()
    
    def get_progress_info(self):
        """获取当前传输进度信息"""
        with self.lock:
            active_tasks = [task for task in self.tasks.values() 
                          if task.status in [TransferStatus.RUNNING, TransferStatus.PAUSED]]
            
            if not active_tasks:
                return {
                    'current_file': '',
                    'speed': 0,
                    'progress': 0,
                    'message': ''
                }
            
            # 只返回第一个活跃任务的信息（简化显示）
            task = active_tasks[0]
            
            # 计算传输速度
            speed = 0
            if task.start_time and task.transferred_size > 0:
                elapsed = (datetime.now() - task.start_time).total_seconds()
                if elapsed > 0:
                    speed = task.transferred_size / elapsed
            
            return {
                'current_file': task.current_file,
                'speed': speed,
                'progress': task.progress,
                'message': f"{task.task_type.upper()}: {os.path.basename(task.local_path)} ({task.progress:.1f}%)"
            }
    
    def get_all_device_progress(self):
        """获取所有设备的传输进度信息"""
        with self.lock:
            device_progress = {}
            
            # 收集每个设备的任务信息
            for task in self.tasks.values():
                device_id = task.device_config.get('id', 'unknown')
                
                if device_id not in device_progress:
                    device_progress[device_id] = {
                        'status': 'idle',
                        'current_file': '',
                        'progress': 0,
                        'file_count': 0,
                        'completed_files': 0,
                        'total_size': 0,
                        'transferred_size': 0,
                        'speed': 0,
                        'md5_status': '',
                        'local_md5': '',
                        'remote_md5': '',
                        'md5_calculation_time': 0,  # MD5计算时间（秒）
                        'remaining_time': 0,  # 剩余时间（秒）
                        'md5_start_time': None,  # MD5计算开始时间
                        'transfer_start_time': None,  # 传输开始时间
                        'md5_history': [],  # MD5历史记录
                        'folder_local_md5': '',  # 文件夹整体本地MD5
                        'folder_remote_md5': ''  # 文件夹整体远程MD5
                    }
                
                # 更新设备状态
                if task.status == TransferStatus.RUNNING:
                    device_progress[device_id]['status'] = 'transferring'
                    device_progress[device_id]['current_file'] = task.current_file
                    device_progress[device_id]['progress'] = task.progress
                    device_progress[device_id]['file_count'] = task.file_count
                    device_progress[device_id]['completed_files'] = task.completed_files
                    device_progress[device_id]['total_size'] = task.total_size
                    device_progress[device_id]['transferred_size'] = task.transferred_size
                    device_progress[device_id]['local_md5'] = task.local_md5
                    device_progress[device_id]['remote_md5'] = task.remote_md5
                    device_progress[device_id]['md5_history'] = task.md5_history
                    device_progress[device_id]['folder_local_md5'] = task.folder_local_md5
                    device_progress[device_id]['folder_remote_md5'] = task.folder_remote_md5
                    
                    # 计算传输速率 - 只计算文件传输时间，不包括MD5计算时间
                    if task.transmission_start_time and task.transferred_size > 0:
                        # 计算传输结束时间
                        end_time = task.transmission_end_time if task.transmission_end_time else datetime.now()
                        # 计算实际传输时间（不包括MD5计算时间）
                        transmission_elapsed = (end_time - task.transmission_start_time).total_seconds()
                        if transmission_elapsed > 0:
                            device_progress[device_id]['speed'] = task.transferred_size / transmission_elapsed
                    
                    # 计算MD5计算时间和剩余时间
                    if task.md5_check_status == "校验中" and task.md5_start_time:
                        md5_elapsed = (datetime.now() - task.md5_start_time).total_seconds()
                        device_progress[device_id]['md5_calculation_time'] = md5_elapsed
                    elif task.md5_check_status == "校验成功" or task.md5_check_status == "校验失败":
                        device_progress[device_id]['md5_calculation_time'] = task.md5_elapsed_time
                    
                    # 传递MD5状态到进度数据
                    device_progress[device_id]['md5_status'] = task.md5_check_status
                    
                    # 计算剩余时间
                    if device_progress[device_id]['speed'] > 0 and task.total_size > 0:
                        remaining_bytes = task.total_size - task.transferred_size
                        device_progress[device_id]['remaining_time'] = remaining_bytes / device_progress[device_id]['speed']
                    else:
                        device_progress[device_id]['remaining_time'] = 0
                elif task.status == TransferStatus.PAUSED:
                    device_progress[device_id]['status'] = 'paused'
                    device_progress[device_id]['md5_status'] = task.md5_check_status
                    device_progress[device_id]['local_md5'] = task.local_md5
                    device_progress[device_id]['remote_md5'] = task.remote_md5
                    device_progress[device_id]['md5_history'] = task.md5_history
                    device_progress[device_id]['folder_local_md5'] = task.folder_local_md5
                    device_progress[device_id]['folder_remote_md5'] = task.folder_remote_md5
                elif task.status == TransferStatus.COMPLETED:
                    device_progress[device_id]['status'] = 'completed'
                    device_progress[device_id]['progress'] = 100.0
                    device_progress[device_id]['current_file'] = task.current_file
                    device_progress[device_id]['file_count'] = task.file_count
                    device_progress[device_id]['completed_files'] = task.completed_files
                    device_progress[device_id]['md5_status'] = task.md5_check_status
                    device_progress[device_id]['local_md5'] = task.local_md5
                    device_progress[device_id]['remote_md5'] = task.remote_md5
                    device_progress[device_id]['md5_history'] = task.md5_history
                    device_progress[device_id]['folder_local_md5'] = task.folder_local_md5
                    device_progress[device_id]['folder_remote_md5'] = task.folder_remote_md5
                    # 计算平均传输速度 - 只计算文件传输时间，不包括MD5计算时间
                    if task.transmission_start_time and task.total_size > 0:
                        # 计算传输结束时间
                        end_time = task.end_time if task.end_time else datetime.now()
                        # 计算实际传输时间（不包括MD5计算时间）
                        transmission_elapsed = (end_time - task.transmission_start_time).total_seconds()
                        if transmission_elapsed > 0:
                            device_progress[device_id]['speed'] = task.total_size / transmission_elapsed
                    # 传输完成后，剩余时间显示为0并标记为已完成
                    device_progress[device_id]['remaining_time'] = 0
                elif task.status == TransferStatus.FAILED:
                    device_progress[device_id]['status'] = 'error'
                    device_progress[device_id]['file_count'] = task.file_count
                    device_progress[device_id]['completed_files'] = task.completed_files
                    device_progress[device_id]['md5_status'] = task.md5_check_status
                    device_progress[device_id]['local_md5'] = task.local_md5
                    device_progress[device_id]['remote_md5'] = task.remote_md5
                    device_progress[device_id]['md5_history'] = task.md5_history
                    device_progress[device_id]['folder_local_md5'] = task.folder_local_md5
                    device_progress[device_id]['folder_remote_md5'] = task.folder_remote_md5
                elif task.status == TransferStatus.PENDING:
                    if device_progress[device_id]['status'] == 'idle':
                        device_progress[device_id]['status'] = 'queued'
                    device_progress[device_id]['md5_status'] = task.md5_check_status
                    device_progress[device_id]['local_md5'] = task.local_md5
                    device_progress[device_id]['remote_md5'] = task.remote_md5
                    device_progress[device_id]['md5_history'] = task.md5_history
                    device_progress[device_id]['folder_local_md5'] = task.folder_local_md5
                    device_progress[device_id]['folder_remote_md5'] = task.folder_remote_md5
                    # 在传输前显示预估的剩余时间
                    if task.total_size > 0 and device_progress[device_id]['speed'] > 0:
                        remaining_bytes = task.total_size
                        device_progress[device_id]['remaining_time'] = remaining_bytes / device_progress[device_id]['speed']
            
            # 为所有已连接但无传输任务的设备添加空闲状态
            for device_id in self.connected_devices:
                if device_id not in device_progress:
                    device_progress[device_id] = {
                        'status': 'idle',
                        'current_file': '',
                        'progress': 0,
                        'file_count': 0,
                        'completed_files': 0,
                        'total_size': 0,
                        'transferred_size': 0,
                        'speed': 0,
                        'md5_history': [],
                        'folder_local_md5': '',
                        'folder_remote_md5': ''
                    }
            
            return device_progress
    
    def _generate_task_id(self):
        """生成任务ID"""
        with self.lock:
            self.task_counter += 1
            return f"task_{self.task_counter}_{int(time.time())}"
    
    def _calculate_file_md5(self, file_path):
        """计算文件的MD5值"""
        try:
            if not os.path.exists(file_path):
                return ""
            
            md5_hash = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192 * 1024), b""):
                    md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except Exception as e:
            print(f"[MD5] 计算本地文件MD5失败: {file_path}, 错误: {str(e)}")
            return ""
    
    def _calculate_remote_md5_sftp(self, sftp, remote_path):
        """通过SFTP计算远程文件的MD5值"""
        try:
            # 尝试使用md5sum命令获取MD5
            # 获取SSH客户端
            ssh = sftp.get_channel().get_transport()
            # 执行远程命令获取MD5
            channel = ssh.open_channel("session")
            channel.exec_command(f"md5sum {remote_path}")
            stdout = channel.makefile("rb", -1)
            stderr = channel.makefile_stderr("rb", -1)
            result = stdout.read().decode().strip()
            channel.close()
            
            if result:
                md5_value = result.split()[0]
                return md5_value
            return ""
        except Exception as e:
            print(f"[MD5] 计算远程文件MD5失败(SFTP): {remote_path}, 错误: {str(e)}")
            return ""
    
    def _calculate_remote_md5_ftp(self, ftp, remote_path):
        """通过FTP计算远程文件的MD5值"""
        try:
            # FTP协议本身不支持直接计算MD5
            # 尝试下载文件到内存计算MD5（仅适用于小文件）
            import io
            md5_hash = hashlib.md5()
            
            def callback(data):
                md5_hash.update(data)
            
            # 尝试获取文件大小
            file_size = ftp.size(remote_path)
            if file_size and file_size < 10 * 1024 * 1024:  # 小于10MB的文件
                ftp.retrbinary(f"RETR {remote_path}", callback)
                return md5_hash.hexdigest()
            else:
                print(f"[MD5] 文件太大，跳过FTP MD5计算: {remote_path}")
                return ""
        except Exception as e:
            print(f"[MD5] 计算远程文件MD5失败(FTP): {remote_path}, 错误: {str(e)}")
            return ""
    
    def _start_worker_if_needed(self):
        """如果需要，启动工作线程"""
        if not self.running and not self.task_queue.empty():
            self.running = True
            self.executor.submit(self._worker)
    
    def _worker(self):
        """工作线程处理传输任务"""
        while self.running:
            try:
                if self.paused:
                    time.sleep(0.5)
                    continue
                
                task = self.task_queue.get(timeout=1.0)
                self._process_task(task)
                
            except queue.Empty:
                # 队列为空，检查是否还有任务
                with self.lock:
                    if all(task.status in [TransferStatus.COMPLETED, TransferStatus.FAILED, TransferStatus.CANCELLED] 
                          for task in self.tasks.values()):
                        self.running = False
                        break
    
    def _process_task(self, task):
        """处理单个传输任务"""
        try:
            task.start()
            protocol = task.device_config.get('protocol', '').upper()
            
            if task.is_directory:
                # 处理目录传输
                if task.task_type == "upload":
                    self._upload_directory_task(task)
                else:
                    self._download_directory_task(task)
            else:
                # 处理文件传输
                if protocol == 'SFTP':
                    self._transfer_via_sftp(task)
                elif protocol == 'FTP':
                    self._transfer_via_ftp(task)
                else:
                    task.fail(f"不支持的协议: {protocol}")
                    return
            
            task.complete()
            print(f"[传输引擎] 任务 {task.task_id} 完成，准备触发界面刷新")
            # 传输完成后触发界面刷新
            self._trigger_refresh()
            print(f"[传输引擎] 任务 {task.task_id} 界面刷新已触发")
            
        except Exception as e:
            print(f"[传输引擎] 任务 {task.task_id} 失败: {str(e)}")
            task.fail(f"传输失败: {str(e)}")
    
    def _upload_directory_task(self, task):
        """上传目录任务"""
        import hashlib
        
        remote_base = task.remote_path
        
        # 初始化文件夹整体MD5计算器（将所有文件的MD5值合并计算）
        folder_md5_hash = hashlib.md5()
        
        for root, dirs, files in os.walk(task.local_path):
            for file in files:
                if task.status != TransferStatus.RUNNING:
                    break
                    
                local_file_path = os.path.join(root, file)
                rel_path = os.path.relpath(local_file_path, task.local_path)
                remote_file_path = os.path.join(remote_base, rel_path).replace('\\', '/')
                
                task.current_file = file
                
                # 上传文件（这会更新task.local_md5和task.remote_md5）
                self._upload_single_file(local_file_path, remote_file_path, task.device_config, task)
                
                # 添加到MD5历史记录
                md5_record = {
                    'filename': file,
                    'local_md5': task.local_md5,
                    'remote_md5': task.remote_md5,
                    'status': task.md5_check_status
                }
                task.md5_history.append(md5_record)
                
                # 累积计算文件夹整体MD5（将每个文件的MD5值作为输入）
                if task.local_md5:
                    folder_md5_hash.update(task.local_md5.encode())
                
                task.completed_files += 1
                
                # 更新总体进度
                if task.file_count > 0:
                    task.progress = (task.completed_files / task.file_count) * 100
                
                # 每个文件完成后触发界面刷新
                self.refresh_signal.emit()
        
        # 完成后计算文件夹整体MD5
        task.folder_local_md5 = folder_md5_hash.hexdigest()
        # 远程文件夹MD5同样计算（使用远程文件的MD5值）
        remote_folder_hash = hashlib.md5()
        for record in task.md5_history:
            if record['remote_md5']:
                remote_folder_hash.update(record['remote_md5'].encode())
        task.folder_remote_md5 = remote_folder_hash.hexdigest()
    
    def _download_directory_task(self, task):
        """下载目录任务"""
        import hashlib
        import stat
        
        remote_base = task.remote_path
        local_base = task.local_path
        
        print(f"[下载目录] 开始下载目录: {remote_base} -> {local_base}")
        print(f"[下载目录] 文件数量: {task.file_count}")
        
        # 确保本地目录存在
        os.makedirs(local_base, exist_ok=True)
        
        # 初始化文件夹整体MD5计算器
        folder_md5_hash = hashlib.md5()
        
        protocol = task.device_config.get('protocol', '').upper()
        
        # 递归获取远程文件列表
        all_files = self._list_remote_files_recursive(remote_base, task.device_config)
        print(f"[下载目录] 获取到 {len(all_files)} 个文件")
        
        for file_info in all_files:
            if task.status != TransferStatus.RUNNING:
                break
            
            remote_file_path = file_info['remote_path']
            rel_path = file_info['rel_path']
            local_file_path = os.path.join(local_base, rel_path.replace('/', os.sep))
            
            task.current_file = file_info['name']
            
            # 下载文件（这会更新task.local_md5和task.remote_md5）
            self._download_single_file(remote_file_path, local_file_path, task.device_config, task)
            
            # 添加到MD5历史记录
            md5_record = {
                'filename': file_info['name'],
                'local_md5': task.local_md5,
                'remote_md5': task.remote_md5,
                'status': task.md5_check_status
            }
            task.md5_history.append(md5_record)
            
            # 累积计算文件夹整体MD5
            if task.local_md5:
                folder_md5_hash.update(task.local_md5.encode())
            
            task.completed_files += 1
            
            # 更新总体进度
            if task.file_count > 0:
                task.progress = (task.completed_files / task.file_count) * 100
            
            # 每个文件完成后触发界面刷新
            self.refresh_signal.emit()
        
        # 完成后计算文件夹整体MD5
        task.folder_local_md5 = folder_md5_hash.hexdigest()
        # 远程文件夹MD5同样计算
        remote_folder_hash = hashlib.md5()
        for record in task.md5_history:
            if record['remote_md5']:
                remote_folder_hash.update(record['remote_md5'].encode())
        task.folder_remote_md5 = remote_folder_hash.hexdigest()
    
    def _list_remote_files_recursive(self, remote_path, device_config, base_path=None):
        """递归获取远程目录下的所有文件"""
        import stat
        
        if base_path is None:
            base_path = remote_path
        
        all_files = []
        protocol = device_config.get('protocol', '').upper()
        
        if protocol == 'SFTP':
            sftp = self._connect_sftp(device_config)
            try:
                self._list_sftp_files_recursive(sftp, remote_path, base_path, all_files)
            finally:
                sftp.close()
        elif protocol == 'FTP':
            ftp = self._connect_ftp(device_config)
            try:
                self._list_ftp_files_recursive(ftp, remote_path, base_path, all_files)
            finally:
                ftp.quit()
        
        return all_files
    
    def _list_sftp_files_recursive(self, sftp, remote_path, base_path, all_files):
        """递归获取SFTP目录下的所有文件"""
        import stat
        
        try:
            for item in sftp.listdir_attr(remote_path):
                item_path = f"{remote_path}/{item.filename}"
                
                if stat.S_ISDIR(item.st_mode):
                    # 递归处理子目录
                    self._list_sftp_files_recursive(sftp, item_path, base_path, all_files)
                elif stat.S_ISREG(item.st_mode):
                    # 记录文件
                    rel_path = os.path.relpath(item_path, base_path)
                    all_files.append({
                        'name': item.filename,
                        'remote_path': item_path,
                        'rel_path': rel_path,
                        'size': item.st_size
                    })
        except Exception as e:
            print(f"[下载目录] 无法列出目录 {remote_path}: {e}")
    
    def _list_ftp_files_recursive(self, ftp, remote_path, base_path, all_files):
        """递归获取FTP目录下的所有文件"""
        try:
            files = []
            ftp.cwd(remote_path)
            ftp.retrlines('LIST', files.append)
            
            for line in files:
                parts = line.split()
                if len(parts) >= 9:
                    name = ' '.join(parts[8:])
                    is_dir = line.startswith('d')
                    item_path = f"{remote_path}/{name}"
                    
                    if is_dir and name not in ['.', '..']:
                        # 递归处理子目录
                        self._list_ftp_files_recursive(ftp, item_path, base_path, all_files)
                    elif not is_dir:
                        # 记录文件
                        rel_path = os.path.relpath(item_path, base_path)
                        all_files.append({
                            'name': name,
                            'remote_path': item_path,
                            'rel_path': rel_path,
                            'size': 0  # FTP的LIST命令解析较复杂，这里简化
                        })
        except Exception as e:
            print(f"[下载目录] 无法列出目录 {remote_path}: {e}")
    
    def _upload_single_file(self, local_path, remote_path, device_config, task):
        """上传单个文件（支持大文件分块传输）"""
        protocol = device_config.get('protocol', '').upper()
        
        if protocol == 'SFTP':
            self._upload_file_sftp(local_path, remote_path, device_config, task)
        elif protocol == 'FTP':
            self._upload_file_ftp(local_path, remote_path, device_config, task)
    
    def _download_single_file(self, remote_path, local_path, device_config, task):
        """下载单个文件"""
        protocol = device_config.get('protocol', '').upper()
        
        if protocol == 'SFTP':
            self._download_file_sftp(remote_path, local_path, device_config, task)
        elif protocol == 'FTP':
            self._download_file_ftp(remote_path, local_path, device_config, task)
    
    def _upload_file_sftp(self, local_path, remote_path, device_config, task):
        """通过SFTP上传文件"""
        config = device_config
        
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # 连接SSH
            ssh.connect(
                hostname=config.get('host', ''),
                port=config.get('port', 22),
                username=config.get('username', ''),
                password=config.get('password', ''),
                timeout=30
            )
            
            # 创建SFTP客户端
            sftp = ssh.open_sftp()
            
            file_size = os.path.getsize(local_path)
            task.total_size = file_size
            task.current_file = local_path
            
            # 计算本地MD5（在传输前）
            print("[MD5] 开始计算本地文件MD5...")
            
            task.md5_start_time = datetime.now()
            task.local_md5 = self._calculate_file_md5(local_path)
            task.md5_elapsed_time = (datetime.now() - task.md5_start_time).total_seconds()
            
            print(f"[MD5] 本地文件MD5: {task.local_md5}")
            print(f"[MD5] MD5计算时间: {task.md5_elapsed_time:.2f}秒")
            
            # MD5计算完成后，设置传输开始时间
            task.transmission_start_time = datetime.now()
            
            # 记录传输开始
            self._log_transfer_start(task)
            
            # 触发界面刷新，清空旧进度数据
            self.refresh_signal.emit()
            
            # 确保远程目录存在
            remote_dir = os.path.dirname(remote_path)
            self._ensure_sftp_directory(sftp, remote_dir)
            
            # 执行上传（支持大文件分块）
            def progress_callback(transferred, total):
                task.update_progress(transferred, total)
            
            sftp.put(local_path, remote_path, callback=progress_callback)
            
            # 文件传输完成，设置传输结束时间
            task.transmission_end_time = datetime.now()
            
            # 上传完成后验证远程文件大小和MD5
            try:
                remote_stat = sftp.stat(remote_path)
                local_size = os.path.getsize(local_path)
                print(f"[传输完成验证] 本地文件: {os.path.basename(local_path)}")
                print(f"[传输完成验证] 本地大小: {local_size} 字节 ({self._format_file_size(local_size)})")
                print(f"[传输完成验证] 远程大小: {remote_stat.st_size} 字节 ({self._format_file_size(remote_stat.st_size)})")
                
                # 验证大小是否一致
                if local_size == remote_stat.st_size:
                    print(f"[传输完成验证] ✓ 文件大小验证成功，传输完整")
                    
                    # 计算并比较MD5
                    print(f"[MD5校验] 开始计算远程文件MD5...")
                    task.md5_check_status = "校验中"
                    task.remote_md5 = self._calculate_remote_md5_sftp(sftp, remote_path)
                    print(f"[MD5校验] 远程文件MD5: {task.remote_md5}")
                    
                    if task.local_md5 and task.remote_md5:
                        if task.local_md5 == task.remote_md5:
                            task.md5_check_status = "校验成功"
                            print(f"[MD5校验] ✓ MD5校验成功，文件完整性验证通过")
                        else:
                            task.md5_check_status = "校验失败"
                            print(f"[MD5校验] ✗ MD5校验失败，本地: {task.local_md5}, 远程: {task.remote_md5}")
                    else:
                        task.md5_check_status = "无法校验"
                        print(f"[MD5校验] ⚠ 无法完成MD5校验")
                else:
                    print(f"[传输完成验证] ⚠ 文件大小不一致！本地: {local_size}, 远程: {remote_stat.st_size}")
                    task.md5_check_status = "校验失败"
                    
                # 记录传输完成
                self._log_transfer_complete(task, task.md5_check_status == "校验成功")
                
            except Exception as e:
                print(f"[传输完成验证] 验证失败: {str(e)}")
                task.md5_check_status = "校验失败"
                self._log_transfer_complete(task, False, str(e))
            
            sftp.close()
            
        finally:
            ssh.close()
    
    def _upload_file_ftp(self, local_path, remote_path, device_config, task):
        """通过FTP上传文件"""
        config = device_config
        
        try:
            # 连接FTP
            ftp = ftplib.FTP()
            ftp.connect(config.get('host', ''), config.get('port', 21))
            ftp.login(config.get('username', ''), config.get('password', ''))
            
            file_size = os.path.getsize(local_path)
            task.total_size = file_size
            task.current_file = local_path
            
            # 计算本地MD5（在传输前）
            print("[MD5] 开始计算本地文件MD5...")
            
            task.md5_start_time = datetime.now()
            task.local_md5 = self._calculate_file_md5(local_path)
            task.md5_elapsed_time = (datetime.now() - task.md5_start_time).total_seconds()
            
            print(f"[MD5] 本地文件MD5: {task.local_md5}")
            print(f"[MD5] MD5计算时间: {task.md5_elapsed_time:.2f}秒")
            
            # MD5计算完成后，设置传输开始时间
            task.transmission_start_time = datetime.now()
            
            # 记录传输开始
            self._log_transfer_start(task)
            
            # 触发界面刷新，清空旧进度数据
            self.refresh_signal.emit()
            
            # 确保远程目录存在
            remote_dir = os.path.dirname(remote_path)
            self._ensure_ftp_directory(ftp, remote_dir)
            
            # 执行上传
            with open(local_path, 'rb') as local_file:
                ftp.storbinary(f"STOR {remote_path}", local_file, 
                             blocksize=8192, 
                             callback=lambda data: self._ftp_upload_callback(task, data, file_size))
            
            # 文件传输完成，设置传输结束时间
            task.transmission_end_time = datetime.now()
            
            # 更新进度表，显示传输前计算的MD5值
            self.update_progress_table()
            
            # 上传完成后验证远程文件大小和MD5
            try:
                remote_size = ftp.size(remote_path)
                local_size = os.path.getsize(local_path)
                print(f"[传输完成验证] 本地文件: {os.path.basename(local_path)}")
                print(f"[传输完成验证] 本地大小: {local_size} 字节 ({self._format_file_size(local_size)})")
                print(f"[传输完成验证] 远程大小: {remote_size} 字节 ({self._format_file_size(remote_size)})")
                
                # 验证大小是否一致
                if remote_size is not None and local_size == remote_size:
                    print(f"[传输完成验证] ✓ 文件大小验证成功，传输完整")
                    
                    # 计算并比较MD5
                    print(f"[MD5校验] 开始计算远程文件MD5...")
                    task.md5_check_status = "校验中"
                    task.remote_md5 = self._calculate_remote_md5_ftp(ftp, remote_path)
                    print(f"[MD5校验] 远程文件MD5: {task.remote_md5}")
                    
                    if task.local_md5 and task.remote_md5:
                        if task.local_md5 == task.remote_md5:
                            task.md5_check_status = "校验成功"
                            print(f"[MD5校验] ✓ MD5校验成功，文件完整性验证通过")
                        else:
                            task.md5_check_status = "校验失败"
                            print(f"[MD5校验] ✗ MD5校验失败，本地: {task.local_md5}, 远程: {task.remote_md5}")
                    else:
                        task.md5_check_status = "无法校验"
                        print(f"[MD5校验] ⚠ 无法完成MD5校验")
                else:
                    print(f"[传输完成验证] ⚠ 文件大小不一致！本地: {local_size}, 远程: {remote_size}")
                    task.md5_check_status = "校验失败"
                    
                # 记录传输完成
                self._log_transfer_complete(task, task.md5_check_status == "校验成功")
                
            except Exception as e:
                print(f"[传输完成验证] 验证失败: {str(e)}")
                task.md5_check_status = "校验失败"
                self._log_transfer_complete(task, False, str(e))
            
            ftp.quit()
            
        except Exception as e:
            raise Exception(f"FTP上传错误: {str(e)}")
    
    def _ftp_upload_callback(self, task, data, total_size):
        """FTP上传进度回调"""
        task.transferred_size += len(data)
        if total_size > 0:
            # 计算进度，但不超过100%
            progress = (task.transferred_size / total_size) * 100
            task.progress = min(progress, 100.0)
    
    def _transfer_via_sftp(self, task):
        """通过SFTP传输文件"""
        if task.task_type == "upload":
            self._upload_file_sftp(task.local_path, task.remote_path, task.device_config, task)
        else:
            self._download_file_sftp(task.remote_path, task.local_path, task.device_config, task)
    
    def _transfer_via_ftp(self, task):
        """通过FTP传输文件"""
        if task.task_type == "upload":
            self._upload_file_ftp(task.local_path, task.remote_path, task.device_config, task)
        else:
            self._download_file_ftp(task.remote_path, task.local_path, task.device_config, task)
    
    def _download_file_sftp(self, remote_path, local_path, device_config, task):
        """通过SFTP下载文件"""
        config = device_config
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            ssh.connect(
                hostname=config.get('host', ''),
                port=config.get('port', 22),
                username=config.get('username', ''),
                password=config.get('password', ''),
                timeout=30
            )
            
            sftp = ssh.open_sftp()
            
            # 获取文件大小
            file_attr = sftp.stat(remote_path)
            file_size = file_attr.st_size
            task.total_size = file_size
            task.current_file = remote_path
            
            # 计算远程MD5（在传输前）
            print("[MD5] 开始计算远程文件MD5...")
            
            task.md5_start_time = datetime.now()
            task.remote_md5 = self._calculate_remote_md5_sftp(sftp, remote_path)
            task.md5_elapsed_time = (datetime.now() - task.md5_start_time).total_seconds()
            
            if task.remote_md5:
                print(f"[MD5] 远程文件MD5: {task.remote_md5}")
            else:
                print(f"[MD5] 远程文件MD5: 计算失败")
            
            print(f"[MD5] MD5计算时间: {task.md5_elapsed_time:.2f}秒")
            
            # MD5计算完成后，设置传输开始时间
            task.transmission_start_time = datetime.now()
            
            # 记录传输开始
            self._log_transfer_start(task)
            
            # 触发界面刷新，清空旧进度数据
            self.refresh_signal.emit()
            
            # 确保本地目录存在
            local_dir = os.path.dirname(local_path)
            os.makedirs(local_dir, exist_ok=True)
            
            # 执行下载
            def progress_callback(transferred, total):
                task.update_progress(transferred, total)
            
            sftp.get(remote_path, local_path, callback=progress_callback)
            
            # 文件传输完成，设置传输结束时间
            task.transmission_end_time = datetime.now()
            
            sftp.close()
            
            # 下载完成后验证本地文件大小和MD5
            try:
                local_size = os.path.getsize(local_path)
                # 重新打开SFTP连接来获取远程文件信息
                ssh.connect(
                    hostname=config.get('host', ''),
                    port=config.get('port', 22),
                    username=config.get('username', ''),
                    password=config.get('password', ''),
                    timeout=30
                )
                sftp = ssh.open_sftp()
                remote_stat = sftp.stat(remote_path)
                sftp.close()
                ssh.close()
                
                print(f"[传输完成验证] 本地文件: {os.path.basename(local_path)}")
                print(f"[传输完成验证] 本地大小: {local_size} 字节 ({self._format_file_size(local_size)})")
                print(f"[传输完成验证] 远程大小: {remote_stat.st_size} 字节 ({self._format_file_size(remote_stat.st_size)})")
                
                # 验证大小是否一致
                if local_size == remote_stat.st_size:
                    print(f"[传输完成验证] ✓ 文件大小验证成功，传输完整")
                    
                    # 计算并比较MD5
                    print(f"[MD5校验] 开始计算本地文件MD5...")
                    task.md5_check_status = "校验中"
                    task.local_md5 = self._calculate_file_md5(local_path)
                    print(f"[MD5校验] 本地文件MD5: {task.local_md5}")
                    
                    # 远程MD5已经在传输前计算过了，这里直接使用
                    if task.remote_md5:
                        print(f"[MD5校验] 远程文件MD5: {task.remote_md5}")
                    else:
                        print(f"[MD5校验] 远程文件MD5: 计算失败")
                    
                    if task.local_md5 and task.remote_md5:
                        if task.local_md5 == task.remote_md5:
                            task.md5_check_status = "校验成功"
                            print(f"[MD5校验] ✓ MD5校验成功，文件完整性验证通过")
                        else:
                            task.md5_check_status = "校验失败"
                            print(f"[MD5校验] ✗ MD5校验失败，本地: {task.local_md5}, 远程: {task.remote_md5}")
                    else:
                        task.md5_check_status = "无法校验"
                        print(f"[MD5校验] ⚠ 无法完成MD5校验")
                else:
                    print(f"[传输完成验证] ⚠ 文件大小不一致！本地: {local_size}, 远程: {remote_stat.st_size}")
                    task.md5_check_status = "校验失败"
                    
                # 记录传输完成
                self._log_transfer_complete(task, task.md5_check_status == "校验成功")
                
            except Exception as e:
                print(f"[传输完成验证] 验证失败: {str(e)}")
                task.md5_check_status = "校验失败"
                self._log_transfer_complete(task, False, str(e))
            
        finally:
            ssh.close()
    
    def _download_file_ftp(self, remote_path, local_path, device_config, task):
        """通过FTP下载文件"""
        config = device_config
        
        try:
            ftp = ftplib.FTP()
            ftp.connect(config.get('host', ''), config.get('port', 21))
            ftp.login(config.get('username', ''), config.get('password', ''))
            
            # 获取文件大小
            file_size = ftp.size(remote_path)
            if file_size is None:
                file_size = 0
            
            task.total_size = file_size
            task.current_file = remote_path
            
            # 计算远程MD5（在传输前）
            print("[MD5] 开始计算远程文件MD5...")
            
            task.md5_start_time = datetime.now()
            task.remote_md5 = self._calculate_remote_md5_ftp(ftp, remote_path)
            task.md5_elapsed_time = (datetime.now() - task.md5_start_time).total_seconds()
            
            if task.remote_md5:
                print(f"[MD5] 远程文件MD5: {task.remote_md5}")
            else:
                print(f"[MD5] 远程文件MD5: 计算失败")
            
            print(f"[MD5] MD5计算时间: {task.md5_elapsed_time:.2f}秒")
            
            # MD5计算完成后，设置传输开始时间
            task.transmission_start_time = datetime.now()
            
            # 记录传输开始
            self._log_transfer_start(task)
            
            # 触发界面刷新，清空旧进度数据
            self.refresh_signal.emit()
            
            # 确保本地目录存在
            local_dir = os.path.dirname(local_path)
            os.makedirs(local_dir, exist_ok=True)
            
            # 执行下载
            with open(local_path, 'wb') as local_file:
                def callback(data):
                    local_file.write(data)
                    task.transferred_size += len(data)
                    if file_size > 0:
                        task.progress = (task.transferred_size / file_size) * 100
                
                ftp.retrbinary(f"RETR {remote_path}", callback, blocksize=8192)
            
            # 文件传输完成，设置传输结束时间
            task.transmission_end_time = datetime.now()
            
            ftp.quit()
            
            # 下载完成后验证本地文件大小和MD5
            try:
                local_size = os.path.getsize(local_path)
                # 重新连接FTP来获取远程文件信息
                ftp = ftplib.FTP()
                ftp.connect(config.get('host', ''), config.get('port', 21))
                ftp.login(config.get('username', ''), config.get('password', ''))
                remote_size = ftp.size(remote_path)
                ftp.quit()
                
                print(f"[传输完成验证] 本地文件: {os.path.basename(local_path)}")
                print(f"[传输完成验证] 本地大小: {local_size} 字节 ({self._format_file_size(local_size)})")
                print(f"[传输完成验证] 远程大小: {remote_size} 字节 ({self._format_file_size(remote_size)})")
                
                # 验证大小是否一致
                if local_size == remote_size:
                    print(f"[传输完成验证] ✓ 文件大小验证成功，传输完整")
                    
                    # 计算并比较MD5
                    print(f"[MD5校验] 开始计算本地文件MD5...")
                    task.md5_check_status = "校验中"
                    task.local_md5 = self._calculate_file_md5(local_path)
                    print(f"[MD5校验] 本地文件MD5: {task.local_md5}")
                    
                    # 远程MD5已经在传输前计算过了，这里直接使用
                    if task.remote_md5:
                        print(f"[MD5校验] 远程文件MD5: {task.remote_md5}")
                    else:
                        print(f"[MD5校验] 远程文件MD5: 计算失败")
                    
                    if task.local_md5 and task.remote_md5:
                        if task.local_md5 == task.remote_md5:
                            task.md5_check_status = "校验成功"
                            print(f"[MD5校验] ✓ MD5校验成功，文件完整性验证通过")
                        else:
                            task.md5_check_status = "校验失败"
                            print(f"[MD5校验] ✗ MD5校验失败，本地: {task.local_md5}, 远程: {task.remote_md5}")
                    else:
                        task.md5_check_status = "无法校验"
                        print(f"[MD5校验] ⚠ 无法完成MD5校验")
                else:
                    print(f"[传输完成验证] ⚠ 文件大小不一致！本地: {local_size}, 远程: {remote_size}")
                    task.md5_check_status = "校验失败"
                    
                # 记录传输完成
                self._log_transfer_complete(task, task.md5_check_status == "校验成功")
                
            except Exception as e:
                print(f"[传输完成验证] 验证失败: {str(e)}")
                task.md5_check_status = "校验失败"
                self._log_transfer_complete(task, False, str(e))
            
        except Exception as e:
            raise Exception(f"FTP下载错误: {str(e)}")
    
    def _connect_sftp(self, config):
        """连接SFTP服务器"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        ssh.connect(
            hostname=config.get('host', config.get('ip', '')),  # 支持 ip 和 host 字段
            port=config.get('port', 22),
            username=config.get('username', ''),
            password=config.get('password', ''),
            timeout=30
        )
        
        return ssh.open_sftp()
    
    def _connect_ftp(self, config):
        """连接FTP服务器"""
        ftp = ftplib.FTP()
        port = config.get('port', 21)
        # 确保端口是整数类型
        if isinstance(port, str):
            port = int(port)
        ftp.connect(config.get('host', config.get('ip', '')), port)  # 支持 ip 和 host 字段
        ftp.login(config.get('username', ''), config.get('password', ''))
        return ftp
    
    def _list_sftp_files(self, remote_path, config):
        """列出SFTP文件"""
        import stat
        sftp = self._connect_sftp(config)
        file_list = []
        
        try:
            # 强制刷新文件列表，避免缓存问题
            sftp.listdir(remote_path)  # 先执行一次listdir刷新缓存
            
            for item in sftp.listdir_attr(remote_path):
                # 使用stat模块准确判断文件类型
                is_dir = stat.S_ISDIR(item.st_mode)
                is_symlink = stat.S_ISLNK(item.st_mode)
                
                # 调试：打印原始文件信息
                print(f"[DEBUG SFTP] 文件: {item.filename}, listdir_attr大小: {item.st_size} 字节, 类型: {'目录' if is_dir else '文件'}")
                
                # 对于文件，始终使用stat获取最新的文件大小
                if not is_dir and not is_symlink:
                    try:
                        # 强制重新获取文件状态，避免缓存
                        file_stat = sftp.stat(remote_path + '/' + item.filename)
                        actual_size = file_stat.st_size
                        print(f"[DEBUG SFTP] 使用stat获取的实际大小: {actual_size} 字节")
                        
                        # 记录大小差异
                        if actual_size != item.st_size:
                            print(f"[DEBUG SFTP] ⚠ 大小不一致！listdir_attr: {item.st_size}, stat: {actual_size}, 差异: {actual_size - item.st_size} 字节")
                        
                        # 始终使用stat的大小，确保显示最新数据
                        item.st_size = actual_size
                        
                    except Exception as e:
                        print(f"[DEBUG SFTP] 获取stat信息失败: {e}")
                        # 如果stat失败，使用listdir_attr的大小作为备选
                        actual_size = item.st_size
                else:
                    actual_size = item.st_size
                
                # 判断文件类型
                if is_dir:
                    file_type = '目录'
                elif is_symlink:
                    # 对于符号链接，尝试判断目标类型
                    try:
                        target_stat = sftp.stat(remote_path + '/' + item.filename)
                        if stat.S_ISDIR(target_stat.st_mode):
                            file_type = '目录'
                            is_dir = True  # 标记为目录，方便后续处理
                        else:
                            file_type = '链接'
                    except:
                        file_type = '链接'
                else:
                    file_type = '文件'
                
                # 格式化文件大小
                if not is_dir:
                    formatted_size = self._format_file_size(actual_size)
                    print(f"[DEBUG SFTP] 最终显示大小: {formatted_size}")
                else:
                    formatted_size = ''
                
                file_info = {
                    'name': item.filename,
                    'type': file_type,
                    'size': formatted_size,
                    'mod_time': datetime.fromtimestamp(item.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'permissions': self._format_permissions(item.st_mode)
                }
                file_list.append(file_info)
        finally:
            sftp.close()
        
        print(f"[DEBUG SFTP] 最终返回文件列表长度: {len(file_list)}")
        return file_list
    
    def _list_ftp_files(self, remote_path, config):
        """列出FTP文件"""
        ftp = self._connect_ftp(config)
        file_list = []
        
        try:
            ftp.cwd(remote_path)
            files = []
            ftp.retrlines('LIST', files.append)
            
            # 调试：打印原始LIST输出
            print(f"[DEBUG] FTP LIST 原始输出:")
            for i, line in enumerate(files):
                print(f"[DEBUG] {i}: {line}")
            
            for line in files:
                # 解析FTP LIST命令的输出
                parts = line.split()
                if len(parts) >= 9:
                    permissions = parts[0]
                    size_str = parts[4] if not parts[0].startswith('d') else ''
                    name = ' '.join(parts[8:])
                    
                    # 调试：打印解析结果
                    print(f"[DEBUG] 解析文件: {name}, 权限: {permissions}, 原始大小: {size_str}")
                    
                    # 正确格式化文件大小
                    if size_str.isdigit():
                        # 转换为整数并使用统一的格式化方法
                        size_bytes = int(size_str)
                        formatted_size = self._format_file_size(size_bytes)
                        print(f"[DEBUG] 格式化后大小: {formatted_size}")
                    else:
                        formatted_size = ''
                        print(f"[DEBUG] 无效大小字符串: {size_str}")
                    
                    file_info = {
                        'name': name,
                        'type': '目录' if permissions.startswith('d') else '文件',
                        'size': formatted_size,  # 使用统一格式化的文件大小
                        'mod_time': ' '.join(parts[5:8]),
                        'permissions': permissions
                    }
                    file_list.append(file_info)
        finally:
            ftp.quit()
        
        return file_list
    
    def _ensure_sftp_directory(self, sftp, remote_dir):
        """确保SFTP远程目录存在"""
        if remote_dir == '' or remote_dir == '/':
            return
        
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            parent_dir = os.path.dirname(remote_dir)
            self._ensure_sftp_directory(sftp, parent_dir)
            sftp.mkdir(remote_dir)
    
    def _ensure_ftp_directory(self, ftp, remote_dir):
        """确保FTP远程目录存在"""
        if remote_dir == '' or remote_dir == '/':
            return
        
        try:
            ftp.cwd(remote_dir)
            ftp.cwd('/')  # 回到根目录
        except:
            parent_dir = os.path.dirname(remote_dir)
            self._ensure_ftp_directory(ftp, parent_dir)
            ftp.mkd(remote_dir)
    
    def _count_files_in_directory(self, directory):
        """计算目录中的文件数量"""
        count = 0
        for root, dirs, files in os.walk(directory):
            count += len(files)
        return count
    
    def _format_file_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size = float(size_bytes)
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        
        # 计算应该使用哪个单位
        unit_index = 0
        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"
    
    def _format_permissions(self, mode):
        """格式化权限字符串（跨平台兼容）"""
        try:
            # 尝试使用Unix权限常量（Linux/Mac）
            perm_str = ''
            for who in "USR", "GRP", "OTH":
                for perm in "R", "W", "X":
                    if mode & getattr(os, f"S_I{perm}{who}"):
                        perm_str += perm.lower()
                    else:
                        perm_str += '-'
            return perm_str
        except AttributeError:
            # Windows系统或其他不支持os权限常量的系统
            # 返回一个通用的权限表示
            if mode & 0o40000:  # 目录
                return 'drwxr-xr-x'
            else:  # 文件
                return '-rw-r--r--'
    
    def shutdown(self):
        """关闭传输引擎"""
        self.cancel_all()
        
        # 断开所有设备连接
        for device_id in list(self.connected_devices.keys()):
            self.disconnect_device(device_id)
        
        self.executor.shutdown(wait=True)