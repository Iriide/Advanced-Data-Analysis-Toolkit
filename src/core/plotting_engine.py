import matplotlib.pyplot as plt
import pandas as pd
from typing import Dict, Any, Tuple, Optional
from matplotlib.axes import Axes
from core.logger import get_logger

logger = get_logger(__name__)


class PlottingEngine:
    """
    Handles generation of matplotlib figures from DataFrames.
    """

    @staticmethod
    def _plot_df_as_table(df: pd.DataFrame) -> Tuple[plt.Figure, Axes]:
        """Renders DataFrame as a styled matplotlib table with dynamic column widths."""

        # --- 1. Calculate Column Widths ---
        col_widths = []
        for col in df.columns:
            max_data_len = (
                df[col].astype(str).map(len).max() if not df[col].empty else 0
            )
            # Length of the header
            header_len = len(str(col))
            # Take the max and add a little padding (e.g., 2 chars)
            col_widths.append(max(max_data_len, header_len) + 2)

        total_chars = sum(col_widths)
        # Calculate relative column widths based on max content length
        rel_widths = [w / total_chars for w in col_widths]
        # Figure width is estimated by converting total character count to inches (heuristic: 0.12 inches per character)

        # --- 2. Dynamic Figure Size ---
        fig_width = max(
            4, min(total_chars * 0.12, 20)
        )  # ~0.12 inches per character for 10pt
        fig_height = min(max(2, 0.4 * (len(df) + 1)), 10)

        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        fig.patch.set_visible(False)
        ax.axis("off")
        ax.axis("tight")

        # --- 3. Create Table ---
        table = ax.table(
            cellText=df.values.tolist(),
            colLabels=df.columns.tolist(),
            loc="center",
            cellLoc="center",
            colWidths=rel_widths,
        )

        # --- 4. Styling ---
        table.scale(1, 1.5)
        table.auto_set_font_size(False)
        table.set_fontsize(10)

        for (row, _), cell in table.get_celld().items():
            if row == 0:
                # Header Style
                cell.set_text_props(weight="bold", color="white")
                cell.set_facecolor("#40466e")
                cell.set_edgecolor("white")
            else:
                # Data Style
                cell.set_edgecolor("#dddddd")
                if row % 2 == 0:
                    cell.set_facecolor("#f5f5f5")
                else:
                    cell.set_facecolor("white")

        fig.tight_layout()
        return fig, ax

    def plot_data(
        self,
        df: pd.DataFrame,
        plot_params: Dict[str, Any],
        should_plot: bool,
        show: bool = True,
        verbose: int = 0,
    ) -> Tuple[Optional[Axes], bool]:
        """
        Plots the dataframe or renders as table based on params.

        Args:
            df (pd.DataFrame): Data to plot.
            plot_params (Dict): Kwargs for df.plot().
            should_plot (bool): LLM recommendation on whether to plot.
            show (bool): Whether to call plt.show().
            verbose (int): Verbosity level.

        Returns:
            Tuple[Axes, bool]: The axes object and a boolean
            indicating if plot was successful.
        """
        ax = None
        success = False

        if should_plot:
            try:
                ax = df.plot(**plot_params)
                success = True
            except Exception as e:
                if verbose > 0:
                    logger.warning("Plotting failed: %s. Falling back to table.", e)

        if not success:
            # If LLM said don't plot, or if plotting failed, show table
            _, ax = self._plot_df_as_table(df)

        if show:
            plt.show()
            self.cleanup_figures(ax)

        if not should_plot and verbose > 0:
            logger.warning(
                "LLM recommended not to plot this result; showing table instead."
            )

        return ax, should_plot

    def cleanup_figures(self, ax: Any) -> None:
        """Helper to safely close figures."""
        fig = None
        try:
            if hasattr(ax, "__iter__") and not isinstance(ax, Axes):
                first = None
                for item in ax:
                    if hasattr(item, "get_figure"):
                        first = item
                        break
                fig = first.get_figure() if first is not None else plt.gcf()
            elif hasattr(ax, "get_figure"):
                fig = ax.get_figure()
            else:
                fig = plt.gcf()

            plt.close(fig)
        except Exception:
            plt.close("all")


if __name__ == "__main__":
    import numpy as np

    # Sample usage
    df = pd.DataFrame(np.random.rand(10, 2), columns=["A", "B"])
    engine = PlottingEngine()
    logger.info("Testing plot engine...")
    engine.plot_data(df, {"kind": "bar"}, should_plot=True, show=True)
