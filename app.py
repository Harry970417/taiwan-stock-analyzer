# app.py（中文版）
# 台灣股票智能分析平台 — 市場總覽儀表板

import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from utils.data_fetcher  import get_stock_data
from utils.indicators    import add_all_indicators
from utils.charts        import plot_candlestick, plot_rsi, plot_macd, plot_kd, add_signals_to_chart
from utils.backtest      import run_backtest, plot_portfolio_value
from utils.exporter      import export_to_csv, export_trades_to_csv, get_export_filename

from strategies.ma_strategy   import ma_crossover_strategy, get_strategy_name as ma_name, get_strategy_description as ma_desc
from strategies.rsi_strategy  import rsi_strategy, rsi_reversal_strategy, get_strategy_name as rsi_name, get_strategy_description as rsi_desc
from strategies.macd_strategy import macd_crossover_strategy, get_strategy_name as macd_name, get_strategy_description as macd_desc

from modules.ui_components   import (inject_css, page_header, disclaimer, kpi_card,
                                      section_header, sidebar_logo, sidebar_section)
from modules.market_dashboard import get_market_overview
from modules.explainability   import generate_dashboard_narrative

st.set_page_config(
    page_title="台灣股票智能分析平台",
    page_icon="📊", layout="wide",
    initial_sidebar_state="expanded"
)
inject_css()

# ══════════════════════════════════════════
# 側邊欄
# ══════════════════════════════════════════
with st.sidebar:
    sidebar_logo()

    sidebar_section("策略回測設定")
    ticker_input = st.text_input("股票代號", value="2330", placeholder="例：2330、2317、0050")

    period_options = {"近6個月":"6mo","近1年":"1y","近2年":"2y","近5年":"5y"}
    selected_period_label = st.selectbox("資料期間", list(period_options.keys()), index=2)
    selected_period = period_options[selected_period_label]

    force_refresh = st.checkbox("強制重新下載資料", value=False)

    sidebar_section("圖表顯示")
    show_ma     = st.checkbox("顯示均線（MA5/20/60）", value=True)
    show_volume = st.checkbox("顯示成交量", value=True)
    show_rsi    = st.checkbox("顯示 RSI", value=True)
    show_macd   = st.checkbox("顯示 MACD", value=True)
    show_kd     = st.checkbox("顯示 KD", value=False)

    sidebar_section("策略選擇")
    strategy_options = {
        "MA 均線交叉策略（MA5×MA20）":    "ma",
        "RSI 回拉確認策略（推薦）":         "rsi_reversal",
        "RSI 超買超賣策略（簡單）":          "rsi",
        "MACD 訊號線交叉策略":             "macd",
    }
    selected_strategy_label = st.selectbox("交易策略", list(strategy_options.keys()))
    selected_strategy = strategy_options[selected_strategy_label]

    initial_capital = st.number_input("初始資金（元）", min_value=10_000,
                                       max_value=10_000_000, value=100_000,
                                       step=10_000, format="%d")

    sidebar_section("風險管理")
    stop_loss_pct   = st.slider("停損比例（%）",   0, 20, 0, 1)
    stop_profit_pct = st.slider("停利比例（%）",   0, 50, 0, 1)
    sl_str = f"停損 {stop_loss_pct}%" if stop_loss_pct else "停損：未啟用"
    sp_str = f"停利 {stop_profit_pct}%" if stop_profit_pct else "停利：未啟用"
    st.caption(f"{sl_str} · {sp_str} · 整張交易（1000股）")

    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
    run_button = st.button("▶  開始回測分析", type="primary", use_container_width=True)

