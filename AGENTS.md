# 项目协作约定

- 产品名统一为 `memoir-tv`，界面、文档、页面标题和导出文件不得另取品牌名。
- 作者：donglixiao。新建 Python、JavaScript、CSS、HTML、SVG、Shell 代码文件必须在头部保留作者说明；JSON 不添加非法注释。
- `master` 是主分支，`develop` 是开发分支。功能在 `develop` 按职责提交，验证后合入 `master`。
- 提交信息使用 `feat：中文描述` 或 `refactor：中文描述`。
- 领域校验在 `memoir/domain.py`；持久化在 `memoir/storage.py`；扫描与封面在 `memoir/scanner.py`；HTTP 只负责协议适配。
- 前端按数据访问、状态查询、展示、编辑、播放、回忆库管理、电视导航拆分，不把所有功能放进 `app.js`。
- 原始素材只读。家庭索引、封面、编辑记录、本机配置、测试截图不得提交 Git。
- 未知拍摄时间保持未知；月精度不伪装成某一天。重新扫描不得覆盖人工编辑。
- 运行 `python -m unittest discover -s tests -v`；涉及交互时运行 `python tests/browser_smoke.py`。测试使用临时目录，不修改真实家庭记录。
- 前端格式遵循 `.prettierrc.json`。当前运行环境不依赖 Node、数据库或 Python 第三方包。
