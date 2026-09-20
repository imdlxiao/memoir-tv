# memoir-tv

把家庭视频、照片和故事放在一起的私人回忆录。暖白与松绿色的时间流，适配电脑、手机与客厅大屏。素材留在原目录，扫描生成静态索引，补充的故事独立保存。

## 功能

- Twitter 式纵向回忆流、网格视图、时间排序和分批加载。
- 视频与照片展示、原片播放、进度拖动、全屏，不支持的格式可下载原片。
- 拍摄时间支持 **精确到天 / 大约某月 / 暂时未知**，自动识别文件名里的明确日期。
- 标题、故事、地点、标签、珍藏；搜索与年份、地点、标签组合筛选。
- 批量整理日期、地点、标签与珍藏，标签可追加／替换／移除；整批验证后一次写入。
- 月份筛选、往年今日与往年同月、按当前筛选随机重温。
- 视频进度记忆与「接着看」、倍速、单段循环、照片放大和可暂停的自动放映。
- 原片信息与下载；自动记住网格／列表、排序和播放偏好。
- 浅色 / 深色模式、手机底部导航、电视方向键导航与连续放映。
- 递归扫描、封面缓存、手动刷新；重新扫描不覆盖人工编辑。
- 编辑记录导入导出、原子写入与上一版自动备份。
- 无第三方运行依赖，支持本地服务和纯静态导出。

## 启动

需要 Python 3.10+。FFmpeg 可选，用于生成封面。

1. 复制 `config.example.json` 为 `config.local.json`。
2. 配置素材目录 `media_root` 和 `ffmpeg` 可执行文件路径。
3. 双击 `START_MEMOIR.cmd`，或运行：

```powershell
python -m memoir serve
```

访问 **http://127.0.0.1:8765**。首次启动先快速生成索引，后台准备封面。也可预先运行 `python -m memoir scan`。

当前电脑已配置 `G:/dcim备份`，本机配置与家庭数据不提交 Git。本地服务在刷新页面时核对实际目录；页面停留期间每 5 秒同步新增或移出的素材，编辑或播放时暂缓更新界面。也可在「管理回忆库」手动刷新封面。素材由文件系统管理，不提供网页上传。

### 手机与电视

设备处于同一可信局域网时，在素材电脑运行：

```powershell
python -m memoir serve --host 0.0.0.0
```

访问 `http://素材电脑局域网IP:8765`。在「客厅放映室」中，方向键移动焦点、确认键打开、Esc 返回；播放器使用原生控件，视频结束继续下一段，照片每 8 秒切换。

默认仅监听本机。局域网模式无账号权限，可访问地址的人能查看和编辑记录；不要直接暴露到公网。

## 静态读取与发布

`data/catalog.json` 是扫描索引，`data/memories.json` 是独立编辑记录。服务只是提供原片和 JSON 编辑接口，不需要数据库。视频使用 HTTP Range，不会一次读取整个大文件。

完全静态部署：

```powershell
python -m memoir export --media-base /family-media/ --out dist
```

将 `dist` 放到静态服务器，把 `/family-media/` 映射到原始素材目录。媒体前缀也可使用 NAS HTTP(S) 地址或相对地址，保留素材相对目录结构。**导出不复制原片**。以 HTTP 访问，不能双击 HTML 使用 `file://`。

静态模式编辑仅保存于当前浏览器，导出编辑备份后，在素材电脑导入、重新发布即可合并。本地服务模式写入同一份磁盘记录，多设备重新加载后共享更新。详见 [部署说明](docs/DEPLOYMENT.md)。

## 素材与备份

- 扫描视频：MP4、MOV、M4V、WebM、MKV、AVI。
- 扫描照片：JPG、PNG、WebP、GIF、AVIF、HEIC、HEIF。
- 能否直接播放取决于浏览器解码能力；MOV/HEVC、HEIC、部分 MKV/AVI 可能需要下载原片。不会自动转码全部大型素材。
- 未知日期、地点和标签明确显示待补充，不虚构家庭故事。
- 编辑备份不含原片；完整备份需同时保留素材、`data/memories.json` 和本机配置。
- ID 来自相对路径，移动或重命名素材会成为新条目，旧编辑记录保留但不会自动关联。
- `data/memories.backup.json` 保留上一次写入前的记录，不代替长期备份。

## 代码结构

```text
memoir/
  domain.py        日期、字段、扩展名与校验
  storage.py       JSON 仓储、锁、原子写入、备份
  scanner.py       只读扫描与封面缓存
  library.py       目录同步、后台预览任务与索引一致性
  exporter.py      合并数据与纯静态站点发布
  http.py          静态服务、媒体 Range、编辑 API
  __main__.py      启动、扫描与静态发布 CLI
web/
  js/             数据、状态、回忆流、编辑、播放、电视导航
  styles/         设计变量、响应式布局、组件样式
  assets/         原创 SVG 品牌、图标和插画
tests/            领域、存储、协议和隔离浏览器验收
docs/             架构与部署说明
```

无需 Node、数据库和前端打包。NAS / 数据库 / 多人权限演进边界见 [架构文档](docs/ARCHITECTURE.md)。

## 验证与开发

```powershell
python -m unittest discover -s tests -v
python -m pip install -r requirements-dev.txt
python tests/browser_smoke.py
python tests/browser_features.py
```

浏览器验收需已安装 Chrome，使用临时素材与记录，不修改真实家庭数据。覆盖日期编辑与持久化、搜索、筛选、珍藏、照片、备份恢复、电视、深色模式和 360/390/768/1440/1920 宽度，以及子路径静态部署、静态编辑持久化和不支持的视频格式回退。验收结果见 [VALIDATION.md](docs/VALIDATION.md)。

GitHub Actions 同时运行后端与浏览器验收，使用自动安装的 Chromium。新增功能的操作说明见 [FEATURES.md](docs/FEATURES.md)。播放进度仅保存在当前浏览器，不属于家庭元数据备份。

主分支 `master`，开发分支 `develop`。按职责使用 `feat：中文描述` / `refactor：中文描述` 提交。作者：**donglixiao**。
