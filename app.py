import os
from datetime import datetime
import pandas as pd
import plotly.graph_objects as io_plotly
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="台灣台指期實時關卡圖", page_icon="📊", layout="wide"
)

# ----------------------------------------------------
# 1. 讀取 XQ 本地資料
# ----------------------------------------------------
def get_xq_data():
    csv_path = r"C:\XQ_Data\TX_5M.csv"
    if not os.path.exists(csv_path):
        return pd.DataFrame()

    try:
        df = pd.read_csv(csv_path, on_bad_lines="skip", engine="python")
        if df.empty or len(df.columns) < 7:
            return pd.DataFrame()

        df.columns = [str(c).strip() for c in df.columns]
        df = df[df["Date"].astype(str).str.lower() != "date"].copy()

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        time_series = df["Date"].astype(str) + " " + df["Time"].astype(str)
        df["Time"] = pd.to_datetime(time_series, errors="coerce")
        df = df.dropna(subset=["Time", "Close"]).set_index("Time")
        return df
    except Exception:
        return pd.DataFrame()

# ----------------------------------------------------
# 2. 備用免費網路數據源 (Yahoo Finance)
# ----------------------------------------------------
def get_yahoo_data():
    try:
        ticker = yf.Ticker("^TWII")
        df = ticker.history(period="5d", interval="5m")
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df = df.rename(
            columns={
                "Datetime": "Time",
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close",
                "Volume": "Volume",
            }
        )
        df["Time"] = pd.to_datetime(df["Time"])
        df = df.set_index("Time")
        return df
    except Exception:
        return pd.DataFrame()

# ----------------------------------------------------
# 3. K 線週期重組 (5M / 15M / 60M)
# ----------------------------------------------------
def resample_kline(df, tf_str):
    if df.empty or tf_str == "5M":
        return df.tail(120)

    rule = "15min" if tf_str == "15M" else "60min"
    resampled = (
        df.resample(rule)
        .agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        })
        .dropna()
    )
    return resampled.tail(120)

# ----------------------------------------------------
# 主程式 UI
# ----------------------------------------------------
st.title("📊 台灣台指期 實時關卡分析圖")

# 控制區域：週期與基準點
col_tf, col_n, col_src = st.columns([2, 2, 3])

with col_tf:
    tf = st.radio("【K線週期】", ["5M", "15M", "60M"], horizontal=True)

# 優先採用 XQ 本地資料
data_source = "XQ 本地同步"
plot_df = get_xq_data()

if plot_df.empty:
    data_source = "免費網絡源 (Yahoo Finance)"
    plot_df = get_yahoo_data()

if plot_df.empty:
    st.warning("⏳ 尚未取得行情資料！請確認 XQ 腳本正常運作或網路連線。")
else:
    # 進行週期重組
    plot_df = resample_kline(plot_df, tf)

    with col_n:
        default_n = float(plot_df["Close"].iloc[-1])
        n_input = st.number_input(
            "【輸入關卡基準點 N】", value=int(default_n), step=50
        )

    with col_src:
        st.info(f"📡 資料來源: **{data_source}** ({tf} 週期)")

    N = float(n_input)
    P1, P2 = N + 300, N + 600
    S1, S2 = N - 300, N - 600

    plot_df["VolColor"] = [
        "#FF3333" if c >= o else "#00EEEE"
        for o, c in zip(plot_df["Open"], plot_df["Close"])
    ]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.72, 0.28],
    )

    x_time_str = plot_df.index.strftime("%m/%d %H:%M")

    # K 線
    fig.add_trace(
        io_plotly.Candlestick(
            x=x_time_str,
            open=plot_df["Open"],
            high=plot_df["High"],
            low=plot_df["Low"],
            close=plot_df["Close"],
            name="K線",
            increasing_line_color="#FF3333",
            increasing_fillcolor="#FF3333",
            decreasing_line_color="#00B359",
            decreasing_fillcolor="#00B359",
        ),
        row=1,
        col=1,
    )

    # 成交量
    fig.add_trace(
        io_plotly.Bar(
            x=x_time_str,
            y=plot_df["Volume"],
            marker_color=plot_df["VolColor"],
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    # 5條核心關卡線
    lines = [
        (P2, f"壓力二 {P2:,.0f}", "#00EEEE"),
        (P1, f"壓力一 {P1:,.0f}", "#00EEEE"),
        (N, f"多空線 {N:,.0f}", "#FFFFFF"),
        (S1, f"支撐一 {S1:,.0f}", "#FFFF00"),
        (S2, f"支撐二 {S2:,.0f}", "#FFFF00"),
    ]

    x_last = x_time_str[-1]
    for val, label, color in lines:
        fig.add_hline(
            y=val, line_color=color, line_width=1.5, line_dash="solid", row=1, col=1
        )
        fig.add_annotation(
            x=x_last,
            y=val,
            text=f"<b>{label}</b>",
            font=dict(color=color, size=15),
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            yshift=12,
            bgcolor="#000000",
            row=1,
            col=1,
        )

    now_str = datetime.now().strftime("%H:%M:%S")

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        height=680,
        title={
            "text": f"<b>[{data_source}] 台指期 {tf} 關卡圖 (更新時間: {now_str})</b>",
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 20, "color": "#FFFFFF"},
        },
        margin=dict(l=10, r=130, t=60, b=20),
        hovermode="x unified",
        showlegend=False,
        # 關閉預設橫向與縱向網格背景線 (showgrid=False)
        xaxis=dict(
            fixedrange=True,
            type="category",
            rangeslider=dict(visible=False),
            showgrid=False,
            showticklabels=False,
        ),
        xaxis2=dict(
            fixedrange=True,
            type="category",
            rangeslider=dict(visible=False),
            showgrid=False,
            showticklabels=False,
        ),
        yaxis=dict(
            fixedrange=True, side="right", tickformat=",.0f", showgrid=False
        ),
        yaxis2=dict(
            fixedrange=True,
            side="right",
            tickformat=",.0f",
            rangemode="tozero",
            showgrid=False,
        ),
    )

    st.plotly_chart(fig, use_container_width=True)
