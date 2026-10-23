"""运行时间、Git 状态、源码快照和脚本历史读取；不依赖具体研究对象。"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import ast
import shutil
import subprocess

from artifacts import sha256

TIMEZONE = "Asia/Shanghai"

def now():
    return datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="microseconds")

def run_id():
    return datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y%m%d_%H%M%S_%f")

def script_history(path):
    """只解析声明，不导入或执行被索引的脚本。"""
    for node in ast.parse(Path(path).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "SCRIPT_HISTORY" for target in node.targets):
            return ast.literal_eval(node.value)
    return []

def git_state(root, source_files):
    def git(*args):
        result = subprocess.run(["git", *args], cwd=root, capture_output=True,
                                text=True, timeout=10, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout.strip()
    try:
        head = git("rev-parse", "HEAD")
        tracked = git("status", "--porcelain=v1", "--untracked-files=no")
        paths = [str(Path(path).relative_to(root)) for path in source_files]
        selected = git("status", "--porcelain=v1", "--untracked-files=all", "--", *paths)
        return {"available": True, "commit": head, "branch": git("branch", "--show-current"),
                "tracked_worktree_dirty": bool(tracked),
                "source_worktree_dirty": bool(selected), "source_changes": selected.splitlines()}
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
        return {"available": False, "reason": str(error)}

def snapshot_sources(root, files, destination):
    """即使工作树尚未提交，也保存当次实际使用的文件内容。"""
    hashes = {}
    for source in sorted(set(Path(path).resolve() for path in files)):
        relative = source.relative_to(root)
        target = Path(destination) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[str(relative)] = sha256(target)
        if sha256(source) != hashes[str(relative)]:
            raise RuntimeError(f"制作快照时源码发生变化：{relative}")
    return hashes
