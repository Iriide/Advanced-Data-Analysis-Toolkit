import matplotlib.pyplot as plt
import pandas as pd
from typing import Dict, Any, Tuple, Optional
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.table import Table, Cell
from backend.utils.logger import get_logger

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
        cell.set_text_props(weight="bold", color="white")
        cell.set_facecolor(HEADER_BACKGROUND_COLOR)
        cell.set_edgecolor("white")

    @staticmethod
    def _style_data_cell(cell: Cell, row_index: int) -> None:
        cell.set_edgecolor(CELL_EDGE_COLOR)
        if row_index % 2 == 0:
            cell.set_facecolor(ALTERNATE_ROW_COLOR)
        else:
            cell.set_facecolor("white")

    @staticmethod
    def _apply_table_styling(table: Table) -> None:
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
        total_characters = sum(column_widths)
        figure_width = max(
            MINIMUM_FIGURE_INCHES,
            min(total_characters * INCHES_PER_CHARACTER, MAXIMUM_FIGURE_INCHES),
        )
        figure_height = min(max(2, 0.4 * (row_count + 1)), 10)
        return figure_width, figure_height

    @staticmethod
    def _render_dataframe_as_table(dataframe: pd.DataFrame) -> Tuple[Figure, Axes]:
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
        try:
            axes = dataframe.plot(**plot_parameters)
            return axes, True
        except (TypeError, ValueError, KeyError) as error:
            if verbosity > 0:
                logger.warning("Plotting failed: %s. Falling back to table.", error)
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
            verbose (int): Verbosity level.

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
            self._close_figure(axes)

        if not should_plot and verbosity > 0:
            logger.warning(
                "LLM recommended not to plot this result; showing table instead."
            )
        return axes, should_plot


    def _extract_figure_from_axes(self, axes: Any) -> Optional[Figure]:
        if hasattr(axes, "__iter__") and not isinstance(axes, Axes):
            for item in axes:
                if hasattr(item, "get_figure"):
                    return cast(Figure, item.get_figure())
            return plt.gcf()
        if hasattr(axes, "get_figure"):
            return cast(Figure, axes.get_figure())
        return plt.gcf()

    def _close_figure(self, axes: Any) -> None:
        try:
            figure = self._extract_figure_from_axes(axes)
            plt.close(figure)
        except (AttributeError, TypeError):
            plt.close("all")


if __name__ == "__main__":
    import numpy as np

    dataframe = pd.DataFrame(np.random.rand(10, 2), columns=["A", "B"])
    engine = PlottingEngine()
    logger.info("Testing plot engine...")
    engine.plot_data(dataframe, {"kind": "bar"}, should_plot=True, show=True)