# ══════════════════════════════════════════
# 首頁：市場總覽儀表板
# ══════════════════════════════════════════
if not run_button:
    st.markdown("""
    <div style="padding:0.5rem 0 1.25rem;border-bottom:1px solid #E2E8F0;margin-bottom:1.5rem;">
        <div style="font-size:0.62rem;font-weight:700;color:#1E40AF;text-transform:uppercase;
                    letter-spacing:0.14em;margin-bottom:0.5rem;">
            Taiwan Equity Intelligence Platform
        </div>
        <div style="font-size:2.2rem;font-weight:900;color:#0F172A;
                    letter-spacing:-0.03em;line-height:1.1;margin-bottom:0.5rem;">
            台灣股票量化研究平台
        </div>
        <div style="font-size:0.875rem;color:#475569;line-height:1.65;max-width:680px;
                    margin-bottom:0.6rem;">
            整合市場動能、法人籌碼、基本面因子、多因子回測與投資組合風險管理，
            建立機構級別的資料驅動投資分析流程。
        </div>
        <div style="display:flex;gap:0.5rem;flex-wrap:wrap;">
            <span style="background:#DBEAFE;color:#1D4ED8;padding:0.15rem 0.6rem;
                         border-radius:999px;font-size:0.67rem;font-weight:700;">
                Yahoo Finance
            </span>
            <span style="background:#DBEAFE;color:#1D4ED8;padding:0.15rem 0.6rem;
                         border-radius:999px;font-size:0.67rem;font-weight:700;">
                TWSE 官方資料
            </span>
            <span style="background:#DBEAFE;color:#1D4ED8;padding:0.15rem 0.6rem;
                         border-radius:999px;font-size:0.67rem;font-weight:700;">
                FinMind API
            </span>
            <span style="background:#F0FDF4;color:#16A34A;padding:0.15rem 0.6rem;
                         border-radius:999px;font-size:0.67rem;font-weight:700;">
                T+1 無未來函數
            </span>
            <span style="background:#F0FDF4;color:#16A34A;padding:0.15rem 0.6rem;
                         border-radius:999px;font-size:0.67rem;font-weight:700;">
                Walk-Forward 驗證
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    disclaimer()
    st.markdown("")

    with st.spinner("載入今日市場資料中..."):
        mkt = get_market_overview()

    # ── 市場情緒 KPI ──
    section_header("今日市場情緒")

    score     = mkt["sentiment_score"]
    direction = mkt["direction"]
    dir_color = mkt["direction_color"]
    dir_zh    = {"Bullish":"偏多","Bearish":"偏空","Neutral":"中性"}.get(direction, direction)

    k1,k2,k3,k4,k5,k6 = st.columns(6)
    with k1:
        st.markdown(f"""
        <div class="kpi-card" style="border-left:4px solid {dir_color};">
            <div class="kpi-label">市場情緒分數</div>
            <div class="kpi-value" style="color:{dir_color};">{score}<span style="font-size:1rem;color:#64748B;">/100</span></div>
            <div class="kpi-sub">
                <span style="background:{dir_color}22;color:{dir_color};padding:0.15rem 0.5rem;
                             border-radius:999px;font-weight:700;font-size:0.75rem;">
                    {dir_zh} {direction}
                </span>
            </div>
        </div>""", unsafe_allow_html=True)

    adv = mkt["advance"]; dec = mkt["decline"]; unch = mkt["unchanged"]
    total = mkt["total"] or 1; avg = mkt["avg_change"]

    with k2: st.markdown(kpi_card("上漲家數", f"{adv:,}", f"佔 {adv/total*100:.0f}%", "up"), unsafe_allow_html=True)
    with k3: st.markdown(kpi_card("下跌家數", f"{dec:,}", f"佔 {dec/total*100:.0f}%", "down"), unsafe_allow_html=True)
    with k4: st.markdown(kpi_card("平盤家數", f"{unch:,}", "無明顯漲跌", "flat"), unsafe_allow_html=True)
    with k5:
        d = "up" if avg >= 0 else "down"
        st.markdown(kpi_card("市場均漲跌幅", f"{avg:+.2f}%", "全市場平均", d), unsafe_allow_html=True)
    with k6:
        ad = round(adv/dec, 2) if dec > 0 else "N/A"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">漲跌比（A/D Ratio）</div>
            <div class="kpi-value">{ad}x</div>
            <div class="kpi-sub">上漲 / 下跌家數比值</div>
        </div>""", unsafe_allow_html=True)

    if mkt.get("error"):
        st.warning(f"市場資料部分載入失敗：{mkt['error']}")

    st.markdown("")

    # ── 強勢股 ──
    section_header("今日強勢個股 — 漲幅前五名")
    opportunities = mkt.get("top_opportunities", [])
    if opportunities:
        op_cols = st.columns(min(len(opportunities), 5))
        for i, op in enumerate(opportunities[:5]):
            with op_cols[i]:
                chg   = op.get("change_pct", 0)
                color = "#16A34A" if chg >= 0 else "#DC2626"
                vol   = op.get("volume", 0)
                vol_str = f"{int(vol/1000):.0f}千" if vol >= 1000 else str(int(vol))
                st.markdown(f"""
                <div class="kpi-card" style="border-top:3px solid {color};text-align:center;">
                    <div style="font-weight:800;font-size:1.1rem;color:#0F172A;">{op['ticker']}</div>
                    <div style="font-size:0.75rem;color:#64748B;margin-bottom:0.4rem;">{op.get('name','')[:6]}</div>
                    <div style="font-weight:700;color:{color};font-size:1.2rem;">+{chg:.2f}%</div>
                    <div style="font-size:0.72rem;color:#94A3B8;margin-top:0.3rem;">量 {vol_str}</div>
                </div>""", unsafe_allow_html=True)
    else:
        st.info("目前無法取得強勢股資料（非交易時間或 API 暫時無回應）")

    st.markdown("")

    # ── 成交量排行 ──
    section_header("今日成交量前五名")
    vol_top = mkt.get("volume_top10", [])
    if vol_top:
        vol_df = pd.DataFrame(vol_top)
        vol_df["漲跌幅"] = vol_df["change_pct"].map(lambda x: f"{x:+.2f}%")
        vol_df["成交量"] = vol_df["volume"].map(lambda x: f"{int(x):,}")
        vol_df = vol_df.rename(columns={"ticker":"代號","name":"名稱","close":"收盤價"})
        st.dataframe(vol_df[["代號","名稱","收盤價","漲跌幅","成交量"]],
                     use_container_width=True, hide_index=True)

    st.markdown("")

    # ── 市場評論 ──
    section_header("今日市場情報")
    snap_col, info_col = st.columns([2, 1])
    with snap_col:
        dash_narrative = generate_dashboard_narrative(mkt)
        # 翻譯關鍵詞
        zh_narrative = dash_narrative \
            .replace("Bullish","偏多").replace("Bearish","偏空").replace("Neutral","中性") \
            .replace("advancing","上漲").replace("declining","下跌") \
            .replace("Market sentiment registers","市場情緒分數為") \
            .replace("advance/decline ratio","漲跌比") \
            .replace("Data sourced from TWSE.","資料來源：台灣證券交易所。") \
            .replace("Use the navigation panel to drill into individual opportunities.",
                     "請使用左側導覽列深入分析個股。")
        st.markdown(f"""
        <div class="research-box">
            <h4>今日市場評論</h4>
            <p>{zh_narrative}</p>
        </div>""", unsafe_allow_html=True)

    with info_col:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-label">可用策略</div>
            <div style="margin-top:0.5rem;font-size:0.82rem;color:#334155;line-height:1.8;">
                ▸ MA 均線交叉策略<br>
                ▸ RSI 回拉確認策略<br>
                ▸ RSI 超買超賣策略<br>
                ▸ MACD 訊號線交叉
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("")

    # ── 分析流程 ──
    section_header("投資分析決策流程")
    steps = [
        ("1","📊","市場總覽","檢視整體情緒與資金動向"),
        ("2","📡","動能篩選","找出強勢個股"),
        ("3","🏦","法人籌碼","確認外資投信方向"),
        ("4","📈","財報因子","評估基本面品質"),
        ("5","🔬","量化分析","技術面評分與風險"),
        ("6","🧪","策略驗證","回測策略有效性"),
        ("7","💼","投資組合","追蹤持倉損益"),
    ]
    cols = st.columns(7)
    for i, (num, icon, title, desc) in enumerate(steps):
        with cols[i]:
            is_first = (num == "1")
            bg = "#EFF6FF" if is_first else "#FFFFFF"
            border = "#1E40AF" if is_first else "#E2E8F0"
            st.markdown(f"""
            <div style="background:{bg};border:2px solid {border};border-radius:10px;
                        padding:0.8rem 0.5rem;text-align:center;height:155px;
                        display:flex;flex-direction:column;align-items:center;justify-content:space-between;">
                <div style="font-size:1.3rem;">{icon}</div>
                <div style="font-size:0.65rem;font-weight:800;color:#1E40AF;">{num}</div>
                <div style="font-size:0.78rem;font-weight:700;color:#0F172A;">{title}</div>
                <div style="font-size:0.67rem;color:#64748B;line-height:1.3;">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("")

    # ── 平台概覽 ──
    section_header("平台研究能力")
    pt1, pt2, pt3, pt4 = st.columns(4)
    pt1.markdown("""
    <div class="kpi-card" style="border-top:3px solid #DC2626;">
        <div class="kpi-label">研究痛點</div>
        <div style="font-size:0.81rem;color:#334155;margin-top:0.5rem;line-height:1.7;">
            散戶常面臨資訊分散、判斷主觀、缺乏嚴格回測驗證與風險量化不足的問題。
        </div>
    </div>""", unsafe_allow_html=True)
    pt2.markdown("""
    <div class="kpi-card" style="border-top:3px solid #1E40AF;">
        <div class="kpi-label">解決方案</div>
        <div style="font-size:0.81rem;color:#334155;margin-top:0.5rem;line-height:1.7;">
            整合市場動能、法人籌碼、基本面因子與多因子模型，建立資料驅動決策流程。
        </div>
    </div>""", unsafe_allow_html=True)
    pt3.markdown("""
    <div class="kpi-card" style="border-top:3px solid #16A34A;">
        <div class="kpi-label">研究方法</div>
        <div style="font-size:0.81rem;color:#334155;margin-top:0.5rem;line-height:1.7;">
            ▸ IC / Walk-Forward 驗證<br>
            ▸ VaR · CVaR · Beta/Alpha<br>
            ▸ Hurst 指數 · Jarque-Bera<br>
            ▸ T+1 無未來函數回測
        </div>
    </div>""", unsafe_allow_html=True)
    pt4.markdown("""
    <div class="kpi-card" style="border-top:3px solid #F59E0B;">
        <div class="kpi-label">平台規模</div>
        <div style="font-size:0.81rem;color:#334155;margin-top:0.5rem;line-height:1.7;">
            ▸ <b>14 個</b>分析模組<br>
            ▸ <b>4 種</b>策略回測<br>
            ▸ <b>3 個</b>外部資料來源<br>
            ▸ <b>5 個</b>量化研究模組
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center;font-size:0.7rem;color:#94A3B8;
                padding:1.75rem 0 0.5rem;border-top:1px solid #F1F5F9;margin-top:1rem;">
        台灣股票量化研究平台 ｜ 資料：Yahoo Finance · TWSE · FinMind ｜ 僅供學術研究與作品集展示
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════
# 策略回測
# ══════════════════════════════════════════
ticker = ticker_input.strip().upper()
with st.spinner(f"載入 {ticker} 資料中..."):
    try:
        df_raw = get_stock_data(ticker, period=selected_period, force_refresh=force_refresh)
    except ValueError as e:
        st.error(f"❌ {e}"); st.stop()

df     = add_all_indicators(df_raw)
latest = df.iloc[-1]; prev = df.iloc[-2]
change = latest["close"] - prev["close"]
change_pct = change / prev["close"] * 100

page_header(f"策略回測分析 — {ticker}", f"{selected_period_label} · {selected_strategy_label}", "📈")
disclaimer()
st.markdown("")

d = "up" if change_pct >= 0 else "down"
c1,c2,c3,c4,c5 = st.columns(5)
c1.markdown(kpi_card("最新收盤價", f"${latest['close']:.1f}", f"{change_pct:+.2f}%", d), unsafe_allow_html=True)
c2.markdown(kpi_card("開盤價", f"${latest['open']:.1f}"), unsafe_allow_html=True)
c3.markdown(kpi_card("最高價", f"${latest['high']:.1f}"), unsafe_allow_html=True)
c4.markdown(kpi_card("最低價", f"${latest['low']:.1f}"), unsafe_allow_html=True)
c5.markdown(kpi_card("成交量", f"{latest['volume']:,.0f}"), unsafe_allow_html=True)
st.caption(f"資料期間：{df['date'].min().date()} ～ {df['date'].max().date()}（共 {len(df)} 個交易日）｜ Yahoo Finance")
st.markdown("---")

# 策略訊號
if selected_strategy == "ma":
    df_signal = ma_crossover_strategy(df); sdname = ma_name(); sdesc = ma_desc()
elif selected_strategy == "rsi":
    df_signal = rsi_strategy(df); sdname = rsi_name("simple"); sdesc = rsi_desc("simple")
elif selected_strategy == "rsi_reversal":
    df_signal = rsi_reversal_strategy(df); sdname = rsi_name("reversal"); sdesc = rsi_desc("reversal")
elif selected_strategy == "macd":
    df_signal = macd_crossover_strategy(df); sdname = macd_name(); sdesc = macd_desc()

buy_dates  = df_signal[df_signal["signal"] == 1]["date"]
sell_dates = df_signal[df_signal["signal"] == -1]["date"]

section_header("K 線價格走勢圖")
fig_candle = plot_candlestick(df_signal, ticker, show_ma=show_ma, show_volume=show_volume)
fig_candle = add_signals_to_chart(fig_candle, df_signal, buy_dates, sell_dates)
st.plotly_chart(fig_candle, use_container_width=True)

ind_cols = st.columns(2)
if show_rsi and "RSI" in df.columns:
    with ind_cols[0]:
        section_header("RSI 相對強弱指標")
        st.plotly_chart(plot_rsi(df_signal), use_container_width=True)
if show_macd and "DIF" in df.columns:
    with ind_cols[1]:
        section_header("MACD 指標")
        st.plotly_chart(plot_macd(df_signal), use_container_width=True)
if show_kd and "K" in df.columns:
    section_header("KD 隨機指標")
    st.plotly_chart(plot_kd(df_signal), use_container_width=True)

st.markdown("---")
section_header(f"回測結果 — {sdname}")

with st.expander("策略說明", expanded=False):
    st.markdown(f'<div class="research-box">{sdesc}</div>', unsafe_allow_html=True)

sl_note = f"停損 {stop_loss_pct}%" if stop_loss_pct else "停損：未啟用"
sp_note = f"停利 {stop_profit_pct}%" if stop_profit_pct else "停利：未啟用"
st.caption(f"⚙ {sl_note}　|　{sp_note}　|　整張交易（1000股）　|　今日訊號 → 隔日開盤成交（避免未來函數）")

bt = run_backtest(df_signal, initial_capital=initial_capital,
                  stop_loss_pct=stop_loss_pct/100, stop_profit_pct=stop_profit_pct/100)

r1,r2,r3,r4,r5,r6 = st.columns(6)
d2 = "up" if bt["total_return"] >= 0 else "down"
r1.markdown(kpi_card("總報酬率", f"{bt['total_return']:+.2f}%", f"持有報酬 {bt['buy_hold_return']:+.2f}%", d2), unsafe_allow_html=True)
r2.markdown(kpi_card("勝率", f"{bt['win_rate']:.1f}%"), unsafe_allow_html=True)
r3.markdown(kpi_card("最大回撤", f"{bt['max_drawdown']:.2f}%"), unsafe_allow_html=True)
r4.markdown(kpi_card("Sharpe Ratio", f"{bt['sharpe_ratio']:.3f}"), unsafe_allow_html=True)
r5.markdown(kpi_card("交易次數", f"{bt['total_trades']} 次"), unsafe_allow_html=True)
r6.markdown(kpi_card("最終資產", f"${bt['final_value']:,.0f}"), unsafe_allow_html=True)

section_header("資產曲線")
st.plotly_chart(plot_portfolio_value(bt["portfolio_df"], initial_capital, ticker), use_container_width=True)

# 研究評論
tr = bt["total_return"]; bh = bt["buy_hold_return"]; alpha = tr - bh
outperf = "優於" if tr > bh else "落後於"
with st.expander("📄 回測研究報告", expanded=True):
    st.markdown(f"""
    <div class="research-box">
        <h4>策略驗證摘要</h4>
        <p>
        本次回測對 <b>{ticker}</b> 使用 <b>{sdname}</b>，
        驗證期間為 {selected_period_label}
        （{df['date'].min().date()} ～ {df['date'].max().date()}，共 {len(df)} 個交易日）。
        </p>
        <p>
        策略共執行 <b>{bt['total_trades']} 筆</b> 完整交易，勝率 <b>{bt['win_rate']:.1f}%</b>，
        總報酬率 <b>{tr:+.2f}%</b>，{outperf}買進持有基準 <b>{alpha:+.2f} 個百分點</b>。
        </p>
        <p>
        風險指標：最大回撤 <b>{bt['max_drawdown']:.2f}%</b>，
        Sharpe Ratio <b>{bt['sharpe_ratio']:.3f}</b>。
        所有訊號於收盤產生，隔日開盤執行，避免未來函數偏誤。
        </p>
    </div>""", unsafe_allow_html=True)

trades_df = bt["trades_df"]
if not trades_df.empty:
    section_header("交易紀錄")
    disp = trades_df.copy()
    for col in ["profit_pct","profit"]:
        if col in disp.columns:
            disp[col] = disp[col].map(lambda x: f"{x:+.2f}%" if col=="profit_pct" and pd.notna(x) else (f"${x:+,.0f}" if pd.notna(x) else "—"))
    if "lots" in disp.columns:
        disp["lots"] = disp["lots"].map(lambda x: f"{x} 張")
    disp["price"]  = disp["price"].map(lambda x: f"${x:.2f}")
    disp["amount"] = disp["amount"].map(lambda x: f"${x:,.0f}")
    st.dataframe(disp, use_container_width=True, hide_index=True)
else:
    st.info("此期間未產生任何交易訊號，請嘗試更長的資料期間或更換策略。")

st.markdown("---")
section_header("匯出資料")
e1,e2,e3 = st.columns(3)
with e1:
    st.download_button("📥 下載股價 + 指標 CSV", export_to_csv(df_signal, ticker),
                       get_export_filename(ticker,"分析"), "text/csv")
with e2:
    if not trades_df.empty:
        st.download_button("📥 下載交易紀錄 CSV", export_trades_to_csv(trades_df),
                           get_export_filename(ticker,"交易紀錄"), "text/csv")
with e3:
    summary = pd.DataFrame([{
        "股票代號":ticker,"策略":sdname,"期間":selected_period_label,
        "初始資金":initial_capital,"最終資產":bt["final_value"],
        "總報酬率(%)":bt["total_return"],"持有報酬(%)":bt["buy_hold_return"],
        "勝率(%)":bt["win_rate"],"最大回撤(%)":bt["max_drawdown"],
        "Sharpe":bt["sharpe_ratio"],"交易次數":bt["total_trades"]
    }])
    st.download_button("📥 下載回測摘要 CSV",
                       summary.to_csv(index=False,encoding="utf-8-sig").encode("utf-8-sig"),
                       get_export_filename(ticker,"回測摘要"), "text/csv")

st.markdown('<div style="text-align:center;font-size:0.72rem;color:#94A3B8;padding:1rem 0;">台灣股票智能分析平台 ｜ 資料來源：Yahoo Finance ｜ 僅供學術研究，不構成投資建議</div>', unsafe_allow_html=True)
