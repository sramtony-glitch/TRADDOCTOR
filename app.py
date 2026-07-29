from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as io_plotly
from plotly.subplots import make_subplots
import requests
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf

# 設定網頁標題與響應式滿版版面
st.set_page_config(page_title="台指期多空關卡分析系統", page_icon="📊", layout="wide")

# 注入深色主題 CSS
st.markdown(
    """
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    </head>
    <style>
    .stNumberInput label, .stDateInput label { font-size: 18px !important; font-weight: bold !important; }
    .stNumberInput input, .stDateInput input { font-size: 18px !important; font-weight: bold !important; }
    h1 { font-size: 28px !important; }
    .js-plotly-plot .plotly .main-svg { touch-action: auto !important; }
    </style>
""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------
# 🔐 1. 欄位一：每月密碼驗證 (30天記憶)
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
if not st.session_state["authenticated"] and query_params.get("auth_token") == CORRECT_PASSWORD:
    st.session_state["authenticated"] = True

def check_password():
    if st.session_state["authenticated"]:
        return True

    st.title("🔒 系統授權鎖定")
    st.caption("請輸入每月授權密碼以存取台指期關卡圖（輸入一次維持 30 天登入）。")

    user_pwd = st.text_input("【欄位一】請輸入授權密碼：", type="password")

    if st.button("解鎖並進入系統", type="primary"):
        if user_pwd == CORRECT_PASSWORD:
            st.session_state["authenticated"] = True
            st.query_params["auth_token"] = CORRECT_PASSWORD
            st.success("驗證成功！已自動記住認證狀態。")
            st.rerun()
        else:
            st.error("❌ 密碼錯誤，請向管理者索取當月密碼！")

    components.html(
        f"""
        <script>
            const savedToken = localStorage.getItem('stock_app_auth_token');
            const tokenTime = localStorage.getItem('stock_app_auth_time');
            const now = new Date().getTime();
            
            if (savedToken === '{CORRECT_PASSWORD}' && tokenTime && (now - parseInt(tokenTime) < 2592000000)) {{
                const url = new URL(window.location.href);
                if (!url.searchParams.has('auth_token')) {{
                    url.searchParams.set('auth_token', '{CORRECT_PASSWORD}');
                    window.location.href = url.href;
                }}
            }}
        </script>
    """,
        height=0,
    )

    return False

if st.session_state["authenticated"]:
    components.html(
        f"""
        <script>
            localStorage.setItem('stock_app_auth_token', '{CORRECT_PASSWORD}');
            localStorage.setItem('stock_app_auth_time', new Date().getTime().toString());
        </script>
    """,
        height=0,
    )

# ----------------------------------------------------
# 🚀 2. 主程式
# ----------------------------------------------------
if check_password():
    st.title("📊 台灣台指期 K線與成交量關卡圖")

    col1, col2, col3 = st.columns([2, 1.5, 1.5])

    default_start = datetime.now().date() - timedelta(days=7)
    default_end = datetime.now().date()

    with col1:
        # 輸入或抓取基準點 N
        n_input = st.number_input(
            "【關卡基準點 N】 (預設前次收盤價)", value=22000, step=50
        )

    with col2:
        start_date = st.date_input("【起始日期】", value=default_start)

    with col3:
        end_date = st.date_input("【結束日期】", value=default_end)

    # ----------------------------------------------------
    # 📈 計算關鍵支撐壓力位
    # ----------------------------------------------------
    N = float(n_input)
    P1 = N + 300  # 壓力一 (綠)
    P2 = N + 600  # 壓力二 (綠)
    S1 = N - 300  # 支撐一 (黃)
    S2 = N - 600  # 支撐二 (黃)

    # ----------------------------------------------------
    # 📊 抓取台指期數據 (yfinance 代號: WTX=F 或 ^TWII 備用)
    # ----------------------------------------------------
    try:
        with st.spinner("正在讀取台指期行情數據..."):
            ticker = "WTX=F"  # 台灣台指期近月
            df = yf.download(ticker, start=start_date, end=end_date + timedelta(days=1), interval="15m")
            if df.empty:
                ticker = "^TWII"  # 加權指數備用
                df = yf.download(ticker, start=start_date, end=end_date + timedelta(days=1), interval="15m")

    except Exception as e:
        st.error(f"資料讀取失敗：{e}")
        st.stop()

    if df.empty:
        st.warning("❌ 暫無該時間範圍內的台指期 K 線數據！")
    else:
        if isinstance(df.columns, pd.MultiIndex):
            open_s = df["Open"][ticker]
            high_s = df["High"][ticker]
            low_s = df["Low"][ticker]
            close_s = df["Close"][ticker]
            vol_s = df["Volume"][ticker]
        else:
            open_s = df["Open"]
            high_s = df["High"]
            low_s = df["Low"]
            close_s = df["Close"]
            vol_s = df["Volume"]

        plot_df = pd.DataFrame({
            "Open": open_s,
            "High": high_s,
            "Low": low_s,
            "Close": close_s,
            "Volume": vol_s
        }).dropna()

        # 設定顏色規則 (紅漲綠跌 / 藍綠成交量)
        plot_df["Color"] = ["#FF3333" if c >= o else "#00B359" for o, c in zip(plot_df["Open"], plot_df["Close"])]
        plot_df["VolColor"] = ["#FF3333" if c >= o else "#00E5FF" for o, c in zip(plot_df["Open"], plot_df["Close"])]

        # 建立上下兩個子圖（上方 K 線 70%，下方成交量 30%）
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.75, 0.25]
        )

        # 🟢🔴 1. 繪製 K 線圖 (Row 1)
        fig.add_trace(
            io_plotly.Candlestick(
                x=plot_df.index,
                open=plot_df["Open"],
                high=plot_df["High"],
                low=plot_df["Low"],
                close=plot_df["Close"],
                name="台指期 K線",
                increasing_line_color="#FF3333",
                increasing_fillcolor="#FF3333",
                decreasing_line_color="#00B359",
                decreasing_fillcolor="#00B359"
            ),
            row=1, col=1
        )

        # 📊 2. 繪製成交量圖 (Row 2)
        fig.add_trace(
            io_plotly.Bar(
                x=plot_df.index,
                y=plot_df["Volume"],
                name="成交量",
                marker_color=plot_df["VolColor"],
                showlegend=False
            ),
            row=2, col=1
        )

        # ----------------------------------------------------
        # 🎯 繪製多空線與關卡平行線 (黃色/綠色虛線 + 右側標籤)
        # ----------------------------------------------------
        lines_config = [
            (P2, f"壓力二 {P2:,.0f}", "#00E5FF", "dash"),   # 亮青綠色虛線
            (P1, f"壓力一 {P1:,.0f}", "#00E5FF", "dash"),   # 亮青綠色虛線
            (N,  f"多空線 {N:,.0f}",  "#FFFF00", "dash"),   # 黃色虛線
            (S1, f"支撐一 {S1:,.0f}", "#FFFF00", "dash"),   # 黃色虛線
            (S2, f"支撐二 {S2:,.0f}", "#FFFF00", "dash"),   # 黃色虛線
        ]

        for val, label_text, color, dash_style in lines_config:
            # 畫平行虛線
            fig.add_hline(
                y=val,
                line_color=color,
                line_width=2,
                line_dash=dash_style,
                row=1, col=1
            )
            # 在右上角貼上文字標籤
            fig.add_annotation(
                x=plot_df.index[-1],
                y=val,
                text=f"<b>{label_text}</b>",
                font=dict(color=color, size=16),
                showarrow=False,
                xanchor="left",
                yanchor="middle",
                row=1, col=1
            )

        # 黑色極簡專業版面設置 (像 MultiCharts)
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0A0A0A",
            plot_bgcolor="#0A0A0A",
            margin=dict(l=10, r=90, t=50, b=20),
            hovermode="x unified",
            showlegend=False,
            xaxis2=dict(
                type="date",
                rangebreaks=[dict(bounds=["sat", "mon"])],
                fixedrange=True
            ),
            xaxis=dict(fixedrange=True),
            yaxis=dict(fixedrange=True, side="right"),
            yaxis2=dict(fixedrange=True, side="right"),
        )

        fig.update_yaxes(showgrid=True, gridcolor="#222222", row=1, col=1)
        fig.update_yaxes(showgrid=True, gridcolor="#222222", row=2, col=1)

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"scrollZoom": False, "displayModeBar": False}
        )
