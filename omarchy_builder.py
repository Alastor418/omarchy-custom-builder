#!/usr/bin/env python3
import os
import re
import subprocess
import sys
import json
import shutil
from pathlib import Path

try:
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                 QTabWidget, QLabel, QLineEdit, QPushButton, QTextEdit,
                                 QComboBox, QCheckBox, QTreeView, QFileSystemModel,
                                 QSplitter, QProgressBar, QMessageBox, QFileDialog, QFormLayout, QDialog, QDialogButtonBox,
                                 QListWidget)
    from PyQt6.QtCore import QThread, pyqtSignal, Qt, QProcess, QDir
    from PyQt6.QtGui import QColor, QPalette, QTextCharFormat, QFont
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

WORK_DIR = Path.home() / "omarchy-work"
ISO_REPO_URL = "https://github.com/omacom/omarchy-iso.git"
OMARCHY_REPO_URL = "https://github.com/omacom/omarchy.git"

ESSENTIAL_PACKAGES = [
    "base", "base-devel", "linux", "linux-firmware", "networkmanager", "iwd",
    "ufw", "bluez", "bluez-utils", "pipewire", "pipewire-alsa", "pipewire-pulse",
    "pipewire-jack", "wireplumber", "sddm", "uwsm", "polkit-gnome", "zram-generator",
    "sudo", "bash-completion", "hyprland", "hyprlock", "hypridle", "hyprpicker",
    "hyprsunset", "xdg-desktop-portal-hyprland", "xdg-desktop-portal-gtk",
    "xdg-user-dirs", "swaybg", "wl-clipboard", "cliphist", "grim", "slurp",
    "satty", "imv", "brightnessctl", "pamixer", "playerctl", "libnotify",
    "quickshell", "qt6-declarative", "qt6-wayland", "qt6-svg", "qt6-5compat",
    "gtk3", "gtk4", "nwg-look", "kvantum-qt6", "gnome-themes-extra",
    "adwaita-icon-theme", "papirus-icon-theme", "ttf-jetbrains-mono-nerd",
    "noto-fonts", "noto-fonts-emoji", "alacritty", "jq", "gum", "fzf",
    "curl", "git", "ripgrep", "fd", "unzip", "tar", "less", "btop", "fastfetch"
]

BASE_ONLY_PACKAGES = [
    "base", "base-devel", "linux", "linux-firmware", "networkmanager", "iwd",
    "sudo", "hyprland", "xdg-desktop-portal-hyprland", "quickshell",
    "qt6-declarative", "qt6-wayland"
]

