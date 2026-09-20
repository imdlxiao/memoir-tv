# 测试素材

作者：donglixiao

`playback.mp4` 为程序生成的 30 秒、64×64 像素松绿色静音画面，无家庭素材、第三方内容或真实拍摄信息。用于隔离浏览器测试中的解码、跳转、进度恢复、倍速与连续播放。

生成方式（FFmpeg 编译需包含 libx264）：

```sh
# Author: donglixiao
ffmpeg -f lavfi -i color=c=0x496d51:s=64x64:r=2:d=30 -c:v libx264 -preset ultrafast -crf 35 -pix_fmt yuv420p -an -movflags +faststart playback.mp4
```

运行测试直接使用已提交的小样本，不需要安装 FFmpeg。

`capture.mov` 由上述静音画面复制并通过 ExifTool 写入**合成**的 Test Camera、2024-02-29 11:03:02+08:00、22.3°N / 114.17°E 元信息；不来自真实拍摄。再通过 FFmpeg `-map_metadata 0 -c copy -movflags use_metadata_tags` 封装，使 `moov` 在 `mdat` 之后，回归验证视频尾部元数据不会漏读。文件仅约 3 KB。ExifTool 集成测试还检查读取前后原片字节未发生变化。
