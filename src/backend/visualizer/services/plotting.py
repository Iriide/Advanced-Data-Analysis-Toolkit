import matplotlib

# Use a non-interactive backend to avoid starting a GUI (Tk) from
# worker threads or server contexts. Must be set before importing
# `pyplot`.
try:
    matplotlib.use("Agg")
except Exception:
    # If backend can't be set (already set elsewhere), continue.
    pass

import matplotlib.pyplot as plt
import pandas as pd
from typing import Dict, Any, Tuple, Optional
from collections.abc import Iterable
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.table import Table, Cell
from backend.utils.logger import get_logger
import numpy as np
import tempfile
from pathlib import Path

logger = get_logger(__name__)

CELL_PADDING = 2
INCHES_PER_CHARACTER = 0.12
MAXIMUM_FIGURE_INCHES = 20
MINIMUM_FIGURE_INCHES = 4
HEADER_BACKGROUND_COLOR = "#40466e"
ALTERNATE_ROW_COLOR = "#f5f5f5"
CELL_EDGE_COLOR = "#dddddd"


class PlottingEngine:
    """
    Handles generation of matplotlib figures from DataFrames.
    """

    @staticmethod
    def _calculate_column_widths(dataframe: pd.DataFrame) -> list[int]:
        """Calculate column widths based on content and header length."""
        column_widths: list[int] = [0] * len(dataframe.columns)
        for i, column in enumerate(dataframe.columns):
            maximum_data_length = (
                dataframe[column].astype(str).map(len).max()
                if not dataframe[column].empty
                else 0
            )
            header_length = len(str(column))
            column_widths[i] = max(maximum_data_length, header_length) + CELL_PADDING
        return column_widths

    @staticmethod
    def _style_header_cell(cell: Cell) -> None:
        """Apply header styling to a table cell."""
        cell.set_text_props(weight="bold", color="white")
        cell.set_facecolor(HEADER_BACKGROUND_COLOR)
        cell.set_edgecolor("white")

    @staticmethod
    def _style_data_cell(cell: Cell, row_index: int) -> None:
        """Apply alternating row styling to a data cell."""
        cell.set_edgecolor(CELL_EDGE_COLOR)
        if row_index % 2 == 0:
            cell.set_facecolor(ALTERNATE_ROW_COLOR)
        else:
            cell.set_facecolor("white")

    @staticmethod
    def _apply_table_styling(table: Table) -> None:
        """Apply consistent styling to a matplotlib table."""
        table.scale(1, 1.5)
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        for (row_index, _), cell in table.get_celld().items():
            if row_index == 0:
                PlottingEngine._style_header_cell(cell)
            else:
                PlottingEngine._style_data_cell(cell, row_index)

    @staticmethod
    def _create_table(
        axes: Axes, dataframe: pd.DataFrame, relative_widths: list[float]
    ) -> None:
        """Create and render a styled table on the given axes."""
        table = axes.table(
            cellText=dataframe.values.tolist(),
            colLabels=dataframe.columns.tolist(),
            loc="center",
            cellLoc="center",
            colWidths=relative_widths,
        )
        PlottingEngine._apply_table_styling(table)

    @staticmethod
    def _calculate_figure_dimensions(
        column_widths: list[int], row_count: int
    ) -> Tuple[float, float]:
        """Compute figure dimensions based on table size."""
        total_characters = sum(column_widths)
        figure_width = max(
            MINIMUM_FIGURE_INCHES,
            min(total_characters * INCHES_PER_CHARACTER, MAXIMUM_FIGURE_INCHES),
        )
        figure_height = min(max(2, 0.4 * (row_count + 1)), 10)
        return figure_width, figure_height

    @staticmethod
    def _render_dataframe_as_table(dataframe: pd.DataFrame) -> Tuple[Figure, Axes]:
        """Render a dataframe as a matplotlib table."""
        column_widths = PlottingEngine._calculate_column_widths(dataframe)
        total_characters = sum(column_widths)
        relative_widths = [width / total_characters for width in column_widths]

        figure_width, figure_height = PlottingEngine._calculate_figure_dimensions(
            column_widths, len(dataframe)
        )
        figure, axes = plt.subplots(figsize=(figure_width, figure_height))
        figure.patch.set_visible(False)
        axes.axis("off")
        axes.axis("tight")

        PlottingEngine._create_table(axes, dataframe, relative_widths)
        figure.tight_layout()
        return figure, axes

    def _attempt_plot(
        self, dataframe: pd.DataFrame, plot_parameters: Dict[str, Any], verbosity: int
    ) -> Tuple[Optional[Axes], bool]:
        """Attempt to plot the dataframe using provided parameters."""
        try:
            axes = dataframe.plot(**plot_parameters)
            return axes, True
        except (TypeError, ValueError, KeyError) as error:
            if verbosity > 0:
                logger.warning(f"Plotting failed: {error}. Falling back to table.")
            return None, False

    def plot_data(
        self,
        dataframe: pd.DataFrame,
        plot_parameters: Dict[str, Any],
        should_plot: bool,
        show: bool = True,
        verbosity: int = 0,
    ) -> Tuple[Optional[Axes], bool]:
        """
        Plots the dataframe or renders as table based on params.

        Args:
            df (pd.DataFrame): Data to plot.
            plot_params (Dict): Kwargs for df.plot().
            should_plot (bool): LLM recommendation on whether to plot.
            show (bool): Whether to call plt.show().
            verbosity (int): Verbosity level.

        Returns:
            Tuple[Axes, bool]: The axes object and a boolean
            indicating if plot was successful.
        """
        axes = None
        plot_succeeded = False

        if should_plot:
            axes, plot_succeeded = self._attempt_plot(
                dataframe, plot_parameters, verbosity
            )

        if not plot_succeeded:
            _, axes = self._render_dataframe_as_table(dataframe)
            should_plot = False

        if show:
            plt.show()

        if not should_plot and verbosity > 0:
            logger.warning(
                "LLM recommended not to plot this result; showing table instead."
            )
        return axes, should_plot


def _extract_figure(axes: Any) -> Optional[Figure]:
    fig = None
    if isinstance(axes, Axes):
        fig = axes.get_figure()
    elif isinstance(axes, Iterable):
        # Handle cases like plt.subplots(2, 2) which return a NumPy array
        for item in np.asarray(axes).flatten():
            if isinstance(item, (Axes, Iterable)):
                target = list(item)[0] if isinstance(item, Iterable) else item
                fig = target.get_figure()
    if not isinstance(fig, Figure):
        raise TypeError("Could not extract Figure from the provided axes.")
    return fig


def save_plot(
    axes: Any,
    fmt: str = "svg",
    plots_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Save the plot associated with the given axes in the specified format."""
    if plots_dir is None:
        plots_dir = Path(tempfile.gettempdir())
    plots_dir.mkdir(parents=True, exist_ok=True)
    plot_path = plots_dir / f"plot_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.{fmt}"
    fig = _extract_figure(axes)
    if fig is None:
        logger.error("No figure found to save.")
        return None
    if fmt == "svg":
        fig.savefig(plot_path, format="svg")
    elif fmt == "png":
        fig.savefig(plot_path, format="png", dpi=300)
    else:
        logger.error(f"Unsupported format: {fmt}")
        return None
    logger.info(f"Plot saved to: {plot_path}")
    return plot_path


if __name__ == "__main__":
    dataframe = pd.DataFrame(np.random.rand(10, 2), columns=["A", "B"])
    engine = PlottingEngine()
    logger.info("Testing plot engine...")
    engine.plot_data(dataframe, {"kind": "bar"}, should_plot=True, show=True)
