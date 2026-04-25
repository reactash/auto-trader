import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(
    page_title="Auto-Trader Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auto-refresh every 30 seconds
st.markdown(
    '<meta http-equiv="refresh" content="30">',
    unsafe_allow_html=True,
)


@st.cache_resource
def get_trader():
    from engine.trader import AlpacaTrader
    return AlpacaTrader()


@st.cache_resource
def init_database():
    from engine.models import init_db
    init_db()


def load_account():
    try:
        trader = get_trader()
        return trader.get_account()
    except Exception as e:
        st.error(f"Failed to connect to Alpaca: {e}")
        return None


def load_positions():
    try:
        trader = get_trader()
        return trader.get_positions()
    except Exception:
        return []


def load_trade_history():
    from engine.models import get_trade_history
    return get_trade_history(limit=100)


def load_todays_trades():
    from engine.models import get_todays_trades
    return get_todays_trades()


def load_daily_pnl():
    from engine.models import get_daily_pnl_history
    return get_daily_pnl_history(limit=30)


def load_news_scores():
    from engine.models import get_todays_news_scores
    return get_todays_news_scores()


# Initialize
init_database()

# Header
st.title("Auto-Trader Dashboard")
st.caption("US Market Paper Trading | ORB + VWAP Strategy")

# Account metrics
account = load_account()
if account:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Portfolio Value", f"${account['portfolio_value']:,.2f}")
    with col2:
        st.metric(
            "Daily P&L",
            f"${account['daily_pnl']:,.2f}",
            delta=f"{account['daily_pnl']:+,.2f}",
        )
    with col3:
        st.metric("Cash", f"${account['cash']:,.2f}")
    with col4:
        st.metric("Buying Power", f"${account['buying_power']:,.2f}")

st.divider()

# Two-column layout
left_col, right_col = st.columns([3, 2])

with left_col:
    # Open Positions
    st.subheader("Open Positions")
    positions = load_positions()
    if positions:
        pos_df = pd.DataFrame(positions)
        pos_df["unrealized_pnl"] = pos_df["unrealized_pnl"].apply(lambda x: f"${x:+,.2f}")
        pos_df["unrealized_pnl_pct"] = pos_df["unrealized_pnl_pct"].apply(lambda x: f"{x:+.2f}%")
        pos_df["entry_price"] = pos_df["entry_price"].apply(lambda x: f"${x:,.2f}")
        pos_df["current_price"] = pos_df["current_price"].apply(lambda x: f"${x:,.2f}")
        pos_df["market_value"] = pos_df["market_value"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(
            pos_df[["symbol", "side", "qty", "entry_price", "current_price", "unrealized_pnl", "unrealized_pnl_pct"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No open positions")

    # Today's Trades
    st.subheader("Today's Trades")
    todays_trades = load_todays_trades()
    if todays_trades:
        trades_df = pd.DataFrame(todays_trades)
        display_cols = ["symbol", "side", "qty", "entry_price", "exit_price", "pnl", "exit_reason", "status"]
        available_cols = [c for c in display_cols if c in trades_df.columns]
        for col in ["entry_price", "exit_price", "pnl"]:
            if col in trades_df.columns:
                trades_df[col] = trades_df[col].apply(
                    lambda x: f"${x:,.2f}" if x is not None else "-"
                )
        st.dataframe(trades_df[available_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No trades today")

    # Cumulative P&L Chart
    st.subheader("Cumulative P&L")
    daily_pnl = load_daily_pnl()
    if daily_pnl:
        pnl_df = pd.DataFrame(daily_pnl)
        pnl_df = pnl_df.sort_values("date")
        pnl_df["cumulative_pnl"] = pnl_df["total_pnl"].cumsum()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pnl_df["date"],
            y=pnl_df["cumulative_pnl"],
            mode="lines+markers",
            name="Cumulative P&L",
            line=dict(color="#00cc96", width=2),
            fill="tozeroy",
        ))
        fig.update_layout(
            yaxis_title="P&L ($)",
            xaxis_title="Date",
            height=350,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Daily P&L bar chart
        colors = ["#00cc96" if x >= 0 else "#ef553b" for x in pnl_df["total_pnl"]]
        fig2 = go.Figure(go.Bar(
            x=pnl_df["date"],
            y=pnl_df["total_pnl"],
            marker_color=colors,
        ))
        fig2.update_layout(
            yaxis_title="Daily P&L ($)",
            height=250,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No P&L data yet. Run the bot during market hours.")

with right_col:
    # Performance Stats
    st.subheader("Performance Stats")
    if daily_pnl:
        pnl_df = pd.DataFrame(daily_pnl)
        total_trades = pnl_df["num_trades"].sum()
        total_wins = pnl_df["wins"].sum()
        total_losses = pnl_df["losses"].sum()
        total_pnl_val = pnl_df["total_pnl"].sum()
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

        stat_col1, stat_col2 = st.columns(2)
        with stat_col1:
            st.metric("Total Trades", total_trades)
            st.metric("Wins", int(total_wins))
            st.metric("Win Rate", f"{win_rate:.1f}%")
        with stat_col2:
            st.metric("Total P&L", f"${total_pnl_val:+,.2f}")
            st.metric("Losses", int(total_losses))
            st.metric("Trading Days", len(pnl_df))
    else:
        st.info("No performance data yet")

    # News Sentiment Feed
    st.subheader("Today's News Sentiment")
    news = load_news_scores()
    if news:
        for article in news[:15]:
            score = article["sentiment_score"]
            if score > 0.05:
                emoji = "+"
                color = "green"
            elif score < -0.05:
                emoji = "-"
                color = "red"
            else:
                emoji = "~"
                color = "gray"

            st.markdown(
                f"**[{emoji}{score:.2f}]** {article['headline'][:80]}  \n"
                f"<small style='color:{color}'>{article.get('source', '')} | {article.get('symbol', '')}</small>",
                unsafe_allow_html=True,
            )
    else:
        st.info("No news data yet. Run pre-market scan first.")

    # Trade History
    st.subheader("Recent Trade History")
    history = load_trade_history()
    if history:
        hist_df = pd.DataFrame(history)
        display_cols = ["symbol", "side", "qty", "entry_price", "pnl", "exit_reason", "status"]
        available = [c for c in display_cols if c in hist_df.columns]
        for col in ["entry_price", "pnl"]:
            if col in hist_df.columns:
                hist_df[col] = hist_df[col].apply(
                    lambda x: f"${x:,.2f}" if x is not None else "-"
                )
        st.dataframe(hist_df[available].head(20), use_container_width=True, hide_index=True)
    else:
        st.info("No trade history yet")

# Sidebar
with st.sidebar:
    st.header("Settings")
    st.markdown(f"""
    - **Strategy**: ORB + VWAP
    - **Max Risk/Trade**: {2}%
    - **Max Daily Loss**: {3}%
    - **Max Positions**: {5}
    - **Risk:Reward**: 1:{1.5}
    - **Scan Interval**: {5} min
    """)

    st.divider()
    st.subheader("Quick Actions")

    if st.button("Run Pre-Market Scan Now", use_container_width=True):
        with st.spinner("Scanning..."):
            from scheduler.jobs import pre_market_job
            pre_market_job()
        st.success("Pre-market scan complete!")
        st.rerun()

    if st.button("Close All Positions", type="primary", use_container_width=True):
        trader = get_trader()
        closed = trader.close_all_positions("manual_close")
        st.success(f"Closed {closed} positions")
        st.rerun()

    st.divider()
    st.caption("Auto-refreshes every 30 seconds")
    if st.button("Refresh Now", use_container_width=True):
        st.rerun()
