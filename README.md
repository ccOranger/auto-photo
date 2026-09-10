# Auto Photo — AI 照片主观审美筛选工具

基于深度学习的本地照片筛选工具，帮助摄影师从海量照片中快速挑出优质作品。

## 核心功能

- **技术废片初筛** — 自动检测模糊、过曝、欠曝，标记问题照片
- **闭眼智能判定** — 区分真闭眼与接吻、大笑等情感高光时刻，避免误删
- **相似照片聚类** — DINOv2 特征提取 + 余弦相似度分组，连拍照片只展示最佳一张
- **主观审美打分** — 对构图、色彩、光影三维度评分，辅助人工决策
- **三种浏览模式** — 网格浏览 / 左右擂台 PK（含滑动对比）/ 连拍分组折叠
- **AI 自动推荐** — 基于本地规则引擎一键标注保留/淘汰（技术废片淘汰 + 聚类最佳保留），无需外部大模型
- **批量操作** — 保留最佳 / 淘汰废片 / 清除标注，一键批量处理
- **撤销/重做** — Ctrl+Z 撤销上一步决策，支持连续撤销
- **排序与筛选** — 按评分、文件名、决策状态排序，底部工具栏一键切换全部/已保留/已淘汰
- **照片详情** — 双击或 Enter 打开详情弹窗，SVG 环形图展示各维度评分
- **会话管理** — 支持会话持久化保存、恢复和删除，关闭后可继续上次的筛选进度
- **无损导出** — 保留照片复制到目标文件夹（支持自定义路径）+ JSON/CSV 评分报告，原始文件不受影响
- **中文路径支持** — 完整兼容含中文等非 ASCII 字符的文件夹路径和文件名

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python · FastAPI · DINOv2 ViT-S/14 · OpenCV · scikit-learn |
| 前端 | React 18 · TypeScript · Vite |
| 算法 | Laplacian 方差（模糊）· 像素直方图（曝光）· Haar 级联（人脸/眼部/微笑）· EAR 纵横比（闭眼）· MAR 纵横比（笑容）· 余弦相似度聚类 · 启发式美学评分（边缘密度 / 饱和方差 / 亮度熵） |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- 约 500MB 磁盘空间（模型缓存 + Haar 级联文件）
- 无需 GPU，纯 CPU 可运行

### 安装依赖

后端使用虚拟环境隔离依赖（推荐使用国内镜像加速）：

```bash
# 后端（在 backend 目录下）
cd backend
python -m venv venv                                              # 创建虚拟环境
.\venv\Scripts\python.exe -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
.\venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 前端
cd frontend
npm install --registry=https://registry.npmmirror.com
```

### 启动

#### 方式一：一键启动（推荐）

Windows 下双击根目录的 `start.bat`，自动完成：

1. 启动后端服务（端口 8321），预加载 DINOv2 模型
2. 等待后端健康检查通过
3. 启动前端开发服务器（端口 5173）
4. 浏览器访问 `http://localhost:5173`

#### 方式二：手动启动

打开两个终端分别启动：

**终端 1 — 后端服务（端口 8321）**

```bash
cd backend
.\venv\Scripts\python.exe start_server.py
```

启动后会先加载 DINOv2 模型（需已下载到本地缓存，详见下方「首次运行」），加载完成后显示 `DINOv2 loaded, starting server...`，接着 Uvicorn 启动 HTTP 服务。

**终端 2 — 前端开发服务器（端口 5173）**

```bash
cd frontend
npm install    # 首次运行需安装依赖
npm run dev
```

前端通过 Vite 代理将 `/api` 请求转发到后端 `localhost:8321`。

#### 验证服务状态

```bash
# 检查后端是否就绪
curl http://localhost:8321/api/health

# 检查前端是否就绪
curl http://localhost:5173
```

#### 常见问题

