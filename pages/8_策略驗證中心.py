# pages/8_策略驗證中心.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from modules.ui_components import inject_css, page_header, disclaimer, section_header, kpi_card
from utils.data_fetcher import get_stock_data
from utils.indicators import add_all_indicators
from utils.backtest import run_backtest, plot_portfolio_value
from strategies.ma_strategy import ma_crossover_strategy
from strategies.rsi_strategy import rsi_reversal_strategy, rsi_strategy
from strategies.macd_strategy import macd_crossover_strategy
from modules.explainability import generate_strategy_interpretation

st.set_page_config(page_title="策略驗證中心", page_icon="🧪", layout="wide")
inject_css()

page_header("策略驗證中心", "系統化回測 · 績效歸因 · 研究級報告 · 策略比較", "🧪")
disclaimer()

with st.sidebar:
    st.markdown('<div style="padding:1rem 0.5rem 0.5rem;"><div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">🧪 策略驗證設定</div></div><hr style="border-color:#1E293B;">', unsafe_allow_html=True)
    ticker = st.text_input("股票代號", value="2330")
    period_opts = {"近1年":"1y","近2年":"2y","近3年":"3y","近5年":"5y"}
    period = period_opts[st.selectbox("驗證期間", list(period_opts.keys()), index=1)]
    strategies_to_run = st.multiselect("選擇要比較的策略",
        ["MA 均線交叉","RSI 回拉確認","RSI 超買超賣","MACD 訊號交叉"],
        default=["MA 均線交叉","RSI 回拉確認"])
    initial_capital  = st.number_input("初始資金（元）", value=100_000, step=10_000, format="%d")
    stop_loss_pct    = st.slider("停損比例（%）", 0, 20, 5, 1)
    stop_profit_pct  = st.slider("停利比例（%）", 0, 50, 0, 1)
    run = st.button("▶ 開始驗證", type="primary", use_container_width=True)

if not run:
    section_header("關於本模組")
    st.markdown("""
    <div class="research-box">
        <h4>策略驗證中心</h4>
        <p>本模組提供系統化、研究級的策略回測功能，嚴格遵守以下規範：</p>
        <ul style="margin:0.5rem 0 0 1rem;font-size:0.85rem;">
            <li><b>無未來函數偏誤</b>：訊號於收盤產生（T日），隔日開盤執行（T+1）</li>
            <li><b>實際交易成本</b>：手續費 0.1425% + 交易稅 0.3%</li>
            <li><b>整張交易</b>：台灣標準（每張 1000 股）</li>
            <li><b>風險管理</b>：可設定停損停利比例</li>
        </ul>
    </div>""", unsafe_allow_html=True)
    st.stop()

ticker = ticker.strip().upper()
with st.spinner(f"載入 {ticker} 資料中..."):
    try:
        df_raw = get_stock_data(ticker, period=period, force_refresh=False)
    except ValueError as e:
        st.error(f"❌ {e}"); st.stop()
df = add_all_indicators(df_raw)

st.markdown(f"""<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;
    padding:0.7rem 1rem;font-size:0.82rem;color:#14532D;margin-bottom:1rem;">
    ✅ 資料載入完成：<b>{ticker}</b> · {len(df)} 個交易日（{df['date'].min().date()} ～ {df['date'].max().date()}）
</div>""", unsafe_allow_html=True)

STRATEGY_MAP = {
    "MA 均線交叉":   (ma_crossover_strategy,  "MA 均線交叉策略（MA5×MA20）"),
    "RSI 回拉確認":  (rsi_reversal_strategy,   "RSI 回拉確認策略"),
    "RSI 超買超賣":  (rsi_strategy,            "RSI 超買超賣策略"),
    "MACD 訊號交叉": (macd_crossover_strategy, "MACD 訊號線交叉策略"),
}

results = {}
for strat_name in strategies_to_run:
    fn, display_name = STRATEGY_MAP[strat_name]
    df_sig = fn(df)
    bt = run_backtest(df_sig, initial_capital=initial_capital,
                      stop_loss_pct=stop_loss_pct/100, stop_profit_pct=stop_profit_pct/100)
    results[strat_name] = {"bt": bt, "df_sig": df_sig, "display_name": display_name}

section_header("策略績效比較")
comparison_data = []
for strat_name, res in results.items():
    bt = res["bt"]
    comparison_data.append({
        "策略":        res["display_name"],
        "總報酬率":    f"{bt['total_return']:+.2f}%",
        "勝率":        f"{bt['win_rate']:.1f}%",
        "Sharpe":      f"{bt['sharpe_ratio']:.3f}",
        "最大回撤":    f"{bt['max_drawdown']:.2f}%",
        "交易次數":    bt["total_trades"],
        "最終資產":    f"${bt['final_value']:,.0f}",
        "_return":     bt["total_return"],
    })
