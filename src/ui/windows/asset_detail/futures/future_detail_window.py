from src.business.model.asset import Asset
from src.ui.windows.asset_detail.shared.asset_detail_window import (
    AssetDetailWindow,
)
from src.ui.windows.asset_detail.futures.pages.history_table.history_table import (
    FutureHistoryTablePage,
)
from src.ui.windows.asset_detail.futures.pages.history_chart.history_chart import (
    FutureHistoryChartPage,
)


class FutureDetailWindow(AssetDetailWindow):
    def __init__(self, asset: Asset):
        super().__init__(asset)

        # MenuBar actions
        self.actionTable.triggered.connect(
            self.setCurrentPage(FutureHistoryTablePage, asset=self.asset)
        )
        self.actionChart.triggered.connect(
            self.setCurrentPage(FutureHistoryChartPage, asset=self.asset)
        )

        self.setCurrentPage(FutureHistoryChartPage, asset=self.asset)()
