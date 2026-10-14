#!/usr/bin/env python3
import os
import re
import subprocess
import sys
from pathlib import Path

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


class OmarchyCustomStudio:
    def __init__(self, work_dir: Path = WORK_DIR) -> None:
        self.work_dir = work_dir
        self.iso_dir = self.work_dir / "omarchy-iso"
        self.installer_dir = self.work_dir / "omarchy-installer"

    def run_cmd(self, cmd: list[str], cwd: Path | None = None) -> None:
        subprocess.run(cmd, cwd=cwd, check=True)

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

    def configure_packages_and_apps(self, selected_pkgs: list[str], custom_pkgs: list[str]) -> None:
        final_pkgs = list(dict.fromkeys(ESSENTIAL_PACKAGES + selected_pkgs + custom_pkgs))
        base_pkg_file = self.installer_dir / "install" / "omarchy-base.packages"
        if base_pkg_file.exists():
            base_pkg_file.write_text("\n".join(final_pkgs) + "\n", encoding="utf-8")

    def inject_custom_dotfiles_and_configs(self, dotfiles_map: dict[str, str]) -> None:
        for rel_target, content in dotfiles_map.items():
            target_path = self.installer_dir / "default" / rel_target
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")

    def patch_any_system_file(self, relative_repo_path: str, line_replacements: dict[str, str]) -> None:
        target = self.work_dir / relative_repo_path
        if not target.exists():
            return
        text = target.read_text(encoding="utf-8")
        for old_str, new_str in line_replacements.items():
            text = text.replace(old_str, new_str)
        target.write_text(text, encoding="utf-8")

    def build_iso(self) -> Path:
        self.run_cmd(["./bin/omarchy-iso-make", "--local-source", str(self.installer_dir)], cwd=self.iso_dir)
        return self.iso_dir / "release" / "omarchy.iso"


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        sys.exit(0)
    studio = OmarchyCustomStudio()
    studio.clone_sources()
    studio.configure_packages_and_apps([], [])
    studio.build_iso()