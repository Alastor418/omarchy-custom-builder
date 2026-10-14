import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Set to offscreen so GUI tests don't crash without display
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import omarchy_builder
from omarchy_builder import OmarchyCustomStudioBackend

@pytest.fixture
def backend(tmp_path):
    return OmarchyCustomStudioBackend(work_dir=tmp_path)

def test_clone_sources(backend):
    with patch.object(backend, 'run_cmd') as mock_run:
        backend.clone_sources()
        assert mock_run.call_count == 2
        args1 = mock_run.call_args_list[0][0][0]
        args2 = mock_run.call_args_list[1][0][0]
        assert "clone" in args1
        assert "clone" in args2

def test_customize_splash_and_branding(backend):
    os_release_path = backend.installer_dir / "default" / "os-release"
    hostname_path = backend.installer_dir / "default" / "hostname"
    
    os_release_path.parent.mkdir(parents=True, exist_ok=True)
    os_release_path.touch()
    hostname_path.touch()

    backend.customize_splash_and_branding({
        "os_name": "Test OS", 
        "hostname": "test-host",
        "fastfetch": "fastfetch content",
        "plymouth": "/path/to/plymouth",
        "sddm": "/path/to/sddm_bg.png",
        "sddm_autologin": True,
        "cidata": {"username": "testuser"}
    })
    
    content = os_release_path.read_text()
    assert 'NAME="Test OS"' in content
    
    host_content = hostname_path.read_text()
    assert "test-host\n" in host_content
    
    ff_path = backend.installer_dir / "default" / ".config" / "fastfetch" / "logo.txt"
    assert ff_path.read_text() == "fastfetch content"

    plymouth_conf_path = backend.installer_dir / "default" / "etc" / "plymouth" / "plymouthd.conf"
    assert "Theme=custom" in plymouth_conf_path.read_text()

    sddm_conf_path = backend.installer_dir / "default" / "etc" / "sddm.conf.d" / "custom.conf"
    sddm_content = sddm_conf_path.read_text()
    assert "Current=custom" in sddm_content
    assert "User=testuser" in sddm_content
    assert "Session=hyprland" in sddm_content

def test_inject_custom_dotfiles_and_configs(backend):
    dotfiles = {".local/bin/script.sh": "echo test"}
    perms = {".local/bin/script.sh": "0755"}
    backend.inject_custom_dotfiles_and_configs(dotfiles, perms)

    script_path = backend.installer_dir / "default" / ".local/bin/script.sh"
    assert script_path.exists()
    assert script_path.read_text() == "echo test"
    # Ensure it's executable
    assert os.access(script_path, os.X_OK)

def test_add_chroot_scripts(backend):
    backend.add_chroot_scripts("echo 'hello from chroot'")
    chroot_script_path = backend.installer_dir / "install" / "99-custom-chroot.sh"
    assert chroot_script_path.exists()
    assert "hello from chroot" in chroot_script_path.read_text()
    assert os.access(chroot_script_path, os.X_OK)

def test_patch_system_lines(backend):
    test_file = backend.work_dir / "test.txt"
    test_file.write_text("Hello World! gaps_in = 5")
    
    backend.patch_system_lines([
        {"file": "test.txt", "old": "World", "new": "Omarchy", "regex": False},
        {"file": "test.txt", "old": r"gaps_in\s*=\s*\d+", "new": "gaps_in = 10", "regex": True}
    ])
    
    assert test_file.read_text() == "Hello Omarchy! gaps_in = 10"

def test_smart_sanitizer(backend):
    script_dir = backend.installer_dir / "install"
    script_dir.mkdir(parents=True, exist_ok=True)
    script_path = script_dir / "test.sh"
    script_path.write_text("apt-get update\nfirefox --version\n")
    
    backend.smart_sanitizer(["firefox"])
    
    content = script_path.read_text()
    assert "if command -v firefox >/dev/null; then" in content
    assert "apt-get update" in content

def test_check_syntax(backend):
    script_dir = backend.installer_dir / "install"
    script_dir.mkdir(parents=True, exist_ok=True)
    valid_script = script_dir / "valid.sh"
    valid_script.write_text("#!/bin/bash\necho 'hello'")
    
    invalid_script = script_dir / "invalid.sh"
    invalid_script.write_text("#!/bin/bash\nif [ 1 ]; then\necho 'missing fi'")
    
    assert backend.check_syntax() == False
    
    invalid_script.unlink()
    assert backend.check_syntax() == True

def test_gui_profile_export_import(tmp_path):
    if not omarchy_builder.HAS_GUI:
        pytest.skip("Requires PyQt6")
    from omarchy_builder import OmarchyApp, QApplication
    import sys
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
        
    window = OmarchyApp()
    
    window.os_name_input.setText("Test OS GUI")
    window.hostname_input.setText("test-gui-host")
    window.base_only_cb.setChecked(True)
    window.custom_pkgs_input.setText("vim htop")
    
    prof_path = tmp_path / "profile.json"
    
    with patch('omarchy_builder.QFileDialog.getSaveFileName', return_value=(str(prof_path), "")):
        window.save_profile()
        
    assert prof_path.exists()
    
    window.os_name_input.setText("")
    window.hostname_input.setText("")
    
    with patch('omarchy_builder.QFileDialog.getOpenFileName', return_value=(str(prof_path), "")):
        window.load_profile()
        
    assert window.os_name_input.text() == "Test OS GUI"
    assert window.hostname_input.text() == "test-gui-host"
    assert window.base_only_cb.isChecked() == True
    assert window.custom_pkgs_input.text() == "vim htop"

def test_gui_startup():
    if not omarchy_builder.HAS_GUI:
        pytest.skip("Requires PyQt6")
    from omarchy_builder import OmarchyApp, QApplication
    import sys
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    window = OmarchyApp()
    assert window.tabs.count() == 6