buy_hold = results[strategies_to_run[0]]["bt"]["buy_hold_return"]
comparison_data.append({
    "策略":"買進持有（基準）","總報酬率":f"{buy_hold:+.2f}%",
    "勝率":"—","Sharpe":"—","最大回撤":"—","交易次數":0,"最終資產":"—","_return":buy_hold,
})
cmp_df = pd.DataFrame(comparison_data)
st.dataframe(cmp_df.drop(columns=["_return"]), use_container_width=True, hide_index=True)

section_header("資產曲線比較（策略 vs 買進持有）")
fig_eq = go.Figure()
colors = ["#1E40AF","#16A34A","#F59E0B","#DC2626"]
for i, (strat_name, res) in enumerate(results.items()):
    pf_df = res["bt"]["portfolio_df"]
    fig_eq.add_trace(go.Scatter(x=pf_df["date"], y=pf_df["portfolio_value"],
        name=res["display_name"], line=dict(color=colors[i%len(colors)], width=2)))
bh_df    = results[strategies_to_run[0]]["df_sig"].copy()
bh_start = float(bh_df["close"].iloc[0])
bh_values= [initial_capital * (float(p)/bh_start) for p in bh_df["close"]]
fig_eq.add_trace(go.Scatter(x=bh_df["date"], y=bh_values,
    name="買進持有", line=dict(color="#94A3B8", width=1.5, dash="dash")))
fig_eq.add_hline(y=initial_capital, line_dash="dot", line_color="#CBD5E1", annotation_text="初始資金")
fig_eq.update_layout(template="plotly_white", height=420,
    legend=dict(orientation="h",y=1.05,x=0), margin=dict(l=10,r=10,t=40,b=10))
st.plotly_chart(fig_eq, use_container_width=True)

for strat_name, res in results.items():
    bt = res["bt"]
    st.markdown("---")
    section_header(f"詳細報告 — {res['display_name']}")
    r1,r2,r3,r4,r5 = st.columns(5)
    d = "up" if bt["total_return"]>=0 else "down"
    r1.markdown(kpi_card("總報酬率",  f"{bt['total_return']:+.2f}%", direction=d), unsafe_allow_html=True)
    r2.markdown(kpi_card("勝率",      f"{bt['win_rate']:.1f}%"), unsafe_allow_html=True)
    r3.markdown(kpi_card("Sharpe",    f"{bt['sharpe_ratio']:.3f}"), unsafe_allow_html=True)
    r4.markdown(kpi_card("最大回撤",  f"{bt['max_drawdown']:.2f}%"), unsafe_allow_html=True)
    r5.markdown(kpi_card("交易次數",  f"{bt['total_trades']} 次"), unsafe_allow_html=True)

    period_label = [k for k,v in {"近1年":"1y","近2年":"2y","近3年":"3y","近5年":"5y"}.items() if v==period]
    period_label = period_label[0] if period_label else period
    interpretation = generate_strategy_interpretation(bt, res['display_name'], ticker, period_label)

    tab_a, tab_b = st.tabs(["📄 回測摘要", "🔍 策略解讀"])
    with tab_a:
        tr = bt["total_return"]; bh = bt["buy_hold_return"]; alpha = tr-bh
        outperf = "優於" if tr>bh else "落後"
        st.markdown(f"""<div class="research-box">
        <h4>策略驗證摘要</h4>
        <p>本次驗證對 <b>{ticker}</b> 使用 <b>{res['display_name']}</b>，期間 {period_label}。
        共執行 <b>{bt['total_trades']} 筆</b>交易，勝率 <b>{bt['win_rate']:.1f}%</b>，
        總報酬率 <b>{tr:+.2f}%</b>，{outperf}買進持有基準 <b>{alpha:+.2f}</b> 個百分點。
        Sharpe Ratio <b>{bt['sharpe_ratio']:.3f}</b>，最大回撤 <b>{bt['max_drawdown']:.2f}%</b>。</p>
        </div>""", unsafe_allow_html=True)
    with tab_b:
        st.markdown(f'<div class="research-box">{interpretation}</div>', unsafe_allow_html=True)

    if not bt["trades_df"].empty:
        with st.expander("📋 交易紀錄"):
            td = bt["trades_df"].copy()
            for c in ["profit_pct","profit"]:
                if c in td.columns:
                    td[c] = td[c].map(lambda x: f"{x:+.2f}%" if c=="profit_pct" and pd.notna(x) else (f"${x:+,.0f}" if pd.notna(x) else "—"))
            td["price"]  = td["price"].map(lambda x: f"${x:.2f}")
            td["amount"] = td["amount"].map(lambda x: f"${x:,.0f}")
            st.dataframe(td, use_container_width=True, hide_index=True)

st.caption("僅供學術研究，不構成投資建議")
