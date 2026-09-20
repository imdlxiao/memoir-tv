# 部署说明

作者：donglixiao

## 本地与局域网

需要 Python 3.10+；FFmpeg 可选，用于封面生成。

```json
{
  "media_root": "G:/dcim备份",
  "host": "127.0.0.1",
  "port": 8765,
  "ffmpeg": "C:/tools/ffmpeg/bin/ffmpeg.exe"
}
```

保存为不入库的 `config.local.json`，运行 `python -m memoir serve`。默认仅本机可访问 `http://127.0.0.1:8765`。`--port` 可改端口；Windows 快捷启动脚本使用默认端口。

手机、电视使用同一可信局域网时，显式运行 `python -m memoir serve --host 0.0.0.0`，访问 `http://素材电脑局域网IP:8765`。需要时在防火墙允许专用网络访问。当前没有账号权限，能访问地址的人可以查看和编辑记录，不要直接映射到公网。

## Nginx 静态部署

先扫描，再导出：

```powershell
python -m memoir scan
python -m memoir export --media-base /family-media/ --out dist
```

导出不复制原片，需在服务器上单独映射素材目录。示例：

```nginx
# Author: donglixiao
server {
    listen 8080;
    server_name _;
    root /srv/memoir/dist;
    index index.html;
    include mime.types;

    location / {
        try_files $uri $uri/ =404;
    }
    location /family-media/ {
        alias /mnt/family-media/;
        autoindex off;
    }
    location /data/ {
        add_header Cache-Control "no-cache";
    }
}
```

保持素材相对目录结构。Nginx 原生支持 Range，无需 Python 中转媒体。子路径部署时可设置相对 `--media-base ../family-media/`；HTML、CSS、JS、封面和索引均支持子路径。不要以 `file://` 打开网页。

静态模式修改保存在各自浏览器：导出备份 → 在本地服务导入 → 重新导出静态站点。浏览器清理站点数据会删除未备份的编辑。再次发布建议使用新目录整体替换，避免留下已删除素材的旧封面。公网使用必须先配置身份验证与 HTTPS。

## 协议参考

- [MDN：HTTP Range 请求](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests)：拖动视频时读取指定字节。
- [MDN：月份输入](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/month)：月份输入兼容性与 `YYYY-MM` 值。

## 故障排查

- 无封面：检查 FFmpeg 路径，管理页刷新会重试生成。
- 有封面但不能播放：浏览器未必支持原片编码，MOV/HEVC/HEIC/MKV 等可下载到本地播放器。
- 日期待补充：文件名没有明确年月日，可手动选择天或月。
- 新增文件看不到：管理回忆库中刷新，并等待封面准备完成。
- 手机打不开：检查局域网绑定、IP、专用网络防火墙和是否处于同一网络。
- 导入失败：使用程序导出的 JSON，最大 4 MB；失败不覆盖已有记录。
- 迁移目录：保留素材相对路径和 `data/memories.json`，不要同时重命名素材。
