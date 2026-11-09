# 汽车之家配置采集器

单机版本地 Web 工具。双击程序后自动打开浏览器，输入汽车之家车系网址，抓取全部在售、停售车型，导出为带筛选器、冻结表头和分年工作表的 Excel。

## 客户使用方式

客户只需要运行一个 Windows 安装包：

```text
AutohomeSpecExporter_Setup_v1.0.1.exe
```

安装后双击“汽车之家配置采集器”桌面图标：

1. 程序在后台启动本地服务
2. 浏览器自动打开 `http://127.0.0.1:8765`
3. 粘贴汽车之家车系网址
4. 等待抓取完成
5. 点击“导出全部 Excel”

客户不需要安装 Python、Node.js、Docker 或其他环境。

## 本地开发

### macOS / Linux

```bash
cd autohome_exporter
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

也可以直接执行：

```bash
./run_local.command
```

### Windows

双击 `run_local.bat`。

## 构建 Windows 安装包

PyInstaller 不支持从 macOS 交叉编译 Windows 程序，因此**必须在 Windows 环境构建**。

### 构建环境

- Windows 10/11 x64
- Python 3.11 x64
- Inno Setup 6

### 一键构建

双击：

```text
build_windows.bat
```

构建产物：

```text
dist\AutohomeSpecExporter\AutohomeSpecExporter.exe
dist\AutohomeSpecExporter_Setup_v1.0.1.exe
dist\AutohomeSpecExporter_Portable_v1.0.1.zip
```

正式发给客户时推荐发送：

```text
AutohomeSpecExporter_Setup_v1.0.1.exe
```

不要只发送 `AutohomeSpecExporter.exe`，因为 PyInstaller 使用 one-folder 模式，运行还需要旁边的 `_internal` 文件。

## GitHub Actions 构建

工作流文件：

```text
.github/workflows/build-windows.yml
```

将整个项目推到 GitHub 后，在 Actions 中手动运行：

```text
Build Autohome Spec Exporter for Windows
```

构建完成后下载 `AutohomeSpecExporter-Windows` artifact，里面包含安装包和便携版 ZIP。

## 数据说明

- `specstatus=20` / `30`：在售
- `specstatus=40`：停售
- `specstatus=10`：待售，默认不导出
- 抓取结果默认缓存 12 小时
- 数据保存在用户目录：
  - Windows：`%LOCALAPPDATA%\AutohomeSpecExporter`
  - macOS：`~/Library/Application Support/AutohomeSpecExporter`

## 安全设计

- 服务只监听 `127.0.0.1`，其他电脑无法访问
- 只接受 `autohome.com.cn` 域名并提取车系 ID
- 不把用户输入直接当作任意网络请求地址
- 单用户单任务串行抓取，避免并发过高
- 抓取失败保留日志，不向前端输出内部堆栈

## 已知限制

- 汽车之家接口结构未来可能变化，需要按实际情况调整
- 如果汽车之家要求验证码，程序不会尝试绕过
- 未签名的 Windows exe 可能触发 SmartScreen 提示，正式交付建议进行代码签名


## 发布到 GitHub

在 GitHub 创建一个空仓库，然后执行：

```bash
./publish_to_github.sh git@github.com:你的账号/autohome-spec-exporter.git
```

推送到 `main` 后会自动触发：

```text
Build Autohome Spec Exporter for Windows
```

Actions 完成后下载 artifact：

```text
AutohomeSpecExporter-Windows
```
