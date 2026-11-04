"""安全的文件夹"删除"：不真正删除，而是移到同级的 _to_delete/ 下，带时间戳，可以事后人工核对或恢复。"""

from datetime import datetime
from pathlib import Path
import shutil

# 项目根目录：analysis/tools/safe_io.py 往上两级
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def retire_dir(path):
    """把文件夹 path 移到 path 的父目录下的 _to_delete/<文件夹名>_<YYYYMMDD-HHMMSS>/。

    - path 不存在：直接返回 None；
    - 移动前检查：path 必须位于项目根目录之内，且不能位于任何 raw 文件夹之内（路径中含 raw 段就报错退出）；
    - 返回移动后的新路径。
    """
    path = Path(path).resolve()
    if not path.exists():
        return None

    # 安全检查 1：必须在项目根目录之内
    if not path.is_relative_to(PROJECT_ROOT):
        raise RuntimeError(f"retire_dir 拒绝移动项目外的路径：{path}")

    # 安全检查 2：不能位于 raw 文件夹之内（路径任一段名为 raw）
    if "raw" in path.parts:
        raise RuntimeError(f"retire_dir 拒绝移动 raw 数据路径：{path}")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    trash_root = path.parent / "_to_delete"
    trash_root.mkdir(parents=True, exist_ok=True)

    target = trash_root / f"{path.name}_{stamp}"
    # 同一秒内重复移动同名文件夹时，加序号避免覆盖
    n = 2
    while target.exists():
        target = trash_root / f"{path.name}_{stamp}_{n}"
        n += 1

    shutil.move(str(path), str(target))
    print(f"  已移到 {target}", flush=True)
    return target
