"""
UI常量定义
消除魔法数字，统一界面配置
"""

from PyQt6.QtCore import Qt


class UIConstants:
    """UI常量定义"""
    
    # 列宽定义
    COLUMN_WIDTHS = {
        'device_name': 90,       # 设备名称列宽
        'device_status': 50,    # 设备状态列宽
        'protocol': 70,         # 协议列宽
        'ip_address': 100,      # IP地址列宽
        'port': 45,             # 端口列宽
        'operation': 80,        # 操作列宽
        'file_name': 120,       # 文件名列宽
        'file_type': 60,        # 文件类型列宽
        'mod_time': 130,         # 修改时间列宽
        'file_size': 70,        # 文件大小列宽
        'file_permissions': 70, # 文件权限列宽
        'progress_file': 120,   # 进度文件名列宽
        'progress_percent': 80, # 进度百分比列宽
    }
    
    # 系统文件过滤
    SYSTEM_FILES = [
        '.gitignore',           # Git忽略文件
        '*.pyc',                # Python编译文件
        '__pycache__',          # Python缓存目录
    ]
    
    # 布局配置
    LAYOUT_CONFIG = {
        'top_panel_ratio': 7,    # 上部面板高度比例
        'bottom_panel_ratio': 3, # 下部面板高度比例
        'left_panel_stretch': 25, # 左侧面板拉伸比例（设备管理，较小）
        'middle_panel_stretch': 50, # 中间面板拉伸比例（本地文件，较大）
        'right_panel_stretch': 50, # 右侧面板拉伸比例（远程文件，较大）
        'layout_spacing': 5,    # 布局间距
        'button_spacing': 5,    # 按钮间距
        'button_height': 24,    # 按钮高度
        'button_min_width': 60, # 按钮最小宽度
        'panel_margin_top': -13, # 面板上边距
    }
    
    # 传输状态颜色定义
    STATUS_COLORS = {
        'connected': Qt.GlobalColor.green,     # 已连接
        'disconnected': Qt.GlobalColor.red,    # 未连接
        'transferring': Qt.GlobalColor.blue,   # 传输中
        'paused': Qt.GlobalColor.yellow,      # 已暂停
        'completed': Qt.GlobalColor.green,     # 已完成
        'error': Qt.GlobalColor.red,           # 错误
        'queued': Qt.GlobalColor.black,        # 队列中
        'idle': Qt.GlobalColor.black,          # 空闲
    }
    
    # 默认值
    DEFAULTS = {
        'sftp_port': 22,           # SFTP默认端口
        'ftp_port': 21,            # FTP默认端口
        'chunk_size': 8192 * 1024, # 文件传输块大小
        'progress_update_interval': 300, # 进度更新间隔(ms)
        'timeout': 30,              # 连接超时时间(秒)
    }
    
    # 路径相关常量
    PATH_CONSTANTS = {
        'root_path': '/',          # 根路径
        'windows_root': 'C:\\',    # Windows根目录
        'current_directory': '.',   # 当前目录
        'parent_directory': '..',  # 父目录
    }
    
    # 文件类型映射
    FILE_TYPES = {
        'directory': '目录',
        'file': '文件',
        'symlink': '链接',
        'special': '特殊文件',
    }
    
    # 错误消息模板
    ERROR_MESSAGES = {
        'file_not_found': "文件不存在: {}",
        'permission_denied': "权限不足: {}",
        'connection_failed': "连接失败: {}",
        'transfer_failed': "传输失败: {}",
        'invalid_path': "无效路径: {}",
        'device_not_connected': "设备未连接",
        'no_protocol_config': "找不到协议配置: {}",
    }
    
    # 成功消息模板
    SUCCESS_MESSAGES = {
        'connection_success': "设备连接成功",
        'transfer_completed': "传输完成: {} 个文件",
        'delete_success': "删除成功: {} 个项目",
        'file_operation_success': "文件操作成功",
    }