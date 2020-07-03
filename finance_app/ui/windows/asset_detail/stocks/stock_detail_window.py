from business.model.asset import Asset
from ui.windows.asset_detail.shared.asset_detail_window import (
    AssetDetailWindow,
)


class StockDetailWindow(AssetDetailWindow):
    def __init__(self, asset: Asset):
        super().__init__(asset)
