"""图表冒烟测试：用系统 python 检查 figures.py 能否跑通、中文字形是否缺失。

不写正式产物目录（FIGURE 输出到 experiments/scheduling/.figcheck/），
只验证 import、着色、字体、保存路径。用法：
    C:\\...\\Python312\\python.exe experiments/scheduling/src/figcheck.py --tag _g1
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import matplotlib
from matplotlib import font_manager, rcParams

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))

import figures  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="_g1")
    args = ap.parse_args()
    out = SRC.parent / ".figcheck"
    out.mkdir(exist_ok=True)
    figures.FIG = out

    figures.style.apply()
    rcParams["savefig.dpi"] = 300
    cjk = figures.style._pick_cjk_font()
    print(f"[font] 选中 = {cjk!r}")
    print(f"[font] 系统可用 CJK = "
          f"{[f.name for f in font_manager.fontManager.ttflist if 'YaHei' in f.name or 'SimHei' in f.name][:5]}")
    print(f"[palette] {figures.PALETTE}")

    df = figures.load_raw(args.tag)
    print(f"[data] {len(df)} 行, methods={sorted(df['method'].unique())}")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        figures.fig_main_bars(df)
        figures.fig_ecdf(args.tag)
        figures.fig_tradeoff(df)
        figures.fig_pairwise(df)
        figures.fig_timeline(args.tag)
        figures.fig_pareto_eps(args.tag)
        missing = [str(x.message)[:120] for x in w
                   if "missing from font" in str(x.message) or "Glyph" in str(x.message)]
    files = sorted(out.glob("*.png"))
    print(f"[out] {len(files)} 张图 -> {out}")
    for p in files:
        print(f"   {p.name:34s} {p.stat().st_size / 1024:7.1f} KB")
    if missing:
        print(f"[FAIL] {len(missing)} 条缺字形警告（中文会变方框）：")
        for m in missing[:5]:
            print("   ", m)
        sys.exit(1)
    print("[ok] 无缺字形警告，中文字体正常")


if __name__ == "__main__":
    main()
