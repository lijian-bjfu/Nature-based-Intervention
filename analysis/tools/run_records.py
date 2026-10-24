"""运行时间、Git 状态、源码记录和脚本历史读取；不依赖具体研究对象。"""
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

def record_sources(root, files, destination):
    """记录当次使用的源码，不整份复制。

    已提交的文件靠 Git 提交号即可还原，只记 SHA-256；有未提交修改或尚未纳入版本库的文件，
    才复制到 destination（通常只有当次正在改的一两个脚本）。Git 不可用时全部复制。
    返回 (全部文件的 SHA-256, 被复制的文件列表)。
    """
    sources = sorted(set(Path(path).resolve() for path in files))
    relatives = [str(source.relative_to(root)) for source in sources]
    try:
        status = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "--", *relatives],
                                cwd=root, capture_output=True, text=True, timeout=10, check=True).stdout
        changed = {line[3:].strip().strip('"') for line in status.splitlines() if line.strip()}
    except (OSError, subprocess.SubprocessError):
        changed = set(relatives)
    hashes, copied = {}, []
    for source, relative in zip(sources, relatives):
        hashes[relative] = sha256(source)
        if relative in changed:
            target = Path(destination) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if sha256(target) != hashes[relative]:
                raise RuntimeError(f"复制时源码发生变化：{relative}")
            copied.append(relative)
    return hashes, copied