| 问题 | 原因 | 解决方案 |
|---|---|---|
| `ModuleNotFoundError` | 后端依赖未安装或未用 venv | `cd backend && .\venv\Scripts\python.exe -m pip install -r requirements.txt` |
| `Cannot find module 'vite'` | 前端依赖未安装 | `cd frontend && npm install` |
| `无法加载文件 npm.ps1` | PowerShell 执行策略禁止脚本 | 使用 `npm.cmd` 代替 `npm`，或执行 `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| 端口 8321 被占用 | 旧进程未退出 | 关闭占用端口的进程或修改 `start_server.py` 中的端口 |
| 前端白屏/502 | 后端未启动 | 确保后端先启动，再访问前端 |
| `DINOv2 repo not found` | 模型未下载到本地缓存 | 见下方「首次运行」手动下载到 `~/.cache/torch/hub/` |

### 首次运行

后端启动时需要从本地缓存加载 DINOv2 模型（代码不会自动联网下载），需预先准备两个文件：

1. **DINOv2 源码仓库** → `~/.cache/torch/hub/facebookresearch_dinov2_main/`
   ```bash
   git clone --depth=1 https://gitclone.com/github.com/facebookresearch/dinov2.git ~/.cache/torch/hub/facebookresearch_dinov2_main
   ```
2. **DINOv2 权重**（~84MB）→ `~/.cache/torch/hub/checkpoints/dinov2_vits14_pretrain.pth`
   ```powershell
   $ProgressPreference='SilentlyContinue'
   Invoke-WebRequest -Uri "https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth" -OutFile "$env:USERPROFILE\.cache\torch\hub\checkpoints\dinov2_vits14_pretrain.pth"
   ```

下载完成后即可离线使用。美学评分使用内置启发式算法，无需额外模型下载。

## 使用流程

1. 点击"选择文件夹"按钮弹出 Windows 原生文件夹选择对话框，或手动输入路径
2. 点击"开始分析"，等待流水线完成：扫描 → 技术分析 → 特征提取（DINOv2，CPU 耗时较长）→ 聚类 → 评分
3. 选择筛选模式：
   - **网格浏览** — 缩略图视图，hover 左下角保留/淘汰按钮，支持排序和筛选，双击/Enter 打开详情弹窗
   - **对比模式** — 两张照片 PK（← 保留左图、→ 保留右图、Del 淘汰低分），按 S 切换滑动对比模式（拖拽分割线）
   - **连拍分组** — 每组只展示折叠的最佳照片，展开后 hover 可逐张保留/淘汰
4. 可选：点击「AI 推荐」一键自动标注保留/淘汰，或使用批量操作按钮
5. 导出时可选择目标文件夹（支持浏览按钮选择），自动在目标目录下生成带时间戳的导出目录

## 项目结构

```
auto-photo/
├── start.bat                     # 一键启动
├── backend/
│   ├── start_server.py           # 启动入口（预加载 DINOv2）
│   ├── requirements.txt
│   └── app/
│       ├── main.py               # FastAPI 应用（错误处理中间件）
│       ├── api/routes.py         # REST API（含会话管理/批量操作/自动推荐）
│       ├── core/                 # 配置与数据模型
│       └── services/
│           ├── image_utils.py    # Unicode 路径兼容的 imread
│           ├── scanner.py        # 文件夹递归扫描
│           ├── sharpness.py      # Laplacian 方差模糊检测
│           ├── exposure.py       # 过曝/欠曝检测
│           ├── face_detect.py    # 人脸/眼部/微笑检测（EAR+MAR 算法）
│           ├── feature_extract.py# DINOv2 离线特征提取
│           ├── cluster.py        # 余弦相似度聚类 + Laplacian 方差排名
│           ├── aesthetic.py      # 启发式美学评分（构图/色彩/光影）
│           └── pipeline.py       # 六阶段异步流水线 + LRU 会话管理
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx               # 主布局 + 状态管理 + 撤销/批量/排序
        ├── App.css               # 毛玻璃主题 + 动效系统
        ├── api/client.ts         # API 客户端（含批量操作/会话管理）
        └── components/
            ├── FolderSelector.tsx # 文件夹选择（浏览 + 手动输入）
            ├── ProgressBar.tsx    # 流光进度条
            ├── PhotoGrid.tsx      # 网格浏览（排序 + 详情弹窗）
            ├── ComparisonView.tsx # PK 模式 + 滑动对比
            ├── ClusterPanel.tsx   # 连拍分组（可交互保留/淘汰）
            ├── PhotoDetailModal.tsx # 照片详情（SVG 评分环形图）
            └── ExportPanel.tsx    # 导出（浏览选择目标文件夹）
