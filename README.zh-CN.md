# 腾讯VOD上传

[English](README.md)

腾讯VOD上传是一款轻量级 Windows 桌面工具，用于将本地视频直接上传到腾讯云点播（VOD）。它适合需要简洁上传流程、但不希望额外部署业务服务器的小型内部团队。

视频通过腾讯云官方服务端上传 SDK，直接从同事电脑传输到腾讯云 VOD。

## 功能

- 拖放视频与批量选择文件
- 顺序上传，避免多个大文件同时挤占网络
- 显示批次进度和单文件状态
- 展示腾讯云返回的 `FileId` 和 `MediaUrl`
- 单击成功后的 URL，使用默认浏览器打开
- 右键复制视频 URL 或 FileId
- 关闭软件后保留上传历史
- 可重新上传成功、失败、取消或中断的文件
- 可终止当前上传，不需要关闭软件
- 移除记录和清空历史前进行二次确认
- 支持可选的 `SubAppId`
- 使用 PyInstaller 打包为独立 Windows EXE

## 使用条件

- Windows 10 或更高版本
- 从源码运行时需要 Python 3.10 或更高版本
- 已开通腾讯云 VOD
- 具有 VOD 上传权限的 CAM API 密钥

## 腾讯云权限

创建仅支持编程访问的 CAM 子用户，并授予以下 VOD 操作：

```json
{
  "version": "2.0",
  "statement": [
    {
      "effect": "allow",
      "action": [
        "name/vod:ApplyUpload",
        "name/vod:CommitUpload"
      ],
      "resource": ["*"]
    }
  ]
}
```

请勿使用腾讯云主账号 API 密钥。

## 从源码运行

在项目目录中打开 PowerShell，执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run.ps1
```

脚本会创建独立虚拟环境、安装依赖并启动软件。

首次启动时，打开右侧的 **VOD 配置**，填写：

- `SecretId`
- `SecretKey`
- `SubAppId`：可选；上传到默认应用时留空
- 接入地域：通常为 `ap-guangzhou`

## 打包 Windows EXE

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

打包结果位于：

```text
dist\LiuguangVODUploader.exe
```

同事只需要这个 EXE，不需要安装 Python。

## 本地数据

软件会把用户相关数据保存在项目目录之外：

```text
%APPDATA%\TencentVODUploader\config.json
%APPDATA%\TencentVODUploader\history.json
```

如果勾选记住 SecretKey，它会保存在本机配置文件中。这适用于可信的内部环境，但该文件不是加密密码保险库。

上传历史只是本机记录，不会自动判断腾讯云中的视频之后是否被删除。

## 开源许可证

本项目使用 [MIT License](LICENSE)。
