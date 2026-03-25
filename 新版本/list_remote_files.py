#!/usr/bin/env python3
"""
列出远程设备 192.168.226.146 的文件列表
"""

import paramiko
from datetime import datetime

def format_file_size(size):
    """格式化文件大小"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"

def format_permissions(mode):
    """格式化文件权限"""
    import stat
    perms = ''
    perms += 'd' if stat.S_ISDIR(mode) else '-'
    perms += 'r' if mode & 0o400 else '-'
    perms += 'w' if mode & 0o200 else '-'
    perms += 'x' if mode & 0o100 else '-'
    perms += 'r' if mode & 0o040 else '-'
    perms += 'w' if mode & 0o020 else '-'
    perms += 'x' if mode & 0o010 else '-'
    perms += 'r' if mode & 0o004 else '-'
    perms += 'w' if mode & 0o002 else '-'
    perms += 'x' if mode & 0o001 else '-'
    return perms

def list_sftp_files(hostname, username, password, port=22, remote_path="/"):
    """列出SFTP文件"""
    try:
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 连接服务器
        print(f"正在连接 {hostname}:{port} ...")
        ssh.connect(hostname, port=port, username=username, password=password, timeout=10)
        
        # 创建SFTP客户端
        sftp = ssh.open_sftp()
        
        print(f"\n{'='*80}")
        print(f"远程路径: {remote_path}")
        print(f"{'='*80}\n")
        
        # 列出文件
        file_list = []
        dir_list = []
        
        for item in sftp.listdir_attr(remote_path):
            file_info = {
                'name': item.filename,
                'type': '目录' if item.st_mode & 0o40000 else '文件',
                'size': format_file_size(item.st_size) if not (item.st_mode & 0o40000) else '',
                'mod_time': datetime.fromtimestamp(item.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'permissions': format_permissions(item.st_mode),
                'is_dir': item.st_mode & 0o40000
            }
            
            if file_info['is_dir']:
                dir_list.append(file_info)
            else:
                file_list.append(file_info)
        
        # 先显示目录
        print("【目录列表】")
        print(f"{'序号':<6}{'名称':<30}{'权限':<15}{'修改时间':<20}")
        print("-" * 80)
        for i, item in enumerate(dir_list, 1):
            print(f"{i:<6}{item['name']:<30}{item['permissions']:<15}{item['mod_time']:<20}")
        
        print(f"\n共 {len(dir_list)} 个目录\n")
        
        # 再显示文件
        print("【文件列表】")
        print(f"{'序号':<6}{'名称':<30}{'大小':<15}{'权限':<15}{'修改时间':<20}")
        print("-" * 80)
        for i, item in enumerate(file_list, 1):
            print(f"{i:<6}{item['name']:<30}{item['size']:<15}{item['permissions']:<15}{item['mod_time']:<20}")
        
        print(f"\n共 {len(file_list)} 个文件")
        print(f"\n总计: {len(dir_list)} 个目录, {len(file_list)} 个文件")
        
        # 关闭连接
        sftp.close()
        ssh.close()
        
        return dir_list, file_list
        
    except Exception as e:
        print(f"连接失败: {str(e)}")
        return [], []

if __name__ == "__main__":
    # 设备配置
    hostname = "192.168.226.146"
    username = "root"
    password = "root"
    port = 22
    remote_path = "/"
    
    print("="*80)
    print("远程设备文件列表查看工具")
    print(f"设备: {hostname}")
    print(f"用户: {username}")
    print(f"路径: {remote_path}")
    print("="*80)
    
    dir_list, file_list = list_sftp_files(hostname, username, password, port, remote_path)
