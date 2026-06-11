# pages/6_投資組合管理.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from modules.portfolio import add_holding, delete_holding, get_all_holdings, calc_portfolio_pnl
from modules.data_source import fetch_realtime_quote, get_stock_name
from modules.ui_components import inject_css, page_header, disclaimer, section_header, kpi_card
from utils.data_fetcher import get_stock_data

st.set_page_config(page_title="投資組合管理", page_icon="💼", layout="wide")
inject_css()

page_header("投資組合管理", "持倉損益追蹤 · 資產配置 · 多股比較 ｜ 資料存於本機，不上傳任何伺服器", "💼")
disclaimer()
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📋 持倉損益", "➕ 新增持倉", "📊 多股比較"])

with tab1:
    holdings_df = get_all_holdings()
    if holdings_df.empty:
        st.info("目前尚無持倉紀錄，請到「新增持倉」頁面加入。")
    else:
        tickers = holdings_df["ticker"].unique().tolist()
        with st.spinner("更新最新股價中..."):
            current_prices = {}
            for t in tickers:
                try:
                    q = fetch_realtime_quote(t); current_prices[t] = q["price"]
                except Exception:
                    current_prices[t] = None
        pnl_df = calc_portfolio_pnl(holdings_df, current_prices)
        valid = pnl_df.dropna(subset=["市值"])
        total_value = valid["市值"].sum(); total_cost = valid["成本"].sum()
        total_pnl = total_value - total_cost
        total_pct = (total_pnl/total_cost*100) if total_cost>0 else 0
        m1,m2,m3,m4,m5 = st.columns(5)
        m1.markdown(kpi_card("總市值",   f"${total_value:,.0f}"), unsafe_allow_html=True)
        m2.markdown(kpi_card("總成本",   f"${total_cost:,.0f}"),  unsafe_allow_html=True)
        d = "up" if total_pnl>=0 else "down"
        m3.markdown(kpi_card("未實現損益", f"${total_pnl:+,.0f}", f"{total_pct:+.2f}%", d), unsafe_allow_html=True)
        m4.markdown(kpi_card("持倉檔數", f"{len(valid)} 檔"), unsafe_allow_html=True)
        m5.markdown(kpi_card("報酬率",   f"{total_pct:+.2f}%", direction=d), unsafe_allow_html=True)
        st.markdown("---")
        section_header("持倉明細")
        display = pnl_df.copy()
        display["損益%"] = display["損益%"].map(lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A")
        display["損益$"] = display["損益$"].map(lambda x: f"${x:+,.0f}" if pd.notna(x) else "N/A")
        display["市值"]  = display["市值"].map(lambda x: f"${x:,.0f}" if pd.notna(x) else "N/A")
        display["成本"]  = display["成本"].map(lambda x: f"${x:,.0f}" if pd.notna(x) else "N/A")
        display["現價"]  = display["現價"].map(lambda x: f"${x:.1f}" if pd.notna(x) else "N/A")
        show_cols = [c for c in ["id","ticker","name","group_name","lots","cost_price","現價","損益$","損益%","市值","buy_date"] if c in display.columns]
        st.dataframe(display[show_cols].rename(columns={"id":"ID","ticker":"代號","name":"名稱","group_name":"群組","lots":"張數","cost_price":"成本均價","buy_date":"買入日"}), use_container_width=True, hide_index=True)
        with st.expander("🗑️ 刪除持倉"):
            del_id = st.number_input("輸入要刪除的 ID", min_value=1, step=1)
            if st.button("確認刪除"):
                if delete_holding(int(del_id)): st.success("✅ 刪除成功！請重新整理頁面。")
                else: st.error("刪除失敗")
        st.markdown("---")
        col_pie, col_bar = st.columns(2)
        with col_pie:
            section_header("持倉配置（市值）")
            valid_pnl = pnl_df.dropna(subset=["市值"])
            if not valid_pnl.empty:
                fig_pie = px.pie(valid_pnl, names="ticker", values="市值", title="持倉市值分佈", template="plotly_white", hole=0.4)
                fig_pie.update_layout(height=350, margin=dict(l=10,r=10,t=50,b=10))
                st.plotly_chart(fig_pie, use_container_width=True)
        with col_bar:
            section_header("各標的損益率（%）")
            valid_pnl2 = pnl_df.dropna(subset=["損益%"])
            if not valid_pnl2.empty:
                fig_bar = go.Figure(go.Bar(
                    x=valid_pnl2["ticker"], y=valid_pnl2["損益%"],
                    marker_color=["#16A34A" if v>=0 else "#DC2626" for v in valid_pnl2["損益%"]],
                    text=valid_pnl2["損益%"].map(lambda x: f"{x:+.1f}%"), textposition="outside"))
                fig_bar.update_layout(title="各標的損益率",template="plotly_white",height=350,margin=dict(l=10,r=10,t=50,b=10))
                st.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    section_header("新增持倉紀錄")
    with st.form("add_holding_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            new_ticker = st.text_input("股票代號 *", placeholder="例如：2330")
            new_lots   = st.number_input("張數 *", min_value=1, value=1, step=1)
            new_cost   = st.number_input("成本均價（元）*", min_value=0.1, value=100.0, step=0.1)
        with col_b:
            new_group  = st.text_input("群組", value="預設")
            new_date   = st.date_input("買入日期")
            new_note   = st.text_input("備註", placeholder="選填")
        submitted = st.form_submit_button("✅ 新增持倉", type="primary")
        if submitted:
            if not new_ticker: st.error("請輸入股票代號！")
            else:
                try: stock_name = get_stock_name(new_ticker.strip())
                except: stock_name = new_ticker.strip()
                success = add_holding(ticker=new_ticker.strip().upper(), name=stock_name,
                    lots=int(new_lots), cost_price=float(new_cost),
                    group_name=new_group or "預設", buy_date=str(new_date), note=new_note or "")
                if success: st.success(f"✅ 已新增 {new_ticker.upper()} {new_lots} 張，成本 ${new_cost}"); st.balloons()
                else: st.error("新增失敗")
    st.caption("1 張 = 1000 股 ｜ 資料儲存於本機 SQLite，不會上傳")

with tab3:
    section_header("多股走勢比較")
    compare_input = st.text_input("輸入多個股票代號（逗號分隔）", value="2330,2317,2454")
    period_opt = st.selectbox("比較期間", ["1mo","3mo","6mo","1y","2y"], index=2)
    run_compare = st.button("📊 開始比較", type="primary")
    if run_compare:
        tickers_cmp = [t.strip() for t in compare_input.split(",") if t.strip()]
        with st.spinner("下載比較資料..."):
            fig_cmp = go.Figure()
            for t in tickers_cmp:
                try:
                    df_c = get_stock_data(t, period=period_opt, force_refresh=False)
                    if df_c.empty: continue
                    base = df_c["close"].iloc[0]
                    df_c["ret"] = (df_c["close"] / base - 1) * 100
                    fig_cmp.add_trace(go.Scatter(x=df_c["date"], y=df_c["ret"], name=t, mode="lines", line=dict(width=2)))
                except: st.warning(f"{t} 資料取得失敗")
            fig_cmp.add_hline(y=0, line_dash="dash", line_color="#CBD5E1")
            fig_cmp.update_layout(title="多股累積報酬率比較（%）",template="plotly_white",height=450,margin=dict(l=10,r=10,t=50,b=10))
            st.plotly_chart(fig_cmp, use_container_width=True)

st.caption("資料來源：Yahoo Finance ｜ 僅供學術研究，不構成投資建議")
