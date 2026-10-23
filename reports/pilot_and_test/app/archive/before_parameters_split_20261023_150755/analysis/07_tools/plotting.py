"""共用绘图样式与保存；不依赖某个被试、会话或数据来源。"""
import os
import settings

def pyplot():
    settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(settings.CACHE_DIR / "matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": settings.PLOT["font"], "font.size": 10,
        "axes.unicode_minus": False, "axes.spines.top": False, "axes.spines.right": False,
        "axes.titleweight": "bold", "savefig.dpi": settings.PLOT["dpi"],
    })
    return plt

def save_figure(figure, folder, stem):
    paths = []
    for extension in settings.PLOT["formats"]:
        path = folder / (stem + "." + extension)
        figure.savefig(path, bbox_inches="tight")
        paths.append(path.name)
    return paths
