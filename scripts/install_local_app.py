"""Install the desktop entry and controller into user-owned directories."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def install() -> None:
    local = Path.home() / ".local"
    launcher = local / "bin" / "finance-workflow"
    controller = PROJECT_ROOT / "scripts" / "finance-workflow"
    icon = local / "share" / "icons" / "finance-workflow.svg"
    desktop = local / "share" / "applications" / "finance-workflow.desktop"
    for path in (launcher, icon, desktop):
        path.parent.mkdir(parents=True, exist_ok=True)
    if launcher.is_symlink() and launcher.resolve() == controller:
        pass
    elif launcher.exists() or launcher.is_symlink():
        raise FileExistsError(f"Existing launcher would be overwritten: {launcher}")
    else:
        launcher.symlink_to(controller)
    controller.chmod(0o755)
    shutil.copyfile(PROJECT_ROOT / "src" / "finance_workflow" / "web" / "icon.svg", icon)
    desktop.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Finance Workflow\n"
        "GenericName=Finance Research Workspace\n"
        "Comment=Equity research, portfolio risk, financial documents, and market monitoring\n"
        f'Exec="{launcher}" app\n'
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=Office;Finance;\n"
        "Keywords=finance;research;portfolio;markets;\n",
        encoding="utf-8",
    )
    desktop.chmod(0o755)
    for command in ("desktop-file-validate", "update-desktop-database"):
        if shutil.which(command):
            target = desktop if command == "desktop-file-validate" else desktop.parent
            subprocess.run([command, str(target)], check=True)
    print(f"Installed {desktop}")
    print("Launch with: finance-workflow app")


if __name__ == "__main__":
    install()
