import logging
from datetime import datetime
from typing import List, Optional

import pandas as pd
from mysharelib.blob_cache import calculate_cache_ttl, constant_ttl
from mysharelib.tools import setup_logger
from openbb_app import project_name
from openbb_app.core.config import config
from openbb_core.app.utils import get_user_cache_directory

setup_logger(project_name)

logger = logging.getLogger(__name__)

# Excel sheet names (as used in the workbook)
SHANGHAI_SHEET = "SS"
SHENZHEN_SHEET = "SZ"
HONGKONG_SHEET = "HK"

# Market codes used in the data's 'Market' column
MARKET_SH = "SH"
MARKET_HK = "HK"

REALIZED = "Realized"
SHORTLIST = "Shortlist"


class EquityData:
    """
    Utility to read and query equity transaction data from
    an Excel workbook.

    The class loads transaction sheets at initialization and exposes simple
    query helpers. It is intentionally lightweight: failures to read the
    workbook fall back to empty DataFrames so callers can still operate
    (they'll simply see empty results).
    """

    totals = {}

    def __init__(self) -> None:
        self._transactions_file = (
            f"{get_user_cache_directory()}/{config.data_folder_path}/{config.data_file}"
        )
        self._load_data()

        # initialize total
        self.total = 0

        # cache for current prices
        self._current_prices_ttl = datetime.now()
        self._is_realized: bool = False
        self._prices: List[dict] = []

        self.default_start_date = "2010-01-01"

    def get_all_data(self, filter: str = "") -> pd.DataFrame:
        """Return all transaction rows including realized and unrealized.

        If a pandas query string is provided via ``filter`` it will be
        applied to the concatenated DataFrame.
        """
        combined = pd.concat(
            [self._data, self._realized_data], ignore_index=True, sort=False
        )
        if filter:
            return combined.query(filter)
        return combined

    def get_data(
        self,
        market: str = MARKET_SH,
        symbol: Optional[int] = None,
        is_realized: bool = False,
    ) -> pd.DataFrame:
        """Return rows for a given market and optionally a specific symbol.

        market: 'SH' or 'HK'
        symbol: integer symbol identifier; when None no symbol filter is applied
        is_realized: whether to include realized rows as well
        """
        raw_data = self.get_all_data() if is_realized else self._data

        if symbol is not None:
            return raw_data.query(f"Market == '{market}' and Symbol == {symbol}")

        # no symbol specified -> return all rows for the market
        if market == MARKET_HK:
            return raw_data.query("Market == 'HK'")
        return raw_data.query("Market == 'SH'")

    def get_holding(
        self, market: str = MARKET_SH, is_realized: bool = False
    ) -> pd.DataFrame:
        """Return aggregated holdings (Name, Price, Quantity, Total) by Symbol.

        The ``is_realized`` flag should be False in get_holding.
        """
        data = self.get_data(market=market, is_realized=False)
        return self._get_holding(data)

    def get_transactions(
        self,
        symbol: Optional[int] = None,
        market: str = MARKET_SH,
        is_realized: bool = False,
    ) -> pd.DataFrame:
        """Return transactions for a symbol (or all transactions for market).

        If ``symbol`` is provided the result is filtered to that symbol. If
        not provided, all transactions for the given market are returned.
        """
        transactions = self.get_all_data() if is_realized else self._data

        if symbol is not None:
            return transactions.query(f"Market == '{market}' and Symbol == {symbol}")

        # return empty DataFrame if no symbol is specified
        return pd.DataFrame()

    def get_symbols(self, market: str = MARKET_SH, is_realized: bool = False) -> str:
        """Return a comma-separated, zero-padded list of symbol ids for the market.

        HK symbols are padded to 5 characters; other markets to 6.
        """
        raw_data = self.get_all_data() if is_realized else self._data

        if market == MARKET_HK:
            market_data = raw_data.query("Market == 'HK'")
            if market_data.empty:
                return ""
            symbols = market_data["Symbol"].dropna().unique()
            return ",".join(str(int(s)).zfill(5) for s in sorted(symbols))

        market_data = raw_data.query("Market != 'HK'")
        if market_data.empty:
            return ""
        symbols = market_data["Symbol"].dropna().unique()
        return ",".join(str(int(s)).zfill(6) for s in sorted(symbols))

    def get_current_prices(
        self, is_realized: bool, market: str = MARKET_SH
    ) -> List[dict]:
        """Return current prices for all held symbols as a list of dicts."""
        if (
            self._prices
            and datetime.now() < self._current_prices_ttl
            and self._is_realized == is_realized
        ):
            logger.info("Using cached current prices with is_realized=%s", is_realized)
            return self._prices

        symbols = self.get_symbols(market=market, is_realized=is_realized)
        if not symbols:
            logger.warning(
                "No symbols found for market=%s with is_realized=%s",
                market,
                is_realized,
            )
            return []

        logger.info(
            "Fetching current prices from provider with is_realized=%s: %s",
            is_realized,
            symbols,
        )

        from openbb_app.core.utils import get_quote

        self._is_realized = is_realized
        self._current_prices_ttl = calculate_cache_ttl(constant_ttl, 60)
        self._prices = get_quote(symbols)

        return self._prices

    def _load_data(self):
        """Load all data from the workbook with safe fallbacks."""
        self._data = self._load_unrealized_data()
        self._realized_data = self._load_extra_data()

    def _load_unrealized_data(self) -> pd.DataFrame:
        """Safely load primary sheets (Hong Kong + Shanghai/Shenzhen) from the workbook.

        If the file or sheets are missing an empty DataFrame is returned and a
        message is logged.
        """
        try:
            hk_data = pd.read_excel(self._transactions_file, HONGKONG_SHEET)
        except Exception as e:  # sheet/file missing or read error
            logger.debug("Could not read HK sheet: %s", e)
            hk_data = pd.DataFrame()

        try:
            ss_data = pd.read_excel(self._transactions_file, SHANGHAI_SHEET)
        except Exception as e:
            logger.debug("Could not read Shanghai sheet: %s", e)
            ss_data = pd.DataFrame()

        if hk_data.empty and ss_data.empty:
            return pd.DataFrame()

        return pd.concat([hk_data, ss_data], ignore_index=True, sort=False).fillna(0)

    def _load_extra_data(self) -> pd.DataFrame:
        """Load supplemental sheets (shortlist + realized) with safe fallbacks."""
        try:
            st_data = pd.read_excel(self._transactions_file, SHORTLIST)
        except Exception as e:
            logger.debug("Could not read Shortlist sheet: %s", e)
            st_data = pd.DataFrame()

        try:
            r_data = pd.read_excel(self._transactions_file, REALIZED)
        except Exception as e:
            logger.debug("Could not read Realized sheet: %s", e)
            r_data = pd.DataFrame()

        if st_data.empty and r_data.empty:
            return pd.DataFrame()

        return pd.concat([st_data, r_data], ignore_index=True, sort=False).fillna(0)

    def _get_holding(self, data: pd.DataFrame) -> pd.DataFrame:
        """Aggregate holdings by Symbol and return a tidy DataFrame.

        The returned DataFrame has columns: Name, Price, Quantity, Total
        and is indexed by Symbol.
        """
        if data is None or data.empty:
            return pd.DataFrame(columns=["Name", "Price", "Quantity", "Total"])

        data_total = data.groupby("Symbol")["Total"].sum()
        data_quantity = data.groupby("Symbol")["Quantity"].sum()
        data_price = data.groupby("Symbol")["Price"].mean()
        data_name = data.groupby("Symbol")["Name"].first()

        df = pd.DataFrame(
            {
                "Name": data_name,
                "Price": data_price,
                "Quantity": data_quantity,
                "Total": data_total,
            }
        )

        # Ensure sensible dtypes and fill missing numeric values with 0
        for col in ("Price", "Quantity", "Total"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        return df

    def get_screener(
        self,
        is_realized: bool,
        market: str = MARKET_SH,
        use_cache: bool = True,
        strategy_rate: float = 0.05,
    ) -> str:
        """
        Get screener data
        This is a HTML static version of the stock screener.
        """
        logger.info(
            "Calling get_screener with is_realized=%s, market=%s", is_realized, market
        )
        stocks = self.get_current_prices(is_realized=is_realized, market=market)

        if not use_cache:
            logger.info("Reloading transactions data.")
            self._load_data()

        def calculate_position(close, low, high):
            if high <= low:
                return 0
            return ((close - low) / (high - low)) * 100

        html_template = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
        <meta charset="UTF-8">
        <title>股票行情表（静态版）</title>
        <style>
            body {{
            background-color: #0f0f0f;
            color: #fff;
            font-family: 'Segoe UI', Arial, sans-serif;
            padding: 20px;
            }}
            table {{
            width: 100%;
            border-collapse: collapse;
            background-color: #1a1a1a;
            border-radius: 8px;
            overflow: hidden;
            }}
            th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #333;
            }}
            th {{
            background-color: #222;
            font-weight: bold;
            color: #ccc;
            }}
            .price-range-container {{
            position: relative;
            height: 24px;
            background: #2d2d2d;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 8px;
            font-size: 12px;
            color: #aaa;
            min-width: 100px;
            }}
            .range-indicator {{
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            width: 0;
            height: 0;
            border-left: 6px solid transparent;
            border-right: 6px solid transparent;
            border-top: 10px solid #1e90ff;
            pointer-events: none;
            }}
            .change-down {{ color: #ff6b6b; }}
            .change-up {{ color: #4caf50; }}
            .price-value {{ font-weight: bold; color: #fff; }}
        </style>
        </head>
        <body>

        <table>
        <thead>
            <tr>
            <th>代码</th>
            <th>名称</th>
            <th>现价</th>
            <th>52周价格</th>
            <th>策略</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
        </table>

        </body>
        </html>
        """

        row_template = """
            <tr>
            <td>{symbol}</td>
            <td>{name}</td>
            <td class="price-value">{close:.2f}</td>
            <td>
                <div class="price-range-container">
                <span>{low_52w:.2f}</span>
                <span>{high_52w:.2f}</span>
                <div class="range-indicator" style="left: {position:.2f}%"></div>
                </div>
            </td>
            <td class="change-{strategy_class}">{strategy}</td>
            </tr>
        """

        rows = []
        for s in stocks:
            from openbb_app.core.utils import BUY, SELL, get_strategies
            from openbb_app.routes.portfolio import get_stock_name_by_search

            pos = calculate_position(
                s["current_price"], s["fifty_two_week_low"], s["fifty_two_week_high"]
            )
            trading_strategy = get_strategies(
                s["fifty_two_week_low"],
                s["fifty_two_week_high"],
                s["current_price"],
                strategy_rate,
            )
            strategy_class = (
                "down"
                if trading_strategy == SELL
                else ("up" if trading_strategy == BUY else "hold")
            )
            row = row_template.format(
                symbol=s["symbol"],
                name=get_stock_name_by_search(s["symbol"]),
                close=s["current_price"],
                low_52w=s["fifty_two_week_low"],
                high_52w=s["fifty_two_week_high"],
                position=pos,
                strategy=trading_strategy,
                strategy_class=strategy_class,
            )
            rows.append(row)

        return html_template.format(rows="\n".join(rows))