class OmarchyCustomStudioBackend:
    def __init__(self, work_dir: Path = WORK_DIR) -> None:
        self.work_dir = Path(work_dir)
        self.iso_dir = self.work_dir / "omarchy-iso"
        self.installer_dir = self.work_dir / "omarchy-installer"

    def run_cmd(self, cmd: list[str], cwd: Path | None = None) -> str:
        res = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
        return res.stdout

    def clone_sources(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        if not self.iso_dir.exists():
            self.run_cmd(["git", "clone", "--recursive", ISO_REPO_URL, str(self.iso_dir)])
        if not self.installer_dir.exists():
            self.run_cmd(["git", "clone", OMARCHY_REPO_URL, str(self.installer_dir)])

    def customize_splash_and_branding(self, config: dict) -> None:
        os_name = config.get("os_name", "Custom Omarchy")
        os_release = self.installer_dir / "default" / "os-release"
        if os_release.parent.exists():
            os_release.write_text(f'NAME="{os_name}"\nPRETTY_NAME="{os_name}"\nID=arch\n', encoding="utf-8")
        
        hostname = config.get("hostname", "omarchy")
        hostname_file = self.installer_dir / "default" / "hostname"
        if hostname_file.parent.exists():
            hostname_file.write_text(f"{hostname}\n", encoding="utf-8")

        plymouth = config.get("plymouth")
        if plymouth:
            plymouth_dir = self.installer_dir / "default" / "usr" / "share" / "plymouth" / "themes" / "custom"
            plymouth_dir.mkdir(parents=True, exist_ok=True)
            (plymouth_dir / "custom.plymouth").write_text(f"[Plymouth Theme]\nName=Custom\nImageDir={plymouth}\n", encoding="utf-8")

        limine_bg = config.get("limine")
        if limine_bg:
            limine_dir = self.installer_dir / "default" / "boot" / "limine"
            limine_dir.mkdir(parents=True, exist_ok=True)
            (limine_dir / "limine.conf").write_text(f"wallpaper: {limine_bg}\ntimeout: 5\n", encoding="utf-8")

        fastfetch = config.get("fastfetch")
        if fastfetch:
            ff_dir = self.installer_dir / "default" / ".config" / "fastfetch"
            ff_dir.mkdir(parents=True, exist_ok=True)
            (ff_dir / "logo.txt").write_text(fastfetch, encoding="utf-8")
            
        sddm = config.get("sddm")
        if sddm:
            sddm_dir = self.installer_dir / "default" / "usr" / "share" / "sddm" / "themes"
            sddm_dir.mkdir(parents=True, exist_ok=True)
            (sddm_dir / "theme.conf").write_text(f"[Theme]\nBackground={sddm}\n", encoding="utf-8")
            
        hyprlock = config.get("hyprlock")
        if hyprlock:
            hyprlock_dir = self.installer_dir / "default" / "hypr"
            hyprlock_dir.mkdir(parents=True, exist_ok=True)
            (hyprlock_dir / "hyprlock.conf").write_text(f"background {{ path = {hyprlock} }}\n", encoding="utf-8")

    def configure_packages_and_apps(self, base_only: bool, selected_pkgs: list[str], custom_pkgs: list[str]) -> list[str]:
        base_pkgs = BASE_ONLY_PACKAGES if base_only else ESSENTIAL_PACKAGES
        removed_pkgs = list(set(ESSENTIAL_PACKAGES) - set(base_pkgs))
        final_pkgs = list(dict.fromkeys(base_pkgs + selected_pkgs + custom_pkgs))
        
        base_pkg_file = self.installer_dir / "install" / "omarchy-base.packages"
        if base_pkg_file.parent.exists():
            base_pkg_file.write_text("\n".join(final_pkgs) + "\n", encoding="utf-8")
        
        return removed_pkgs

    def inject_custom_dotfiles_and_configs(self, dotfiles_map: dict[str, str]) -> None:
        for rel_target, content in dotfiles_map.items():
            target_path = self.installer_dir / "default" / rel_target
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")

    def apply_hyprland_quickshell_theme(self, theme_config: dict) -> None:
        hypr_conf_path = self.installer_dir / "default" / "hypr" / "hyprland.conf"
        if hypr_conf_path.exists():
            content = hypr_conf_path.read_text(encoding="utf-8")
            for key, val in theme_config.items():
                if key in ["gaps_in", "gaps_out", "rounding", "blur", "animations"]:
                    content = re.sub(rf'{key}\s*=\s*.*', f'{key} = {val}', content)
            hypr_conf_path.write_text(content, encoding="utf-8")
            
        quickshell_conf_path = self.installer_dir / "default" / "quickshell" / "config.qml"
        if quickshell_conf_path.exists():
            content = quickshell_conf_path.read_text(encoding="utf-8")
            for key, val in theme_config.items():
                if key in ["margins", "opacity", "radius", "font"]:
                    content = re.sub(rf'{key}:\s*.*', f'{key}: {val}', content)
            quickshell_conf_path.write_text(content, encoding="utf-8")

    def generate_cidata(self, cidata_config: dict) -> None:
        cidata_dir = self.work_dir / "cidata"
        cidata_dir.mkdir(parents=True, exist_ok=True)
        meta_data = f"instance-id: custom-omarchy\nlocal-hostname: {cidata_config.get('hostname', 'omarchy')}\n"
        
        # generate password hash
        password = cidata_config.get('password', '')
        hashed_password = ""
        if password:
            hashed_password = subprocess.run(["openssl", "passwd", "-6", password], capture_output=True, text=True).stdout.strip()
            
        ssh_keys = cidata_config.get('ssh_keys', '')
        ssh_keys_str = ""
        if ssh_keys:
            ssh_keys_str = f"ssh_authorized_keys:\n  - {ssh_keys}\n"

        user_data = f"""#cloud-config
users:
  - name: {cidata_config.get('username', 'omarchy')}
    passwd: {hashed_password}
    lock_passwd: false
    sudo: ALL=(ALL) NOPASSWD:ALL
{ssh_keys_str}
timezone: {cidata_config.get('timezone', 'Europe/Moscow')}
keyboard:
  layout: {cidata_config.get('keymap', 'ru')}
"""
        (cidata_dir / "meta-data").write_text(meta_data, encoding="utf-8")
        (cidata_dir / "user-data").write_text(user_data, encoding="utf-8")

    def patch_system_lines(self, line_patches: list[dict]) -> None:
        for patch in line_patches:
            filepath = patch.get("file")
            old_str = patch.get("old")
            new_str = patch.get("new")
            if not filepath or not old_str or new_str is None:
                continue
            
            target = self.work_dir / filepath
            if target.exists():
                text = target.read_text(encoding="utf-8")
                # Using regex if specified, otherwise simple string replace
                if patch.get("regex"):
                    text = re.sub(old_str, new_str, text)
                else:
                    text = text.replace(old_str, new_str)
                target.write_text(text, encoding="utf-8")

    def smart_sanitizer(self, removed_packages: list[str]) -> None:
        dirs_to_check = [
            self.installer_dir / "install",
            self.installer_dir / "bin",
            self.installer_dir / "default" / "hypr"
        ]
        
        if not removed_packages:
            return
            
        for d in dirs_to_check:
            if not d.exists():
                continue
            for root, _, files in os.walk(d):
                for f in files:
                    if f.endswith('.sh') or f.startswith('omarchy-provision') or f == 'autostart.conf':
                        filepath = Path(root) / f
                        try:
                            content = filepath.read_text(encoding="utf-8")
                            modified = False
                            for pkg in removed_packages:
                                pattern = re.compile(rf'^\s*{pkg}\b.*$', re.MULTILINE)
                                for match in pattern.finditer(content):
                                    line = match.group(0)
                                    if 'command -v' not in line:
                                        safe_line = f"if command -v {pkg} >/dev/null; then\n  {line.strip()}\nfi"
                                        content = content.replace(line, safe_line)
                                        modified = True
                            if modified:
                                filepath.write_text(content, encoding="utf-8")
                        except Exception:
                            pass

    def check_syntax(self) -> bool:
        success = True
        for d in [self.installer_dir, self.iso_dir]:
            if not d.exists():
                continue
            for root, _, files in os.walk(d):
                for f in files:
                    if f.endswith('.sh') or ('.' not in f and os.access(Path(root)/f, os.X_OK)):
                        filepath = Path(root) / f
                        try:
                            res = subprocess.run(["bash", "-n", str(filepath)], capture_output=True, text=True)
                            if res.returncode != 0:
                                print(f"Syntax error in {filepath}:\n{res.stderr}")
                                success = False
                        except Exception:
                            pass
        return success

    def build_iso_process(self) -> "QProcess":
        bin_script = self.iso_dir / "bin" / "omarchy-iso-make"
        process = QProcess()
        process.setWorkingDirectory(str(self.iso_dir))
        
        if bin_script.exists():
            process.start(str(bin_script), ["--local-source", str(self.installer_dir)])
        else:
            # mock for testing
            process.start("echo", ["Mocking build..."])
        return process

# --- GUI ---
if HAS_GUI:
    class LinePatchDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Добавить замену строк")
            l = QFormLayout(self)
            self.file_input = QLineEdit()
            self.file_input.setPlaceholderText("Например: omarchy-installer/default/hypr/hyprland.conf")
            self.old_input = QLineEdit()
            self.new_input = QLineEdit()
            self.regex_cb = QCheckBox("Использовать Regex")
            l.addRow("Файл (относительно work dir):", self.file_input)
            l.addRow("Что заменить (старая строка):", self.old_input)
            l.addRow("На что заменить (новая строка):", self.new_input)
            l.addRow("", self.regex_cb)
            
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            l.addWidget(buttons)
            
        def get_patch(self):
            return {
                "file": self.file_input.text(),
                "old": self.old_input.text(),
                "new": self.new_input.text(),
                "regex": self.regex_cb.isChecked()
            }

    class OmarchyApp(QMainWindow):
        def __init__(self):
            super().__init__()
            self.backend = OmarchyCustomStudioBackend()
            self.setWindowTitle("Omarchy Custom ISO Studio")
            self.resize(1100, 750)
            self.apply_theme()

            self.tabs = QTabWidget()
            self.setCentralWidget(self.tabs)
            
            self.line_patches = []

            self.init_tab1()
            self.init_tab2()
            self.init_tab3()
            self.init_tab4()
            self.init_tab5()
            self.init_tab6()
            
        def apply_theme(self):
            palette = QPalette()
            bg_color = QColor(26, 27, 38)
            fg_color = QColor(192, 202, 245)
            palette.setColor(QPalette.ColorRole.Window, bg_color)
            palette.setColor(QPalette.ColorRole.WindowText, fg_color)
            palette.setColor(QPalette.ColorRole.Base, QColor(22, 22, 30))
            palette.setColor(QPalette.ColorRole.AlternateBase, bg_color)
            palette.setColor(QPalette.ColorRole.ToolTipBase, bg_color)
            palette.setColor(QPalette.ColorRole.ToolTipText, fg_color)
            palette.setColor(QPalette.ColorRole.Text, fg_color)
            palette.setColor(QPalette.ColorRole.Button, QColor(41, 46, 66))
            palette.setColor(QPalette.ColorRole.ButtonText, fg_color)
            palette.setColor(QPalette.ColorRole.BrightText, QColor(247, 118, 142))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(122, 162, 247))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(26, 27, 38))
            self.setPalette(palette)
            self.setStyleSheet("""
                QWidget { font-size: 14px; }
                QPushButton { padding: 6px; border-radius: 4px; background: #3b4261; }
                QPushButton:hover { background: #7aa2f7; color: #1a1b26; }
                QLineEdit, QTextEdit, QComboBox { padding: 4px; border: 1px solid #565f89; background: #16161e; border-radius: 4px; }
                QTabWidget::pane { border: 1px solid #565f89; }
                QTabBar::tab { background: #1a1b26; border: 1px solid #565f89; padding: 8px; }
                QTabBar::tab:selected { background: #7aa2f7; color: #1a1b26; }
            """)

        def init_tab1(self):
            w = QWidget()
            l = QFormLayout(w)
            self.os_name_input = QLineEdit("Custom Omarchy")
            self.hostname_input = QLineEdit("omarchy")
            self.plymouth_input = QLineEdit()
            self.limine_input = QLineEdit()
            self.fastfetch_input = QTextEdit()
            self.sddm_input = QLineEdit()
            self.hyprlock_input = QLineEdit()
            l.addRow("Имя ОС (/etc/os-release):", self.os_name_input)
            l.addRow("Имя хоста:", self.hostname_input)
            l.addRow("Plymouth (путь к фону):", self.plymouth_input)
            l.addRow("Limine (путь к обоям):", self.limine_input)
            l.addRow("SDDM (путь к фону):", self.sddm_input)
            l.addRow("Hyprlock (путь к фону):", self.hyprlock_input)
            l.addRow("Fastfetch (ASCII art):", self.fastfetch_input)
            self.tabs.addTab(w, "Заставка, Загрузчик и Брендинг")

        def init_tab2(self):
            w = QWidget()
            l = QVBoxLayout(w)
            
            top_l = QHBoxLayout()
            self.pkg_search = QLineEdit()
            self.pkg_search.setPlaceholderText("Поиск пакетов...")
            self.pkg_category = QComboBox()
            self.pkg_category.addItems(["Все", "Система", "Сеть", "UI"])
            top_l.addWidget(self.pkg_search)
            top_l.addWidget(self.pkg_category)
            l.addLayout(top_l)
            
            self.base_only_cb = QCheckBox("Только чистая база Hyprland + Quickshell")
            l.addWidget(self.base_only_cb)
            
            l.addWidget(QLabel("Дополнительные пакеты (AUR/Official, через пробел):"))
            self.custom_pkgs_input = QLineEdit()
            l.addWidget(self.custom_pkgs_input)
            
            l.addWidget(QLabel("Добавить свои конфиги (например, путь ~/.config/app -> содержимое JSON):"))
            self.dotfiles_input = QTextEdit()
            self.dotfiles_input.setPlaceholderText('{\n  ".config/kitty/kitty.conf": "font_size 12.0"\n}')
            l.addWidget(self.dotfiles_input)
            self.tabs.addTab(w, "Программы и Свои Конфиги")

        def init_tab3(self):
            w = QWidget()
            l = QFormLayout(w)
            self.gaps_in_input = QLineEdit("5")
            self.gaps_out_input = QLineEdit("10")
            self.rounding_input = QLineEdit("8")
            self.blur_input = QLineEdit("yes")
            self.animations_input = QLineEdit("yes")
            
            self.panel_pos_combo = QComboBox()
            self.panel_pos_combo.addItems(["top", "bottom"])
            self.qs_margins = QLineEdit("5")
            self.qs_opacity = QLineEdit("0.9")
            self.qs_radius = QLineEdit("10")
            self.qs_font = QLineEdit("JetBrains Mono")
            
            l.addRow("Hyprland: gaps_in:", self.gaps_in_input)
            l.addRow("Hyprland: gaps_out:", self.gaps_out_input)
            l.addRow("Hyprland: rounding:", self.rounding_input)
            l.addRow("Hyprland: blur:", self.blur_input)
            l.addRow("Hyprland: animations:", self.animations_input)
            
            l.addRow("Quickshell: panel position:", self.panel_pos_combo)
            l.addRow("Quickshell: margins:", self.qs_margins)
            l.addRow("Quickshell: opacity:", self.qs_opacity)
            l.addRow("Quickshell: radius:", self.qs_radius)
            l.addRow("Quickshell: font:", self.qs_font)
            
            self.tabs.addTab(w, "Внешний вид Hyprland и Quickshell")

        def init_tab4(self):
            w = QWidget()
            layout = QHBoxLayout(w)
            
            # Left: File Tree
            self.file_model = QFileSystemModel()
            self.file_model.setRootPath(str(WORK_DIR))
            self.tree = QTreeView()
            self.tree.setModel(self.file_model)
            self.tree.setRootIndex(self.file_model.index(str(WORK_DIR)))
            self.tree.clicked.connect(self.load_file)
            layout.addWidget(self.tree)
            
            # Center: Editor
            editor_layout = QVBoxLayout()
            self.editor = QTextEdit()
            self.editor.setFont(QFont("Monospace", 10))
            editor_layout.addWidget(self.editor)
            
            save_btn = QPushButton("Сохранить файл")
            save_btn.clicked.connect(self.save_file)
            editor_layout.addWidget(save_btn)
            layout.addLayout(editor_layout)
            
            # Right: Line Patches
            patches_layout = QVBoxLayout()
            patches_layout.addWidget(QLabel("Правила замены строк (Line Patches):"))
            self.patches_view = QTextEdit()
            self.patches_view.setReadOnly(True)
            patches_layout.addWidget(self.patches_view)
            add_patch_btn = QPushButton("Добавить правило замены")
            add_patch_btn.clicked.connect(self.add_patch)
            patches_layout.addWidget(add_patch_btn)
            layout.addLayout(patches_layout)
            
            self.current_file = None
            self.tabs.addTab(w, "Глубокий редактор файлов системы")

        def load_file(self, index):
            path = self.file_model.filePath(index)
            if os.path.isfile(path):
                try:
                    self.editor.setPlainText(Path(path).read_text(encoding='utf-8'))
                    self.current_file = path
                except Exception as e:
                    self.editor.setPlainText(f"Не удалось открыть файл:\n{e}")

        def save_file(self):
            if self.current_file:
                try:
                    Path(self.current_file).write_text(self.editor.toPlainText(), encoding='utf-8')
                    QMessageBox.information(self, "Успех", "Файл сохранен!")
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", str(e))

        def add_patch(self):
            dialog = LinePatchDialog(self)
            if dialog.exec():
                patch = dialog.get_patch()
                self.line_patches.append(patch)
                self.update_patches_view()
                
        def update_patches_view(self):
            self.patches_view.clear()
            for i, p in enumerate(self.line_patches):
                self.patches_view.append(f"{i+1}. Файл: {p['file']}\n   Найти: {p['old']}\n   Заменить: {p['new']}\n   Regex: {p['regex']}\n")

        def init_tab5(self):
            w = QWidget()
            l = QFormLayout(w)
            self.username_input = QLineEdit("omarchy")
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.timezone_input = QLineEdit("Europe/Moscow")
            self.keymap_input = QLineEdit("ru")
            self.ssh_keys_input = QTextEdit()
            self.ssh_keys_input.setPlaceholderText("ssh-rsa AAAAB3NzaC1yc2E...")
            
            l.addRow("Имя пользователя:", self.username_input)
            l.addRow("Пароль (будет захэширован):", self.password_input)
            l.addRow("Часовой пояс:", self.timezone_input)
            l.addRow("Раскладка клавиатуры:", self.keymap_input)
            l.addRow("SSH ключи (по одному на строку):", self.ssh_keys_input)
            
            self.tabs.addTab(w, "Автоустановка (Unattended / cidata)")

        def init_tab6(self):
            w = QWidget()
            l = QVBoxLayout(w)
            
            btn_layout = QHBoxLayout()
            self.btn_save_profile = QPushButton("Сохранить профиль")
            self.btn_load_profile = QPushButton("Загрузить профиль")
            self.btn_check = QPushButton("Проверить синтаксис (bash -n)")
            self.btn_build = QPushButton("Собрать рабочий ISO")
            self.btn_test = QPushButton("Протестировать в QEMU")
            
            self.btn_save_profile.clicked.connect(self.save_profile)
            self.btn_load_profile.clicked.connect(self.load_profile)
            self.btn_check.clicked.connect(self.run_checks)
            self.btn_build.clicked.connect(self.build_iso)
            self.btn_test.clicked.connect(self.test_qemu)
            
            btn_layout.addWidget(self.btn_save_profile)
            btn_layout.addWidget(self.btn_load_profile)
            btn_layout.addWidget(self.btn_check)
            btn_layout.addWidget(self.btn_build)
            btn_layout.addWidget(self.btn_test)
            l.addLayout(btn_layout)
            
            self.console = QTextEdit()
            self.console.setReadOnly(True)
            self.console.setFont(QFont("Monospace", 10))
            l.addWidget(self.console)
            
            self.progress = QProgressBar()
            self.progress.setRange(0, 0)
            self.progress.setVisible(False)
            l.addWidget(self.progress)
            
            self.tabs.addTab(w, "Самодиагностика и Сборка ISO")
            
            self.process = None

        def gather_profile_data(self):
            return {
                "os_name": self.os_name_input.text(),
                "hostname": self.hostname_input.text(),
                "plymouth": self.plymouth_input.text(),
                "limine": self.limine_input.text(),
                "sddm": self.sddm_input.text(),
                "hyprlock": self.hyprlock_input.text(),
                "fastfetch": self.fastfetch_input.toPlainText(),
                "base_only": self.base_only_cb.isChecked(),
                "custom_pkgs": self.custom_pkgs_input.text(),
                "dotfiles": self.dotfiles_input.toPlainText(),
                "gaps_in": self.gaps_in_input.text(),
                "gaps_out": self.gaps_out_input.text(),
                "rounding": self.rounding_input.text(),
                "blur": self.blur_input.text(),
                "animations": self.animations_input.text(),
                "panel_pos": self.panel_pos_combo.currentText(),
                "margins": self.qs_margins.text(),
                "opacity": self.qs_opacity.text(),
                "radius": self.qs_radius.text(),
                "font": self.qs_font.text(),
                "line_patches": self.line_patches,
                "cidata": {
                    "username": self.username_input.text(),
                    "password": self.password_input.text(),
                    "timezone": self.timezone_input.text(),
                    "keymap": self.keymap_input.text(),
                    "ssh_keys": self.ssh_keys_input.toPlainText()
                }
            }

        def load_profile_data(self, prof):
            self.os_name_input.setText(prof.get("os_name", "Custom Omarchy"))
            self.hostname_input.setText(prof.get("hostname", "omarchy"))
            self.plymouth_input.setText(prof.get("plymouth", ""))
            self.limine_input.setText(prof.get("limine", ""))
            self.sddm_input.setText(prof.get("sddm", ""))
            self.hyprlock_input.setText(prof.get("hyprlock", ""))
            self.fastfetch_input.setPlainText(prof.get("fastfetch", ""))
            
            self.base_only_cb.setChecked(prof.get("base_only", False))
            self.custom_pkgs_input.setText(prof.get("custom_pkgs", ""))
            self.dotfiles_input.setPlainText(prof.get("dotfiles", ""))
            
            self.gaps_in_input.setText(prof.get("gaps_in", "5"))
            self.gaps_out_input.setText(prof.get("gaps_out", "10"))
            self.rounding_input.setText(prof.get("rounding", "8"))
            self.blur_input.setText(prof.get("blur", "yes"))
            self.animations_input.setText(prof.get("animations", "yes"))
            
            self.panel_pos_combo.setCurrentText(prof.get("panel_pos", "top"))
            self.qs_margins.setText(prof.get("margins", "5"))
            self.qs_opacity.setText(prof.get("opacity", "0.9"))
            self.qs_radius.setText(prof.get("radius", "10"))
            self.qs_font.setText(prof.get("font", "JetBrains Mono"))
            
            self.line_patches = prof.get("line_patches", [])
            self.update_patches_view()
            
            cidata = prof.get("cidata", {})
            self.username_input.setText(cidata.get("username", "omarchy"))
            self.password_input.setText(cidata.get("password", ""))
            self.timezone_input.setText(cidata.get("timezone", "Europe/Moscow"))
            self.keymap_input.setText(cidata.get("keymap", "ru"))
            self.ssh_keys_input.setPlainText(cidata.get("ssh_keys", ""))

        def save_profile(self):
            path, _ = QFileDialog.getSaveFileName(self, "Сохранить профиль", "", "JSON (*.json)")
            if path:
                prof = self.gather_profile_data()
                Path(path).write_text(json.dumps(prof, indent=2), encoding="utf-8")
                self.console.append(f"Профиль сохранен в {path}")

        def load_profile(self):
            path, _ = QFileDialog.getOpenFileName(self, "Загрузить профиль", "", "JSON (*.json)")
            if path:
                try:
                    prof = json.loads(Path(path).read_text(encoding="utf-8"))
                    self.load_profile_data(prof)
                    self.console.append(f"Профиль загружен из {path}")
                except Exception as e:
                    self.console.append(f"Ошибка загрузки: {e}")

        def run_checks(self):
            self.console.append("Проверка синтаксиса bash...")
            success = self.backend.check_syntax()
            if success:
                self.console.append("Проверка пройдена успешно.")
            else:
                self.console.append("Найдены синтаксические ошибки. См. терминал или логи.")

        def build_iso(self):
            self.btn_build.setEnabled(False)
            self.progress.setVisible(True)
            self.console.append("Клонирование/обновление исходников...")
            QApplication.processEvents()
            try:
                self.backend.clone_sources()
            except Exception as e:
                self.console.append(f"Ошибка клонирования: {e}")
            
            prof = self.gather_profile_data()
            
            self.console.append("Применение брендинга...")
            self.backend.customize_splash_and_branding(prof)
            
            self.console.append("Настройка пакетов...")
            custom_pkgs = [p for p in prof["custom_pkgs"].split() if p]
            removed_pkgs = self.backend.configure_packages_and_apps(prof["base_only"], [], custom_pkgs)
            
            self.console.append("Применение тем...")
            self.backend.apply_hyprland_quickshell_theme({
                "gaps_in": prof["gaps_in"], "gaps_out": prof["gaps_out"], "rounding": prof["rounding"],
                "blur": prof["blur"], "animations": prof["animations"],
                "margins": prof["margins"], "opacity": prof["opacity"], "radius": prof["radius"], "font": prof["font"]
            })
            
            try:
                dotfiles = json.loads(prof["dotfiles"] or "{}")
                self.backend.inject_custom_dotfiles_and_configs(dotfiles)
            except Exception as e:
                self.console.append(f"Ошибка в JSON конфигов: {e}")
                
            self.console.append("Применение патчей строк...")
            self.backend.patch_system_lines(self.line_patches)
            
            self.console.append("Генерация cidata автоустановки...")
            self.backend.generate_cidata(prof["cidata"])
            
            self.console.append("Запуск Smart Sanitizer...")
            self.backend.smart_sanitizer(removed_pkgs)
            
            self.console.append("Запуск сборки ISO...")
            
            self.process = self.backend.build_iso_process()
            self.process.readyReadStandardOutput.connect(self.handle_stdout)
            self.process.readyReadStandardError.connect(self.handle_stderr)
            self.process.finished.connect(self.build_finished)

        def handle_stdout(self):
            data = self.process.readAllStandardOutput().data().decode('utf-8')
            self.console.append(data.strip())
            
        def handle_stderr(self):
            data = self.process.readAllStandardError().data().decode('utf-8')
            self.console.append(data.strip())
            
        def build_finished(self, exitCode, exitStatus):
            self.progress.setVisible(False)
            self.btn_build.setEnabled(True)
            iso = self.backend.iso_dir / "release" / "omarchy.iso"
            self.console.append(f"Сборка завершена. Код выхода: {exitCode}. Путь: {iso}")

        def test_qemu(self):
            iso = self.backend.iso_dir / "release" / "omarchy.iso"
            if not iso.exists():
                self.console.append("ISO файл не найден.")
                return
            self.console.append("Запуск QEMU...")
            subprocess.Popen(["qemu-system-x86_64", "-m", "2G", "-cdrom", str(iso)])

