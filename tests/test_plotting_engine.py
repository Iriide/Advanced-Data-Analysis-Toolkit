import pandas as pd
from core.plotting_engine import PlottingEngine


def test_plot_data_returns_axes():
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    engine = PlottingEngine()
    ax, plotted = engine.plot_data(df, {"kind": "line"}, should_plot=True, show=False)
    assert plotted is True
    assert ax is not None


def test_plot_data_table_fallback():
    df = pd.DataFrame({"A": [1], "B": [2]})
    engine = PlottingEngine()
    ax, plotted = engine.plot_data(df, {}, should_plot=False, show=False)
    assert plotted is False
    assert ax is not None
