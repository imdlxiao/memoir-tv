# 地图依赖与许可

- `leaflet/`：Leaflet 1.9.4，BSD-2-Clause，保留原作者与 [LICENSE](leaflet/LICENSE)。来源 https://leafletjs.com/download.html ，本地托管 JS/CSS，不使用运行时 CDN。使用自定义缩略图与按钮，不使用默认 PNG marker/layer 图标。
- `natural-earth/land.geojson`：Natural Earth 1:110m land（`ne_110m_land.geojson`），来自维护者仓库 https://github.com/nvkelso/natural-earth-vector 。公有领域，许可 https://www.naturalearthdata.com/about/terms-of-use/ 。仅作离线大陆轮廓概览，不提供街道或精确边界。
- 街道图使用 https://tile.openstreetmap.org/{z}/{x}/{y}.png ，仅用户点击后按视口请求。保留 OpenStreetMap contributors 署名。遵守 https://operations.osmfoundation.org/policies/tiles/ ，无批量下载、离线瓦片缓存或预抓取。自动化测试拦截外部瓦片，不向公共服务发送测试流量。
- 第三方文件保留原始作者与许可，不将其署名改为项目作者。
