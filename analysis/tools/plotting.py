"""跨来源共用绘图工具，展示参数由调用方明确传入。"""
import os
from paths import CACHE

def pyplot(options):
    CACHE.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR",str(CACHE/"matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family":options.font, "font.size":options.font_size,
        "axes.unicode_minus":False,"axes.spines.top":False,"axes.spines.right":False,
        "axes.titleweight":"bold","savefig.dpi":options.dpi,
    })
    return plt

def save_figure(figure,folder,stem,options):
    paths=[]
    for extension in options.formats:
        path=folder/(stem+"."+extension)
        figure.savefig(path,bbox_inches="tight")
        paths.append(path.name)
    return paths
