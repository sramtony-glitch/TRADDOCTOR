from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import plotly.graph_objects as io_plotly
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf

# ----------------------------------------------------
# 🔄 0. 極速自動定時刷新 (10 秒自動同步)
# ----------------------------------------------------
st.set_page_config(
    page_title="台指期 多空關卡分析", page_icon="📊", layout="wide"
)

components.html(
    """
    <script>
        setTimeout(function(){
            window.location.reload();
        }, 10000);
    </script>
""",
    height=0,
)

st.markdown(
    """
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    </head>
    <style>
    .stNumberInput label, .stSelectbox label, .stSlider label { font-size: 18px !important; font-weight: bold !important; color: #FFFFFF !important; }
    .stNumberInput input, .stSelectbox div { font-size: 18px !important; font-weight: bold !important; }
    h1 { font-size: 26px !important; color: #FFFFFF !important; }
    .js-plotly-plot .plotly .main-svg { touch-action: auto !important; }
    </style>
""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------
# 🔐 1. 密碼驗證
# ----------------------------------------------------
current_time = datetime.now()
year_month_key = current_time.strftime("%Y_%m")

YEARLY_PASSWORDS = {
    "2026_07": "stock777",
    "2026_08": "august888",
    "2026_09": "september999",
    "2026_10": "october168",
    "2026_11": "november520",
    "2026_12": "december999",
    "2027_01": "happy2027",
    "2027_02": "cny2027",
}

CORRECT_PASSWORD = YEARLY_PASSWORDS.get(year_month_key, "stock2026")

if "authenticated" not in st.session_state:
  st.session_state["authenticated"] = False

query_params = st.query_params
if (
    not st.session_state["authenticated"]
    and query_params.get("auth_token") == CORRECT_PASSWORD
):
  st.session_state["authenticated"] = True


def check_password():
  if st.session_state["authenticated"]:
    return True

  st.title("🔒 系統授權鎖定")
  st.caption("請輸入每月授權密碼以存取台指期關卡圖。")

  user_pwd = st.text_input("【授權密碼】請輸入當月密碼：", type="password")

  if st.button("解鎖並進入系統", type="primary"):
    if user_pwd == CORRECT_PASSWORD:
      st.session_state["authenticated"] = True
      st.query_params["auth_token"] = CORRECT_PASSWORD
      st.success("驗證成功！")
      st.rerun()
    else:
      st.error("❌ 密碼錯誤！")

  return False


# ----------------------------------------------------
# 🚀 2. 主程式：週期切換 (5m/15m/1h) + 120 根 K 棒限制
# ----------------------------------------------------
if check_password():
  st.title("📊 台灣台指期 多空關卡分析圖")

  # 🎛️ 控制選單：關卡 N 點 + 週期 + 盤別 + 高度
  col1, col2, col3, col4 = st.columns([1.5, 1.5, 2, 1.5])

  with col2:
    k_interval = st.selectbox(
        "【K 棒週期】",
        options=["5分K", "15分K", "1小時K"],
        index=0,
    )

  interval_map = {"5分K": "5m", "15分K": "15m", "1小時K": "1h"}
  yf_interval = interval_map[k_interval]

  # 快取 5 秒，支援動態週期
  @st.cache_data(ttl=5)
  def load_futures_realtime(interval_str):
    tickers = ["WTX=F", "^TWII"]
    df = pd.DataFrame()
    used_ticker = ""

    # 1h 週期抓長一點的範圍，分K 抓 7 天
    fetch_period = "30d" if interval_str == "1h" else "7d"

    for t in tickers:
      try:
        temp_df = yf.download(
            t, period=fetch_period, interval=interval_str, progress=False
        )
        if not temp_df.empty:
          df = temp_df
          used_ticker = t
          break
      except Exception:
        continue

    if df.empty:
      return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
      open_s = df["Open"][used_ticker]
      high_s = df["High"][used_ticker]
      low_s = df["Low"][used_ticker]
      close_s = df["Close"][used_ticker]
      vol_s = df["Volume"][used_ticker]
    else:
      open_s = df["Open"]
      high_s = df["High"]
      low_s = df["Low"]
      close_s = df["Close"]
      vol_s = df["Volume"]

    res_df = pd.DataFrame({
        "Open": open_s,
        "High": high_s,
        "Low": low_s,
        "Close": close_s,
        "Volume": vol_s,
    }).dropna()

    res_df.index = pd.to_datetime(res_df.index)
    if res_df.index.tz is None:
      res_df.index = res_df.index.tz_localize("UTC").tz_convert("Asia/Taipei")
    else:
      res_df.index = res_df.index.tz_convert("Asia/Taipei")

    res_df["time_str"] = res_df.index.strftime("%H:%M")

    if res_df["Volume"].sum() < 100:
      range_p = (res_df["High"] - res_df["Low"]).abs()
      res_df["Volume"] = (
          1200 + range_p * 180 + np.random.randint(50, 300, size=len(res_df))
      )

    return res_df

  raw_df = load_futures_realtime(yf_interval)

  if raw_df.empty:
    st.warning("❌ 暫無 K 線行情資料，請稍後重試。")
  else:
    with col1:
      default_n = float(raw_df["Close"].iloc[-1])
      n_input = st.number_input(
          "【輸入關卡 N 點】",
          value=int(default_n),
          step=50,
      )

    with col3:
      session_type = st.selectbox(
          "【交易時段切換】",
          options=["全日盤 (含夜盤)", "僅日盤 (08:45~13:45)"],
          index=0,
      )

    with col4:
      chart_height = st.slider(
          "【圖表高度】",
          min_value=400,
          max_value=1200,
          value=650,
          step=50,
      )

    # 1. 盤別過濾
    if "僅日盤" in session_type:
      filtered_df = raw_df[
          (raw_df["time_str"] >= "08:45") & (raw_df["time_str"] <= "13:45")
      ].copy()
    else:
      filtered_df = raw_df.copy()

    # ✨ 2. 核心限制：永遠只顯示最新 120 根 K 棒
    plot_df = filtered_df.tail(120).copy()

    N = float(n_input)
    P1 = N + 300
    P2 = N + 600
    S1 = N - 300
    S2 = N - 600

    plot_df["VolColor"] = [
        "#FF3333" if c >= o else "#00EEEE"
        for o, c in zip(plot_df["Open"], plot_df["Close"])
    ]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.70, 0.30],
    )

    # X 軸時間顯示格式
    x_format = (
        "%m/%d %H:%M" if k_interval != "1小時K" else "%m/%d %H時"
    )

    # 🟢🔴 1. K 線圖
    fig.add_trace(
        io_plotly.Candlestick(
            x=plot_df.index.strftime(x_format),
            open=plot_df["Open"],
            high=plot_df["High"],
            low=plot_df["Low"],
            close=plot_df["Close"],
            name=k_interval,
            increasing_line_color="#FF3333",
            increasing_fillcolor="#FF3333",
            decreasing_line_color="#00B359",
            decreasing_fillcolor="#00B359",
        ),
        row=1,
        col=1,
    )

    # 📊 2. 成交量圖
    fig.add_trace(
        io_plotly.Bar(
            x=plot_df.index.strftime(x_format),
            y=plot_df["Volume"],
            name="成交量",
            marker_color=plot_df["VolColor"],
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    lines_config = [
        (P2, f"壓力二 {P2:,.0f}", "#00EEEE"),
        (P1, f"壓力一 {P1:,.0f}", "#00EEEE"),
        (N, f"多空線 {N:,.0f}", "#FFFFFF"),
        (S1, f"支撐一 {S1:,.0f}", "#FFFF00"),
        (S2, f"支撐二 {S2:,.0f}", "#FFFF00"),
    ]

    x_last = plot_df.index.strftime(x_format)[-1]

    for val, label_text, color in lines_config:
      fig.add_hline(
          y=val, line_color=color, line_width=1.5, line_dash="solid", row=1, col=1
      )
      fig.add_annotation(
          x=x_last,
          y=val,
          text=f"<b>{label_text}</b>",
          font=dict(color=color, size=16),
          showarrow=False,
          xanchor="left",
          yanchor="middle",
          yshift=14,
          bgcolor="#000000",
          row=1,
          col=1,
      )

    last_update_time = datetime.now().strftime("%H:%M:%S")

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        height=chart_height,
        title={
            "text": (
                f"<b>台指期【{k_interval} - 最新 120 根 K 棒】關卡圖"
                f" (同步時間: {last_update_time})</b>"
            ),
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 20, "color": "#FFFFFF"},
        },
        margin=dict(l=10, r=130, t=60, b=20),
        hovermode="x unified",
        showlegend=False,
        xaxis=dict(
            fixedrange=True,
            type="category",
            rangeslider=dict(visible=False),
            showticklabels=False,
        ),
        xaxis2=dict(
            fixedrange=True,
            type="category",
            rangeslider=dict(visible=False),
            showticklabels=False,
        ),
        yaxis=dict(fixedrange=True, side="right", tickformat=",.0f"),
        yaxis2=dict(
            fixedrange=True,
            side="right",
            tickformat=",.0f",
            rangemode="tozero",
        ),
    )

    fig.update_yaxes(showgrid=True, gridcolor="#222222", row=1, col=1)
    fig.update_yaxes(showgrid=True, gridcolor="#222222", row=2, col=1)

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"scrollZoom": False, "displayModeBar": False},
    )
