#!/usr/bin/env bash
set -euo pipefail

echo "=== Запуск установки Omarchy Custom ISO Studio ==="

if ! ping -c 1 google.com &>/dev/null; then
    echo "Ошибка: Нет подключения к интернету."
    exit 1
fi
echo "Интернет: Подключен"

FREE_SPACE=$(df -P "$HOME" | awk 'NR==2 {print $4}')
REQUIRED_SPACE=$((20 * 1024 * 1024))
if [ "$FREE_SPACE" -lt "$REQUIRED_SPACE" ]; then
    echo "Ошибка: Недостаточно свободного места на диске. Требуется минимум 20 ГБ."
    exit 1
fi
echo "Место на диске: Достаточно ($(numfmt --to=iec --from-unit=1K $FREE_SPACE))"

if command -v pacman &>/dev/null; then
    echo "ОС: Arch Linux"
    sudo pacman -Syu --noconfirm --needed git docker python jq curl squashfs-tools qemu-desktop python-pyqt6 python-pytest python-pip
elif command -v apt-get &>/dev/null; then
    echo "ОС: Debian/Ubuntu"
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y git docker.io python3 jq curl squashfs-tools qemu-system-x86 python3-pyqt6 python3-pytest python3-pip
elif command -v dnf &>/dev/null; then
    echo "ОС: Fedora/RHEL"
    sudo dnf install -y git docker python3 jq curl squashfs-tools qemu-system-x86 python3-qt6 python3-pytest python3-pip
elif command -v zypper &>/dev/null; then
    echo "ОС: openSUSE"
    sudo zypper install -y git docker python3 jq curl squashfs-tools qemu-x86 python3-qt6 python3-pytest python3-pip
else
    echo "Предупреждение: Не удалось определить пакетный менеджер. Установите зависимости вручную."
fi

if command -v systemctl &>/dev/null; then
    sudo systemctl enable --now docker || true
elif command -v service &>/dev/null; then
    sudo service docker start || true
fi

if ! groups | grep -q '\bdocker\b'; then
    sudo usermod -aG docker "$USER" || true
    echo "Внимание: Возможно, потребуется перезайти в систему для применения прав Docker."
fi

INSTALL_DIR="$HOME/.local/share/omarchy-custom-builder"
REPO_URL="https://github.com/Alastor418/omarchy-custom-builder"

if [ -d "$INSTALL_DIR"/.git ]; then
    echo "Обновление репозитория..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "Клонирование репозитория..."
    mkdir -p "$INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

chmod +x install.sh
chmod +x -R *.py || true

echo "=== Запуск Omarchy Custom ISO Studio ==="
if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
    python3 omarchy_builder.py "$@"
else
    echo "Графический сервер не найден. Запуск TUI (текстового интерфейса)..."
    python3 omarchy_builder.py --tui "$@"
fi
