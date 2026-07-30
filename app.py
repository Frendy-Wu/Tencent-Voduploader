from __future__ import annotations

import json
import multiprocessing as mp
import os
import queue
import sys
import threading
import time
import tkinter as tk
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".m4v", ".mkv", ".avi", ".wmv", ".flv", ".webm",
    ".mpeg", ".mpg", ".ts", ".mts", ".m2ts",
}

COLORS = {
    "bg": "#0B0E14", "sidebar": "#0D1119", "surface": "#121722",
    "surface_2": "#171D2A", "hover": "#1D2636", "border": "#263044",
    "text": "#EAF2FF", "muted": "#8290A8", "blue": "#69D2FF",
    "blue_2": "#5794FF", "violet": "#8B7CFF", "success": "#55D68B",
    "danger": "#FF7188",
}


@dataclass
class VodConfig:
    secret_id: str = ""
    secret_key: str = ""
    sub_app_id: int = 0
    region: str = "ap-guangzhou"


def config_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "TencentVODUploader" / "config.json"


def history_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "TencentVODUploader" / "history.json"


def load_config() -> VodConfig:
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
        return VodConfig(
            secret_id=str(data.get("secret_id", "")),
            secret_key=str(data.get("secret_key", "")),
            sub_app_id=int(data.get("sub_app_id", 0)),
            region=str(data.get("region", "ap-guangzhou")),
        )
    except (OSError, ValueError, TypeError):
        return VodConfig()


def save_config(config: VodConfig, remember_secret: bool) -> None:
    data = asdict(config)
    if not remember_secret:
        data["secret_key"] = ""
    target = config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def upload_one_process(
    config_data: dict, file_path: str, result_queue: mp.Queue
) -> None:
    """Upload one file in an isolated process so it can be terminated safely."""
    try:
        from qcloud_vod.model import VodUploadRequest
        from qcloud_vod.vod_upload_client import VodUploadClient

        client = VodUploadClient(
            config_data["secret_id"], config_data["secret_key"]
        )
        request = VodUploadRequest()
        request.MediaFilePath = file_path
        request.MediaName = Path(file_path).stem
        if config_data.get("sub_app_id"):
            request.SubAppId = int(config_data["sub_app_id"])
        response = client.upload(config_data["region"], request)
        result_queue.put(
            ("succeeded", str(response.FileId or ""), str(response.MediaUrl or ""))
        )
    except Exception as exc:
        result_queue.put(("failed", str(exc)))


class ConfigDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, current: VodConfig) -> None:
        super().__init__(parent)
        self.result: VodConfig | None = None
        self.title("腾讯云 VOD 配置")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.transient(parent)
        self.grab_set()

        self.secret_id = tk.StringVar(value=current.secret_id)
        self.secret_key = tk.StringVar(value=current.secret_key)
        self.sub_app_id = tk.StringVar(
            value=str(current.sub_app_id) if current.sub_app_id else ""
        )
        self.region = tk.StringVar(value=current.region)
        self.remember = tk.BooleanVar(value=bool(current.secret_key))

        frame = tk.Frame(self, bg=COLORS["bg"], padx=24, pady=22)
        frame.grid(sticky="nsew")
        tk.Label(
            frame, text="VOD 配置", bg=COLORS["bg"], fg=COLORS["text"],
            font=("Microsoft YaHei UI", 16, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))
        fields = [
            ("SecretId", self.secret_id, False),
            ("SecretKey", self.secret_key, True),
            ("SubAppId", self.sub_app_id, False),
            ("接入地域", self.region, False),
        ]
        for row, (label, variable, masked) in enumerate(fields):
            tk.Label(
                frame, text=label, bg=COLORS["bg"], fg=COLORS["muted"],
                font=("Microsoft YaHei UI", 9)
            ).grid(
                row=row + 1, column=0, sticky="w", padx=(0, 14), pady=7
            )
            entry = tk.Entry(
                frame, textvariable=variable, width=46, bg=COLORS["surface_2"],
                fg=COLORS["text"], insertbackground=COLORS["blue"], relief="flat",
                highlightthickness=1, highlightbackground=COLORS["border"],
                highlightcolor=COLORS["blue_2"], font=("Segoe UI", 10)
            )
            if masked:
                entry.configure(show="●")
            entry.grid(row=row + 1, column=1, sticky="ew", pady=7, ipady=8, ipadx=8)

        tk.Checkbutton(
            frame,
            text="在当前 Windows 用户配置中保存 SecretKey",
            variable=self.remember,
            bg=COLORS["bg"], fg=COLORS["muted"], activebackground=COLORS["bg"],
            activeforeground=COLORS["text"], selectcolor=COLORS["surface_2"],
            font=("Microsoft YaHei UI", 9)
        ).grid(row=5, column=1, sticky="w", pady=(6, 8))
        tk.Label(
            frame,
            text="SubAppId 可留空（默认应用）；仅上传到指定 VOD 应用时填写。",
            bg=COLORS["bg"], fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 8)
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 16))

        buttons = tk.Frame(frame, bg=COLORS["bg"])
        buttons.grid(row=7, column=0, columnspan=2, sticky="e")
        tk.Button(
            buttons, text="取消", command=self.destroy, bg=COLORS["surface_2"],
            fg=COLORS["muted"], activebackground=COLORS["hover"],
            activeforeground=COLORS["text"], relief="flat", bd=0,
            font=("Microsoft YaHei UI", 9), padx=18, pady=8
        ).pack(
            side="left", padx=(0, 8)
        )
        tk.Button(
            buttons, text="保存", command=self._save, bg=COLORS["blue_2"],
            fg="#FFFFFF", activebackground=COLORS["violet"],
            activeforeground="#FFFFFF", relief="flat", bd=0,
            font=("Microsoft YaHei UI", 9, "bold"), padx=20, pady=8
        ).pack(side="left")
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_visibility()
        self.focus_set()

    def _save(self) -> None:
        sub_app_id_text = self.sub_app_id.get().strip()
        try:
            sub_app_id = int(sub_app_id_text) if sub_app_id_text else 0
            if sub_app_id < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "配置错误", "SubAppId 请留空，或填写大于 0 的数字。", parent=self
            )
            return
        result = VodConfig(
            secret_id=self.secret_id.get().strip(),
            secret_key=self.secret_key.get().strip(),
            sub_app_id=sub_app_id,
            region=self.region.get().strip(),
        )
        missing = [
            name
            for name, value in (
                ("SecretId", result.secret_id),
                ("SecretKey", result.secret_key),
                ("接入地域", result.region),
            )
            if not value
        ]
        if missing:
            messagebox.showwarning(
                "配置不完整", "请填写：" + "、".join(missing), parent=self
            )
            return
        try:
            save_config(result, self.remember.get())
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)
            return
        self.result = result
        self.destroy()


class VodUploaderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("流光上传")
        self.root.geometry("1280x800")
        self.root.minsize(1000, 650)
        self.root.configure(bg=COLORS["bg"])
        self.config = load_config()
        self.jobs: dict[str, str] = {}
        self.events: queue.Queue[tuple] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.cancel_current_requested = False
        self.active_process: mp.Process | None = None

        self._configure_style()
        self._build_ui()
        self.load_history()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.process_events)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Dark.Treeview", background=COLORS["surface"],
            fieldbackground=COLORS["surface"], foreground=COLORS["text"],
            rowheight=44, borderwidth=0, font=("Microsoft YaHei UI", 9)
        )
        style.map(
            "Dark.Treeview", background=[("selected", "#202E47")],
            foreground=[("selected", COLORS["text"])]
        )
        style.configure(
            "Dark.Treeview.Heading", background=COLORS["surface_2"],
            foreground=COLORS["muted"], relief="flat", borderwidth=0,
            padding=(10, 12), font=("Microsoft YaHei UI", 9, "bold")
        )
        style.map("Dark.Treeview.Heading", background=[("active", COLORS["surface_2"])])
        style.configure(
            "Glow.Horizontal.TProgressbar", troughcolor="#202838",
            background=COLORS["blue_2"], borderwidth=0, thickness=7
        )

    def _build_ui(self) -> None:
        shell = tk.Frame(self.root, bg=COLORS["bg"])
        shell.pack(fill="both", expand=True)

        content = tk.Frame(shell, bg=COLORS["bg"])
        content.pack(fill="both", expand=True)
        topbar = tk.Frame(
            content, bg=COLORS["sidebar"], height=54, highlightthickness=1,
            highlightbackground="#1B2330"
        )
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        tk.Label(
            topbar, text="●  本地直连", bg=COLORS["sidebar"],
            fg=COLORS["success"], font=("Microsoft YaHei UI", 9)
        ).pack(side="right", padx=22)

        main = tk.Frame(content, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=22, pady=20)
        hero = tk.Frame(main, bg=COLORS["bg"], height=300)
        hero.pack(fill="x")
        hero.pack_propagate(False)

        upload_panel = tk.Frame(
            hero, bg=COLORS["surface"], highlightthickness=1,
            highlightbackground=COLORS["border"]
        )
        upload_panel.pack(side="left", fill="both", expand=True, padx=(0, 14))
        tk.Label(
            upload_panel, text="视频素材上传", bg=COLORS["surface"],
            fg=COLORS["text"], font=("Microsoft YaHei UI", 16, "bold")
        ).pack(anchor="w", padx=24, pady=(20, 0))
        self.drop_canvas = tk.Canvas(
            upload_panel, bg="#101622", highlightthickness=0, cursor="hand2"
        )
        self.drop_canvas.pack(fill="both", expand=True, padx=24, pady=(14, 20))
        self.drop_canvas.bind("<Configure>", self.draw_drop_zone)
        self.drop_canvas.bind("<Button-1>", lambda _event: self.choose_files())
        if DND_FILES:
            self.drop_canvas.drop_target_register(DND_FILES)
            self.drop_canvas.dnd_bind("<<Drop>>", self.on_drop)

        side_panel = tk.Frame(
            hero, bg=COLORS["surface"], width=300, highlightthickness=1,
            highlightbackground=COLORS["border"]
        )
        side_panel.pack(side="right", fill="y")
        side_panel.pack_propagate(False)
        vod_header = tk.Frame(side_panel, bg=COLORS["surface"])
        vod_header.pack(fill="x", padx=22, pady=(18, 10))
        tk.Label(
            vod_header, text="VOD 配置", bg=COLORS["surface"],
            fg=COLORS["text"], font=("Microsoft YaHei UI", 13, "bold")
        ).pack(side="left")
        self.config_button = tk.Button(
            vod_header, text="修改", command=self.open_config,
            bg=COLORS["surface"], fg=COLORS["blue"],
            activebackground=COLORS["surface"], activeforeground=COLORS["text"],
            relief="flat", bd=0, cursor="hand2",
            font=("Microsoft YaHei UI", 9, "bold"), padx=0
        )
        self.config_button.pack(side="right")

        region_row = tk.Frame(side_panel, bg=COLORS["surface_2"])
        region_row.pack(fill="x", padx=22, pady=(0, 7), ipady=7)
        tk.Label(
            region_row, text="接入地域", bg=COLORS["surface_2"],
            fg=COLORS["muted"], font=("Microsoft YaHei UI", 8)
        ).pack(side="left", padx=10)
        self.region_value = tk.Label(
            region_row, text="ap-guangzhou", bg=COLORS["surface_2"],
            fg=COLORS["text"], font=("Segoe UI", 9)
        )
        self.region_value.pack(side="right", padx=10)

        app_row = tk.Frame(side_panel, bg=COLORS["surface_2"])
        app_row.pack(fill="x", padx=22, pady=(0, 12), ipady=7)
        tk.Label(
            app_row, text="上传应用", bg=COLORS["surface_2"],
            fg=COLORS["muted"], font=("Microsoft YaHei UI", 8)
        ).pack(side="left", padx=10)
        self.app_value = tk.Label(
            app_row, text="默认应用", bg=COLORS["surface_2"],
            fg=COLORS["text"], font=("Microsoft YaHei UI", 9)
        )
        self.app_value.pack(side="right", padx=10)

        overview_row = tk.Frame(side_panel, bg=COLORS["surface"])
        overview_row.pack(fill="x", padx=22)
        tk.Label(
            overview_row, text="当前批次", bg=COLORS["surface"],
            fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)
        ).pack(side="left")
        self.summary_count = tk.Label(
            side_panel, text="0", bg=COLORS["surface"], fg=COLORS["blue"],
            font=("Segoe UI", 27, "bold")
        )
        self.summary_count.pack(anchor="w", padx=20, pady=(2, 0))
        self.summary_status = tk.Label(
            side_panel, text="准备就绪", bg=COLORS["surface"],
            fg=COLORS["text"], font=("Microsoft YaHei UI", 9, "bold")
        )
        self.summary_status.pack(anchor="w", padx=22, pady=(0, 6))
        self.progress = ttk.Progressbar(
            side_panel, mode="determinate", style="Glow.Horizontal.TProgressbar"
        )
        self.progress.pack(fill="x", padx=22)
        self.progress_text = tk.Label(
            side_panel, text="0 / 0", bg=COLORS["surface"],
            fg=COLORS["muted"], font=("Segoe UI", 9)
        )
        self.progress_text.pack(anchor="e", padx=22, pady=(5, 0))
        self.refresh_config_summary()

        queue_header = tk.Frame(main, bg=COLORS["bg"])
        queue_header.pack(fill="x", pady=(18, 9))
        tk.Label(
            queue_header, text="上传队列", bg=COLORS["bg"], fg=COLORS["text"],
            font=("Microsoft YaHei UI", 13, "bold")
        ).pack(side="left")
        self.status = tk.StringVar(value="尚未添加文件")
        tk.Label(
            queue_header, textvariable=self.status, bg=COLORS["bg"],
            fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)
        ).pack(side="left", padx=14)

        self.upload_button = self._button(
            queue_header, "开始上传", self.start_upload, COLORS["blue_2"],
            "#FFFFFF", bold=True
        )
        self.upload_button.pack(side="right")
        self.cancel_button = self._button(
            queue_header, "终止上传", self.cancel_upload,
            COLORS["surface_2"], COLORS["muted"]
        )
        self.cancel_button.configure(state="disabled")
        self.cancel_button.pack(side="right", padx=(0, 8))
        self.clear_button = self._button(
            queue_header, "清空", self.clear, COLORS["bg"], COLORS["muted"]
        )
        self.clear_button.pack(side="right", padx=(0, 4))
        self.remove_button = self._button(
            queue_header, "移除选中", self.remove_selected,
            COLORS["bg"], COLORS["muted"]
        )
        self.remove_button.pack(side="right")
        self.add_button = self._button(
            queue_header, "＋ 添加视频", self.choose_files,
            COLORS["bg"], COLORS["blue"], bold=True
        )
        self.add_button.pack(side="right")

        table_frame = tk.Frame(
            main, bg=COLORS["surface"], highlightthickness=1,
            highlightbackground=COLORS["border"]
        )
        table_frame.pack(fill="both", expand=True)
        columns = ("file", "size", "status", "file_id", "url")
        self.table = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="extended",
            style="Dark.Treeview"
        )
        headings = {
            "file": "文件",
            "size": "大小",
            "status": "状态",
            "file_id": "FileId",
            "url": "视频 URL",
        }
        widths = {"file": 250, "size": 90, "status": 100, "file_id": 170, "url": 360}
        for name in columns:
            self.table.heading(name, text=headings[name])
            self.table.column(
                name,
                width=widths[name],
                minwidth=70,
                stretch=name in {"file", "url"},
            )
        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.table.yview
        )
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.bind("<Button-3>", self.show_context_menu)
        self.table.bind("<ButtonRelease-1>", self.open_url_from_click)
        self.table.bind("<Motion>", self.update_table_cursor)

        self.table.tag_configure("success", foreground=COLORS["success"])
        self.table.tag_configure("failed", foreground=COLORS["danger"])
        self.table.tag_configure("active", foreground=COLORS["blue"])

    def _button(
        self, parent, text: str, command, background: str, foreground: str,
        bold: bool = False
    ) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, bg=background, fg=foreground,
            activebackground=COLORS["hover"], activeforeground=COLORS["text"],
            disabledforeground="#4F596A", relief="flat", bd=0, cursor="hand2",
            font=("Microsoft YaHei UI", 9, "bold" if bold else "normal"),
            padx=15, pady=8
        )

    def draw_drop_zone(self, _event=None) -> None:
        canvas = self.drop_canvas
        canvas.delete("all")
        width, height = max(1, canvas.winfo_width()), max(1, canvas.winfo_height())
        canvas.create_rectangle(
            8, 8, width - 8, height - 8, outline="#355A8C",
            width=1, dash=(7, 6)
        )
        cx, cy = width / 2, height / 2 - 20
        canvas.create_oval(
            cx - 34, cy - 25, cx + 34, cy + 25,
            outline=COLORS["blue_2"], width=3
        )
        canvas.create_line(
            cx, cy + 11, cx, cy - 15, fill=COLORS["blue"], width=4,
            arrow=tk.LAST, arrowshape=(10, 12, 5)
        )
        canvas.create_text(
            cx, cy + 56, text="拖放视频到这里", fill=COLORS["text"],
            font=("Microsoft YaHei UI", 14, "bold")
        )
        canvas.create_text(
            cx, cy + 83, text="或点击选择视频 · 支持批量添加",
            fill=COLORS["muted"], font=("Microsoft YaHei UI", 9)
        )

    def refresh_config_summary(self) -> None:
        if not hasattr(self, "region_value"):
            return
        self.region_value.configure(text=self.config.region or "未配置")
        app_text = (
            f"应用 {self.config.sub_app_id}"
            if self.config.sub_app_id
            else "默认应用"
        )
        self.app_value.configure(text=app_text)

    def save_history(self) -> None:
        records = []
        for item_id in self.table.get_children():
            records.append(
                {
                    "path": self.jobs.get(item_id, ""),
                    "file": self.table.set(item_id, "file"),
                    "size": self.table.set(item_id, "size"),
                    "status": self.table.set(item_id, "status"),
                    "file_id": self.table.set(item_id, "file_id"),
                    "url": self.table.set(item_id, "url"),
                }
            )
        target = history_path()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(records, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def load_history(self) -> None:
        try:
            records = json.loads(history_path().read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            records = []
        for record in records:
            status = str(record.get("status", "等待上传"))
            if status in {"上传中", "正在终止"}:
                status = "已中断"
            item_id = self.table.insert(
                "",
                "end",
                values=(
                    str(record.get("file", "")),
                    str(record.get("size", "")),
                    status,
                    str(record.get("file_id", "")),
                    str(record.get("url", "")),
                ),
            )
            self.jobs[item_id] = str(record.get("path", ""))
            if status == "上传成功":
                self.table.item(item_id, tags=("success",))
            elif status in {"上传失败", "已取消", "已中断"}:
                self.table.item(item_id, tags=("failed",))
        self.update_queue_summary()
        self.save_history()

    def update_queue_summary(self) -> None:
        count = len(self.jobs)
        self.summary_count.configure(text=str(count))
        self.status.set("尚未添加文件" if not count else f"队列中有 {count} 个视频")
        self.progress.configure(maximum=max(1, count))
        self.progress_text.configure(text=f"0 / {count}")

    def choose_files(self) -> None:
        files = filedialog.askopenfilenames(
            parent=self.root,
            title="选择视频",
            filetypes=[
                ("视频文件", "*.mp4 *.mov *.m4v *.mkv *.avi *.wmv *.flv *.webm *.mpeg *.mpg *.ts *.mts *.m2ts"),
                ("所有文件", "*.*"),
            ],
        )
        self.add_paths(files)

    def on_drop(self, event) -> None:
        self.add_paths(self.root.tk.splitlist(event.data))

    def add_paths(self, paths) -> None:
        rejected = 0
        for raw in paths:
            path = os.path.abspath(str(raw))
            if (
                not os.path.isfile(path)
                or Path(path).suffix.lower() not in VIDEO_EXTENSIONS
            ):
                rejected += 1
                continue
            if path in self.jobs.values():
                continue
            item_id = self.table.insert(
                "",
                "end",
                values=(
                    Path(path).name,
                    human_size(os.path.getsize(path)),
                    "等待上传",
                    "",
                    "",
                ),
            )
            self.jobs[item_id] = path
        self.status.set(f"已添加 {len(self.jobs)} 个视频")
        self.summary_count.configure(text=str(len(self.jobs)))
        self.summary_status.configure(text="等待开始")
        self.progress_text.configure(text=f"0 / {len(self.jobs)}")
        self.progress.configure(maximum=max(1, len(self.jobs)), value=0)
        self.save_history()
        if rejected:
            messagebox.showinfo("部分文件未添加", f"已忽略 {rejected} 个无效或非视频文件。")

    def remove_selected(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        selected = self.table.selection()
        if not selected:
            return
        count = len(selected)
        if not messagebox.askyesno(
            "确认移除",
            f"确定移除选中的 {count} 条记录吗？\n\n这不会删除本地视频或腾讯云中的视频。",
            parent=self.root,
        ):
            return
        for item_id in selected:
            self.table.delete(item_id)
            self.jobs.pop(item_id, None)
        self.update_queue_summary()
        self.save_history()

    def clear(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self.jobs:
            return
        if not messagebox.askyesno(
            "确认清空",
            "确定清空全部上传记录吗？\n\n清空后将无法在历史队列中找回这些记录。",
            parent=self.root,
        ):
            return
        for item_id in self.table.get_children():
            self.table.delete(item_id)
        self.jobs.clear()
        self.progress.configure(maximum=1, value=0)
        self.status.set("尚未添加文件")
        self.summary_count.configure(text="0")
        self.summary_status.configure(text="准备就绪")
        self.progress_text.configure(text="0 / 0")
        self.save_history()

    def open_config(self) -> bool:
        dialog = ConfigDialog(self.root, self.config)
        self.root.wait_window(dialog)
        if dialog.result:
            self.config = dialog.result
            self.refresh_config_summary()
            return True
        return False

    def start_upload(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not all(
            (
                self.config.secret_id,
                self.config.secret_key,
                self.config.region,
            )
        ):
            if not self.open_config():
                return
        pending = [
            (item_id, path)
            for item_id, path in self.jobs.items()
            if self.table.set(item_id, "status") != "上传成功"
        ]
        if not pending:
            messagebox.showinfo("没有任务", "请先添加视频，或列表中的视频均已上传。")
            return
        self.cancel_current_requested = False
        self._set_busy(True)
        self.progress.configure(maximum=len(pending), value=0)
        self.status.set(f"准备上传 {len(pending)} 个视频…")
        self.summary_status.configure(text="正在建立连接")
        self.progress_text.configure(text=f"0 / {len(pending)}")
        self.worker = threading.Thread(
            target=self.upload_batch, args=(pending,), daemon=True
        )
        self.worker.start()

    def upload_batch(self, pending: list[tuple[str, str]]) -> None:
        config_data = asdict(self.config)
        for item_id, path in pending:
            if not os.path.isfile(path):
                self.events.put(("failed", item_id, "本地文件不存在，无法重新上传"))
                continue
            self.events.put(("started", item_id))
            self.cancel_current_requested = False
            result_queue = mp.Queue()
            process = mp.Process(
                target=upload_one_process,
                args=(config_data, path, result_queue),
                daemon=False,
            )
            self.active_process = process
            process.start()
            while process.is_alive():
                if self.cancel_current_requested:
                    process.terminate()
                    process.join(timeout=3)
                    self.events.put(("cancelled", item_id))
                    break
                time.sleep(0.1)
            else:
                process.join()
                try:
                    result = result_queue.get(timeout=2)
                except queue.Empty:
                    result = ("failed", "上传进程异常结束，未返回结果")
                if result[0] == "succeeded":
                    self.events.put(
                        ("succeeded", item_id, result[1], result[2])
                    )
                else:
                    self.events.put(("failed", item_id, result[1]))
            result_queue.close()
            self.active_process = None
        self.events.put(("finished",))

    def process_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "started":
                    item_id = event[1]
                    self.table.set(item_id, "status", "上传中")
                    self.table.item(item_id, tags=("active",))
                    self.status.set(f"正在上传：{self.table.set(item_id, 'file')}")
                    self.summary_status.configure(text="上传中")
                    self.save_history()
                elif kind == "succeeded":
                    _, item_id, file_id, url = event
                    self.table.set(item_id, "status", "上传成功")
                    self.table.set(item_id, "file_id", file_id)
                    self.table.set(item_id, "url", url)
                    self.table.item(item_id, tags=("success",))
                    self.progress.step(1)
                    self.progress_text.configure(
                        text=f"{int(float(self.progress['value']))} / {int(float(self.progress['maximum']))}"
                    )
                    self.save_history()
                elif kind == "failed":
                    _, item_id, error = event
                    self.table.set(item_id, "status", "上传失败")
                    self.table.set(item_id, "url", error)
                    self.table.item(item_id, tags=("failed",))
                    self.progress.step(1)
                    self.progress_text.configure(
                        text=f"{int(float(self.progress['value']))} / {int(float(self.progress['maximum']))}"
                    )
                    self.save_history()
                elif kind == "cancelled":
                    self.table.set(event[1], "status", "已取消")
                    self.table.item(event[1], tags=("failed",))
                    self.progress.step(1)
                    self.progress_text.configure(
                        text=f"{int(float(self.progress['value']))} / {int(float(self.progress['maximum']))}"
                    )
                    self.save_history()
                elif kind == "finished":
                    self.finish_batch()
        except queue.Empty:
            pass
        self.root.after(100, self.process_events)

    def finish_batch(self) -> None:
        states = [self.table.set(item, "status") for item in self.jobs]
        success = states.count("上传成功")
        failed = states.count("上传失败") + states.count("已取消")
        self.status.set(f"处理完成：成功 {success}，失败/取消 {failed}")
        self.summary_status.configure(
            text="全部完成" if failed == 0 else f"{failed} 个需要处理",
            fg=COLORS["success"] if failed == 0 else COLORS["danger"]
        )
        self._set_busy(False)
        self.save_history()

    def cancel_upload(self) -> None:
        self.cancel_current_requested = True
        self.cancel_button.configure(state="disabled")
        self.status.set("正在终止当前上传…")
        self.summary_status.configure(text="正在终止", fg=COLORS["danger"])

    def _set_busy(self, busy: bool) -> None:
        normal = "disabled" if busy else "normal"
        for button in (
            self.add_button,
            self.remove_button,
            self.clear_button,
            self.config_button,
            self.upload_button,
        ):
            button.configure(state=normal)
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def show_context_menu(self, event) -> None:
        item_id = self.table.identify_row(event.y)
        if not item_id:
            return
        self.table.selection_set(item_id)
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="复制视频 URL", command=self.copy_selected_url)
        menu.add_command(label="复制 FileId", command=self.copy_selected_id)
        menu.add_command(label="在浏览器中打开 URL", command=self.open_selected_url)
        menu.add_separator()
        menu.add_command(label="重新上传此文件", command=self.retry_selected)
        menu.tk_popup(event.x_root, event.y_root)

    def url_at_event(self, event) -> str:
        item_id = self.table.identify_row(event.y)
        column = self.table.identify_column(event.x)
        if not item_id or column != "#5":
            return ""
        url = self.table.set(item_id, "url")
        return url if url.startswith(("http://", "https://")) else ""

    def open_url_from_click(self, event) -> None:
        url = self.url_at_event(event)
        if url:
            os.startfile(url)

    def update_table_cursor(self, event) -> None:
        self.table.configure(cursor="hand2" if self.url_at_event(event) else "")

    def selected_value(self, column: str) -> str:
        selected = self.table.selection()
        return self.table.set(selected[0], column) if selected else ""

    def copy_text(self, text: str) -> None:
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

    def copy_selected_url(self) -> None:
        self.copy_text(self.selected_value("url"))

    def copy_selected_id(self) -> None:
        self.copy_text(self.selected_value("file_id"))

    def open_selected_url(self) -> None:
        url = self.selected_value("url")
        if url.startswith(("http://", "https://")):
            os.startfile(url)

    def retry_selected(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        selected = self.table.selection()
        if not selected:
            return
        item_id = selected[0]
        path = self.jobs.get(item_id, "")
        if not os.path.isfile(path):
            messagebox.showwarning(
                "无法重新上传",
                "原始文件已被移动或删除，请重新添加该视频。",
                parent=self.root,
            )
            return
        self.table.set(item_id, "status", "等待上传")
        self.table.set(item_id, "file_id", "")
        self.table.set(item_id, "url", "")
        self.table.item(item_id, tags=())
        self.summary_status.configure(text="等待开始", fg=COLORS["text"])
        self.save_history()

    def on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("正在上传", "请等待当前上传结束，或先停止后续上传。")
            return
        self.root.destroy()


def main() -> int:
    if TkinterDnD:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    VodUploaderApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
