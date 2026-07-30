# TencentVOD Uploader

[简体中文](README.zh-CN.md)

TencentVOD VOD Uploader is a lightweight Windows desktop application for uploading local video files directly to Tencent Cloud Video on Demand (VOD). It is designed for small internal teams that need a simple upload workflow without deploying an additional application server.

Videos are transferred directly from the user's computer to Tencent Cloud VOD through the official server upload SDK.

## Features

- Drag-and-drop and multi-file selection
- Sequential uploads to avoid saturating the network with multiple large files
- Upload progress and per-file status
- Displays the returned VOD `FileId` and `MediaUrl`
- Opens a successful media URL in the default browser with one click
- Copies media URLs and FileIds from the context menu
- Persists upload history across application restarts
- Retries successful, failed, cancelled, or interrupted uploads
- Terminates the current upload without closing the application
- Confirmation dialogs before removing records or clearing history
- Optional `SubAppId` support
- Standalone Windows executable packaging with PyInstaller

## Requirements

- Windows 10 or later
- Python 3.10 or later when running from source
- A Tencent Cloud VOD account
- A CAM API key with VOD upload permissions

## Tencent Cloud permissions

Create a CAM sub-user with programmatic access and grant only the following VOD operations:

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

Do not use a Tencent Cloud root account API key.

## Run from source

Open PowerShell in the project directory and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run.ps1
```

The script creates a local virtual environment, installs the dependencies, and launches the application.

On first launch, open **VOD Configuration** and enter:

- `SecretId`
- `SecretKey`
- `SubAppId` — optional; leave empty when uploading to the default application
- API region — normally `ap-guangzhou`

## Build a Windows executable

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

The standalone executable is created at:

```text
dist\TencentVODVODUploader.exe
```

The recipient does not need Python installed.

## Local data

The application stores user-specific data outside the repository:

```text
%APPDATA%\TencentVODUploader\config.json
%APPDATA%\TencentVODUploader\history.json
```

If the user chooses to remember the SecretKey, it is stored in the local configuration file. This is convenient for a trusted internal environment, but it is not an encrypted credential vault.

Upload history is local metadata. It does not automatically detect whether a video has later been deleted from Tencent Cloud.


## License

This project is licensed under the [MIT License](LICENSE).
