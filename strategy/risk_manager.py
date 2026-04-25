import math

from config.settings import settings
from utils.logger import logger


def calculate_position_size(capital: float, entry_price: float, stop_loss: float,
                            risk_pct: float | None = None) -> int:
    """
    Calculate number of shares based on risk per trade.
    Formula: qty = (capital * risk%) / (entry_price - stop_loss)
    """
    if risk_pct is None:
        risk_pct = settings.MAX_RISK_PER_TRADE

    risk_amount = capital * risk_pct
    risk_per_share = abs(entry_price - stop_loss)

    if risk_per_share <= 0:
        logger.warning("Invalid stop loss — risk per share is 0")
        return 0

    qty = math.floor(risk_amount / risk_per_share)

    # Don't let position exceed 20% of capital
    max_qty = math.floor((capital * 0.20) / entry_price)
    qty = min(qty, max_qty)

    # Minimum 1 share
    qty = max(qty, 1) if qty > 0 else 0

    logger.debug(
        f"Position size: {qty} shares | Risk: ${risk_amount:.2f} | "
        f"Per share risk: ${risk_per_share:.2f}"
    )
    return qty


def get_stop_loss(entry_price: float, atr: float, side: str = "buy",
                  multiplier: float | None = None) -> float:
    """Calculate ATR-based stop loss."""
    if multiplier is None:
        multiplier = 1.5

    if side == "buy":
        stop = entry_price - (atr * multiplier)
    else:
        stop = entry_price + (atr * multiplier)

    return round(stop, 2)


def get_take_profit(entry_price: float, stop_loss: float, side: str = "buy",
                    rr_ratio: float | None = None) -> float:
    """Calculate take profit based on risk-reward ratio."""
    if rr_ratio is None:
        rr_ratio = settings.RISK_REWARD_RATIO

    risk = abs(entry_price - stop_loss)
    reward = risk * rr_ratio

    if side == "buy":
        target = entry_price + reward
    else:
        target = entry_price - reward

    return round(target, 2)


def check_daily_loss_limit(current_pnl: float, capital: float,
                           max_loss_pct: float | None = None) -> bool:
    """Check if daily loss limit is hit. Returns True if should STOP trading."""
    if max_loss_pct is None:
        max_loss_pct = settings.MAX_DAILY_LOSS

    max_loss = capital * max_loss_pct
    if current_pnl <= -max_loss:
        logger.warning(f"DAILY LOSS LIMIT HIT: ${current_pnl:.2f} (limit: -${max_loss:.2f})")
        return True
    return False


def check_profit_target(current_pnl: float, capital: float,
                        target_pct: float | None = None) -> bool:
    """Check if daily profit target is met. Returns True if target reached."""
    if target_pct is None:
        target_pct = settings.PROFIT_TARGET

    target = capital * target_pct
    if current_pnl >= target:
        logger.info(f"DAILY PROFIT TARGET REACHED: ${current_pnl:.2f} (target: ${target:.2f})")
        return True
    return False


def should_trail_stop(current_price: float, entry_price: float, current_stop: float,
                      atr: float, side: str = "buy") -> float | None:
    """
    Trailing stop logic:
    - After 1:1 R:R is achieved, move stop to breakeven
    - Then trail by 0.5x ATR from highest point

    Returns new stop loss price, or None if no change.
    """
    multiplier = settings.TRAILING_STOP_ATR_MULTIPLIER
    risk = abs(entry_price - current_stop)

    if side == "buy":
        unrealized = current_price - entry_price

        # If we've achieved 1:1 R:R, start trailing
        if unrealized >= risk:
            new_stop = current_price - (atr * multiplier)
            # Never move stop backwards
            if new_stop > current_stop:
                logger.debug(
                    f"Trailing stop updated: ${current_stop:.2f} -> ${new_stop:.2f}"
                )
                return round(new_stop, 2)
    else:
        unrealized = entry_price - current_price

        if unrealized >= risk:
            new_stop = current_price + (atr * multiplier)
            if new_stop < current_stop:
                logger.debug(
                    f"Trailing stop updated: ${current_stop:.2f} -> ${new_stop:.2f}"
                )
                return round(new_stop, 2)

    return None
