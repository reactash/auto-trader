from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus

from config.settings import settings
from engine.models import log_trade_open, log_trade_close, get_open_trades
from utils.logger import logger


class AlpacaTrader:
    """Alpaca paper trading execution engine."""

    def __init__(self):
        self.client = TradingClient(
            settings.ALPACA_API_KEY,
            settings.ALPACA_SECRET_KEY,
            paper=True,
        )
        logger.info("Alpaca paper trading client initialized")

    def get_account(self) -> dict:
        """Get current account info (balance, buying power, etc)."""
        account = self.client.get_account()
        return {
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
            "equity": float(account.equity),
            "daily_pnl": float(account.equity) - float(account.last_equity),
        }

    def get_positions(self) -> list[dict]:
        """Get all open positions from Alpaca."""
        positions = self.client.get_all_positions()
        return [{
            "symbol": p.symbol,
            "qty": int(p.qty),
            "side": "buy" if float(p.qty) > 0 else "sell",
            "entry_price": float(p.avg_entry_price),
            "current_price": float(p.current_price),
            "market_value": float(p.market_value),
            "unrealized_pnl": float(p.unrealized_pl),
            "unrealized_pnl_pct": float(p.unrealized_plpc) * 100,
        } for p in positions]

    def place_order(self, symbol: str, qty: int, side: str,
                    stop_loss: float, take_profit: float) -> dict | None:
        """
        Place a market order on Alpaca paper trading.
        Also logs the trade in our SQLite DB.
        """
        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL

        try:
            # Place main market order
            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=TimeInForce.DAY,
            )
            order = self.client.submit_order(order_request)

            # Log to our DB
            trade_id = log_trade_open(
                symbol=symbol,
                side=side,
                qty=qty,
                entry_price=float(order.filled_avg_price) if order.filled_avg_price else 0.0,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            logger.info(
                f"Order placed: {side.upper()} {qty} {symbol} | "
                f"Alpaca ID: {order.id} | DB ID: {trade_id}"
            )

            return {
                "trade_id": trade_id,
                "alpaca_order_id": str(order.id),
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "status": order.status.value,
            }

        except Exception as e:
            logger.error(f"Order failed: {side} {qty} {symbol}: {e}")
            return None

    def close_position(self, symbol: str, trade_id: int | None = None,
                       reason: str = "manual") -> bool:
        """Close a specific position."""
        try:
            self.client.close_position(symbol)

            # Update our DB if we have the trade ID
            if trade_id:
                positions = self.get_positions()
                # Get the fill price (position just closed, so get current price)
                from data.market_data import get_latest_quote
                quote = get_latest_quote(symbol)
                exit_price = quote["bid_price"] if quote else 0.0
                log_trade_close(trade_id, exit_price, reason)

            logger.info(f"Position closed: {symbol} ({reason})")
            return True

        except Exception as e:
            logger.error(f"Failed to close {symbol}: {e}")
            return False

    def close_all_positions(self, reason: str = "end_of_day") -> int:
        """Close all open positions. Returns number of positions closed."""
        try:
            self.client.close_all_positions(cancel_orders=True)

            # Update our DB
            open_trades = get_open_trades()
            for trade in open_trades:
                from data.market_data import get_latest_quote
                quote = get_latest_quote(trade["symbol"])
                exit_price = quote["bid_price"] if quote else 0.0
                log_trade_close(trade["id"], exit_price, reason)

            count = len(open_trades)
            logger.info(f"All positions closed: {count} positions ({reason})")
            return count

        except Exception as e:
            logger.error(f"Failed to close all positions: {e}")
            return 0

    def get_order_history(self, limit: int = 50) -> list[dict]:
        """Get recent order history from Alpaca."""
        request = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            limit=limit,
        )
        orders = self.client.get_orders(request)
        return [{
            "id": str(o.id),
            "symbol": o.symbol,
            "side": o.side.value,
            "qty": o.qty,
            "filled_qty": o.filled_qty,
            "type": o.type.value,
            "status": o.status.value,
            "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
            "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
        } for o in orders]