```

## 配置

关键阈值在 [backend/app/core/config.py](backend/app/core/config.py) 中：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `blur_threshold_laplacian` | 100 | Laplacian 方差阈值，低于此值为模糊 |
| `overexposed_ratio` | 0.05 | 像素亮度 ≥250 的比例上限 |
| `underexposed_ratio` | 0.30 | 像素亮度 ≤30 的比例上限 |
| `eye_aspect_ratio_threshold` | 0.2 | 眼部纵横比阈值，低于此值为闭眼 |
| `emotion_smile_threshold` | 0.3 | 嘴部纵横比阈值，用于笑容检测 |
| `similarity_threshold` | 0.85 | 余弦相似度阈值，用于聚类分组 |
| `max_image_dimension` | 2048 | 特征提取前缩放长边最大像素数 |
| `max_concurrent_tasks` | CPU/2 (2~6) | CPU 并行任务数 |
| `max_sessions_in_memory` | 10 | 内存中最大保留会话数（LRU 淘汰） |

## 技术废片检测标准

四种技术问题（blur / overexposed / underexposed / eyes_closed）的判定原理：

### 模糊 (blur)

**算法**：图片转灰度 → Laplacian 二阶导数算子（突出边缘变化）→ 全图方差。方差越小说明边缘越少，图片越模糊。

**阈值**：`blur_threshold_laplacian = 100`，方差 < 100 判定为模糊。

### 过曝 (overexposed)

**算法**：统计灰度值 ≥ 250 的像素占全图比例。

**阈值**：`overexposed_ratio = 0.05`，超过 5% 即判定为过曝。

### 欠曝 (underexposed)

**算法**：统计灰度值 ≤ 30 的像素占全图比例。

**阈值**：`underexposed_ratio = 0.30`，超过 30% 即判定为欠曝。

### 闭眼 (eyes_closed)

**算法**：在检测到的人脸区域内定位眼部关键点，计算眼部纵横比（EAR）。EAR 低于阈值判定为闭眼。同时检测嘴部关键点计算纵横比（MAR），若闭眼 + 高 MAR（大笑、接吻等情感表达）同时出现，标记为情感高光时刻，不会归入技术废片。

**EAR 阈值**：`eye_aspect_ratio_threshold = 0.2`
**MAR 阈值**：`emotion_smile_threshold = 0.3`

---

## 性能说明

| 阶段 | 耗时（每张） | 说明 |
|---|---|---|
| 技术分析 | ~0.2 秒 | 模糊/曝光/人脸检测 |
| 特征提取 | 20~40 秒 | DINOv2 ViT-S/14 纯 CPU 推理 |
| 聚类 | <1 秒 | 全部照片完成后执行 |
| 评分 | ~0.5 秒 | 启发式算法，极快 |

几十张照片通常 10-30 分钟完成全流程，进度条实时显示当前阶段。

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/scan` | 启动文件夹扫描 |
| GET | `/api/progress/{session_id}` | 查询流水线进度 |
| GET | `/api/photos/{session_id}` | 获取照片列表（支持筛选） |
| GET | `/api/photos/{session_id}/{photo_id}/image` | 获取原图 |
| GET | `/api/thumbs/{session_id}/{photo_id}` | 获取缩略图（支持 `?size=` 参数） |
| PUT | `/api/photos/{session_id}/{photo_id}/decision` | 设置保留/淘汰/清除 |
| GET | `/api/clusters/{session_id}` | 获取聚类分组 |
| POST | `/api/export/{session_id}` | 导出照片与报告 |
| POST | `/api/auto-decide/{session_id}` | AI 自动推荐（本地规则引擎） |
| POST | `/api/batch-decide/{session_id}/{action}` | 批量操作（keep-best/discard-issues/clear） |
| GET | `/api/sessions` | 获取已保存的会话列表 |
| POST | `/api/sessions/{session_id}/restore` | 恢复历史会话 |
| DELETE | `/api/sessions/{session_id}` | 删除历史会话 |
| GET | `/api/browse-folder` | 弹出原生文件夹选择对话框 |
| GET | `/api/health` | 健康检查 |

## 快捷键

| 快捷键 | 功能 |
|---|---|
| `Ctrl+Z` | 撤销上一步决策 |
| `Enter` | 打开照片详情弹窗 |
| `Escape` | 关闭详情弹窗 |
| `S` | 对比模式下切换滑动对比 |
| `←` / `→` | 对比模式保留左/右图 |
| `Del` | 对比模式淘汰低分照片 |
