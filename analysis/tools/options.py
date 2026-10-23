"""调用方明确传入的通用展示选项与基本校验；不读取任何参数文件。"""
from dataclasses import dataclass
import math
import numbers

@dataclass(frozen=True)
class FigureOptions:
    dpi: int
    formats: tuple
    font: str
    font_size: float

def string_list(value, key):
    if not isinstance(value, (list, tuple)) or not value or any(
            not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{key} 必须是非空文字列表，例如 ['*']")
    return tuple(value)

def positive(value, key):
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{key} 必须是大于 0 的有限数值，当前为 {value!r}")
    return float(value)

def figure_options(values, overrides=None):
    from matplotlib.colors import is_color_like
    overrides = overrides or {}
    dpi = positive(overrides.get("figure_dpi", values["dpi"]), "figure.dpi")
    if not dpi.is_integer():
        raise ValueError("figure.dpi 必须是正整数")
    formats = string_list(overrides.get("figure_formats", values["formats"]), "figure.formats")
    if len(set(formats)) != len(formats) or set(formats)-{"png", "svg", "pdf"}:
        raise ValueError("figure.formats 不能重复，只支持 png、svg、pdf")
    if not isinstance(values["font"], str) or not values["font"].strip():
        raise ValueError("figure.font 不能为空")
    return FigureOptions(int(dpi), formats, values["font"], positive(values["font_size"], "figure.font_size"))

def valid_colors(colors, required):
    from matplotlib.colors import is_color_like
    if not isinstance(colors, dict) or not set(required).issubset(colors):
        raise ValueError(f"description.colors 必须包含 {sorted(required)}")
    if any(not is_color_like(colors[key]) for key in required):
        raise ValueError("description.colors 包含无效颜色")
    return dict(colors)
