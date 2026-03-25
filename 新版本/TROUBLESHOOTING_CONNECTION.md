# 连接卡死问题排查指南

## ⚠️ 重要提醒

**代码已修改，但必须重启程序才能生效！**

## 解决步骤

### 1️⃣ 重启程序（必须）

```bash
# 方法1: 在IDE中重启
# 停止程序运行（Ctrl+C 或点击停止按钮）
# 重新运行 main_app.py

# 方法2: 在命令行中
python main_app.py
```

### 2️⃣ 运行诊断测试

我创建了一个诊断脚本，用于测试连接功能：

```bash
python test_connection_thread.py
```

**测试说明：**
- 点击 **"🔴 主线程连接"** 按钮 → 界面会卡死5秒（演示问题）
- 点击 **"✅ 后台线程连接"** 按钮 → 界面正常响应（正确方案）

### 3️⃣ 检查调试输出

重启程序后，点击连接按钮，应该会在控制台看到调试信息：

```
[DEBUG] 开始执行连接切换
[DEBUG] 协议类型: ssh
[DEBUG] 当前连接状态: False
[DEBUG] 调用SSH连接
[DEBUG] connect_ssh 开始执行
[DEBUG] SSH配置: ip=192.168.1.100, port=22, username=root
[DEBUG] 准备创建连接线程
[DEBUG] 启动连接线程
[DEBUG] 连接线程已启动
```

**如果看不到这些信息 → 程序未重启！**

### 4️⃣ 检查设备配置

确保设备配置正确：

```bash
# 检查配置文件
cat device_configs.json
```

**必需字段：**
- `ip`: 设备IP地址
- `port`: SSH端口（通常是22）
- `username`: 用户名
- `password`: 密码

## 可能的问题

### 问题1: 程序未重启

**现象：** 点击连接仍然卡死，控制台无调试信息

**解决：**
```bash
# 完全关闭程序
# 重新运行
python main_app.py
```

### 问题2: Python缓存问题

**现象：** 修改代码但运行的是旧版本

**解决：**
```bash
# 清理Python缓存
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# 重新运行
python main_app.py
```

### 问题3: 配置文件错误

**现象：** 点击连接立即报错"未选择设备和协议"

**解决：**
1. 检查设备配置文件 `device_configs.json`
2. 确保至少有一个设备配置
3. 确保协议类型正确（ssh/serial）

### 问题4: Paramiko版本问题

**现象：** 连接超时过长

**解决：**
```bash
# 检查paramiko版本
python -c "import paramiko; print(paramiko.__version__)"

# 应该是 3.4.0 或更高
# 如果版本过低，升级：
pip install --upgrade paramiko
```

## 验证修复

### ✅ 成功标志

1. **点击连接后：**
   - 按钮立即变为禁用状态
   - 显示"正在连接..."提示
   - **界面可以移动、缩放**
   - **可以点击其他按钮**

2. **控制台输出：**
   ```
   [DEBUG] 启动连接线程
   [DEBUG] 连接线程已启动
   ```

3. **连接成功后：**
   - 显示"✓ SSH连接成功"
   - 终端可以输入命令

### ❌ 失败标志

1. 点击连接后界面完全冻结
2. 窗口无法移动
3. 任务管理器显示程序"无响应"

**→ 如果出现失败标志，说明程序未重启！**

## 快速诊断命令

```bash
# 1. 检查进程
ps aux | grep python | grep main_app

# 2. 杀死旧进程
pkill -f main_app.py

# 3. 清理缓存
find . -type d -name __pycache__ -exec rm -rf {} +

# 4. 重新运行
python main_app.py
```

## 测试用例

### 测试1: 网络超时
- 输入错误的IP（如192.168.999.999）
- 点击连接
- **预期：** 界面保持响应，5秒后显示连接失败

### 测试2: 正常连接
- 输入正确的设备配置
- 点击连接
- **预期：** 显示"正在连接..."，几秒后显示连接成功

### 测试3: 重复连接
- 连接失败后再次点击连接
- **预期：** 可以重新尝试连接

## 如果问题依然存在

### 收集诊断信息

1. **Python版本：**
   ```bash
   python --version
   ```

2. **PyQt6版本：**
   ```bash
   python -c "import PyQt6; print(PyQt6.QtCore.PYQT_VERSION_STR)"
   ```

3. **Paramiko版本：**
   ```bash
   python -c "import paramiko; print(paramiko.__version__)"
   ```

4. **操作系统：**
   ```bash
   # Windows
   systeminfo | findstr /B /C:"OS Name"
   
   # Linux
   cat /etc/os-release
   ```

5. **错误日志：**
   - 查看控制台输出
   - 查看 `log/` 目录下的日志文件

### 联系支持

如果问题依然存在，请提供：
1. 上述诊断信息
2. 控制台完整输出
3. `device_configs.json` 配置（隐藏密码）
4. 点击连接时的具体现象描述

## 临时回退方案

如果新版本有问题，可以使用旧的连接方式：

1. 打开 `test_execution/test_execution_page.py`
2. 找到 `connect_ssh()` 方法
3. 将 `ConnectionThread` 相关代码注释掉
4. 取消注释旧的直接连接代码

**注意：** 这会导致界面卡死，仅用于紧急情况！