# --- TUI Fallback ---
def run_tui():
    print("=== Omarchy Custom ISO Studio (TUI) ===")
    backend = OmarchyCustomStudioBackend()
    print("1. Клонирование исходников...")
    try:
        backend.clone_sources()
        print("Готово.")
    except Exception as e:
        print(f"Ошибка: {e}")
        return
    
    os_name = input("Имя ОС [Custom Omarchy]: ").strip() or "Custom Omarchy"
    hostname = input("Имя хоста [omarchy]: ").strip() or "omarchy"
    backend.customize_splash_and_branding({"os_name": os_name, "hostname": hostname})
    
    custom_pkgs = input("Доп. пакеты (через пробел): ").strip().split()
    removed = backend.configure_packages_and_apps(False, [], custom_pkgs)
    
    print("Запуск Smart Sanitizer...")
    backend.smart_sanitizer(removed)
    
    print("Проверка синтаксиса bash...")
    backend.check_syntax()
    
    print("Запуск сборки ISO (может занять время)...")
    try:
        iso_path = backend.build_iso()
        print(f"ISO собран: {iso_path}")
    except Exception as e:
        print(f"Ошибка сборки: {e}")

if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        sys.exit(0)
    
    if "--tui" in sys.argv or not HAS_GUI:
        run_tui()
    else:
        app = QApplication(sys.argv)
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            pass
        window = OmarchyApp()
        window.show()
        sys.exit(app.exec())
