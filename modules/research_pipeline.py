# modules/research_pipeline.py
# 自動化截面因子研究流程
# 使用方式：由 scripts/run_research_study.py 或 Page 12 呼叫

import json
import os
import time
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

from modules.universe_builder import build_universe, get_ticker_coverage_df
from modules.cross_sectional_ic import (
    build_factor_panel,
    build_return_panel,
    calc_cross_sectional_ic_series,
    calc_ic_stats,
    ic_stats_to_df,
    FACTOR_NAMES,
    FACTOR_LABELS,
)
from modules.factor_portfolio import (
    build_quantile_portfolios,
    calc_cumulative_returns,
    calc_all_quantile_metrics,
    quantile_metrics_to_df,
)
from modules.multi_factor import compute_factor_matrix
from modules.finmind_client import (
    FinMindClient,
    build_fundamental_panel,
    build_flow_panel,
    get_roe,
    get_roa,
    get_eps,
    get_revenue_growth,
)

# ── 因子名稱映射 ──────────────────────────────────────────────────────────────
# 研究管線支援的因子（技術面 + 基本面 + 籌碼）
PIPELINE_FACTORS = [
    # 技術面
    "momentum_20d",
    "volume_ratio",
    "rsi_14",
    "macd_signal",
    # 基本面
    "roe",
    "roa",
    "eps_growth",
    "revenue_yoy",
    # 法人籌碼
    "foreign_net_buy",
    "trust_net_buy",
    "dealer_net_buy",
]

# compute_factor_matrix 欄位 → pipeline 命名
_TECH_COL_MAP = {
    "momentum_20d": "momentum",
    "volume_ratio": "volume_factor",
    "rsi_14":       "rsi_factor",
    "macd_signal":  "macd_factor",
}

FACTOR_ZH = {
    "momentum_20d":    "動能（20日）",
    "volume_ratio":    "成交量比",
    "rsi_14":          "RSI-14",
    "macd_signal":     "MACD 信號",
    "roe":             "ROE",
    "roa":             "ROA",
    "eps_growth":      "EPS 年增率",
    "revenue_yoy":     "月營收年增率",
    "foreign_net_buy": "外資淨買超",
    "trust_net_buy":   "投信淨買超",
    "dealer_net_buy":  "自營商淨買超",
}


# ═════════════════════════════════════════════════════════════════════════════
# ResearchPipeline
# ═════════════════════════════════════════════════════════════════════════════

class ResearchPipeline:
    """
    自動化截面因子研究流程。

    典型用法：
        pipeline = ResearchPipeline(tickers, period="2y")
        pipeline.build_universe()
        pipeline.prepare_factor_data()
        pipeline.run_ic_analysis()
        pipeline.run_factor_portfolio()
        pipeline.export_research_package()
        summary = pipeline.generate_research_summary()
    """

    def __init__(
        self,
        tickers: list,
        period: str = "2y",
        output_dir: str = "exports/research_package",
        lag: int = 1,
        n_quantiles: int = 5,
        finmind_token: str = "",
        log_cb: Optional[Callable] = None,
    ):
        self.tickers       = list(dict.fromkeys(t.strip() for t in tickers if t.strip()))
        self.period        = period
        self.output_dir    = output_dir
        self.lag           = lag
        self.n_quantiles   = n_quantiles
        self.finmind_token = finmind_token
        self._log          = log_cb or print

        # ── FinMind 用戶端（優先使用傳入 token，否則從 .env 讀取）──────────────
        import warnings
        with warnings.catch_warnings(record=True) as _w:
            warnings.simplefilter("always")
            self._fm_client = FinMindClient(token=finmind_token or None)
        if not self._fm_client.has_token:
            self._log("[Init] FinMind Token Not Found — 基本面 / 籌碼因子將跳過")

        # ── 研究狀態（各 step 填入）─────────────────────────────────────────
        self.universe_result:   dict = {}
        self.universe_data:     dict = {}          # {ticker: OHLCV DataFrame}
        self.skipped:           dict = {}          # {ticker: reason}
        self.factor_panels:     dict = {}          # {factor_name: wide DataFrame}
        self.return_panel:      pd.DataFrame = pd.DataFrame()
        self.ic_results:        dict = {}          # {factor_name: stats_dict}
        self.ic_series_all:     dict = {}          # {factor_name: IC pd.Series}
        self.portfolio_results: dict = {}          # {factor_name: result_dict}
        self._summary:          dict = {}

    # ─────────────────────────────────────────────────────────────────────────
    # A. build_universe
    # ─────────────────────────────────────────────────────────────────────────

    def build_universe(
        self,
        min_days: int = 100,
        min_avg_volume_k: float = 100.0,
        progress_cb: Optional[Callable] = None,
    ) -> dict:
        """
        建立股票池，並將 universe_summary.csv 存入 output_dir。

        Parameters
        ----------
        min_days         : 通過篩選所需的最少交易日數
        min_avg_volume_k : 通過篩選所需的最小日均量（千股）
        progress_cb      : 進度回呼 (pct, msg)

        Returns
        -------
        universe_result dict（同時儲存於 self.universe_result）
        """
        self._log(f"[A] 建立股票池：{len(self.tickers)} 檔 → period={self.period}")

        def _cb(pct, msg):
            self._log(f"    {msg}")
            if progress_cb:
                progress_cb(pct, msg)

        # ── 呼叫 universe_builder ─────────────────────────────────────────
        result = build_universe(
            tickers           = self.tickers,
            period            = self.period,
            min_days          = min_days,
            min_avg_volume_k  = min_avg_volume_k,
            progress_cb       = _cb,
        )

        self.universe_result = result
        self.universe_data   = result.get("data", {})
        self.skipped         = result.get("excluded", {})
        summary              = result.get("summary", {})

        # ── 記錄摘要 ──────────────────────────────────────────────────────
        self._log(
            f"[A] 完成：{summary.get('n_stocks', 0)} 檔通過篩選，"
            f"{summary.get('n_excluded', 0)} 檔排除，"
            f"信心分數 {summary.get('confidence_score', 0):.2f}"
            f"（{summary.get('confidence_label', '')}）"
        )

        if self.skipped:
            self._log(f"[A] 排除明細（前 5）：")
            for t, reason in list(self.skipped.items())[:5]:
                self._log(f"    {t}: {reason}")

        # ── 匯出 universe_summary.csv ─────────────────────────────────────
        self._export_universe_csv()

        return result

    def _export_universe_csv(self):
        """將股票池覆蓋情況輸出至 output_dir/universe_summary.csv"""
        if not self.universe_result:
            return

        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        cov_df = get_ticker_coverage_df(self.universe_result)

        # 附加：排除統計列
        summary = self.universe_result.get("summary", {})
        meta_rows = pd.DataFrame([{
            "代號":         "── 摘要 ──",
            "狀態":         f"通過 {summary.get('n_stocks',0)} / 請求 {summary.get('n_requested',0)}",
            "交易日數":      summary.get("avg_days", 0),
            "起始日":        summary.get("date_start", ""),
            "結束日":        summary.get("date_end", ""),
            "日均量（千股）": "—",
        }])

        export_df = pd.concat([cov_df, meta_rows], ignore_index=True)
        path = out_dir / "universe_summary.csv"
        export_df.to_csv(path, index=False, encoding="utf-8-sig")
        self._log(f"[A] 已輸出 → {path}")

        # 同時輸出 skipped_stocks.csv（若有排除標的）
        if self.skipped:
            skipped_df = pd.DataFrame([
                {"代號": t, "排除原因": r}
                for t, r in self.skipped.items()
            ])
            skip_path = out_dir / "skipped_stocks.csv"
            skipped_df.to_csv(skip_path, index=False, encoding="utf-8-sig")
            self._log(f"[A] 已輸出 → {skip_path}（{len(self.skipped)} 檔排除記錄）")

    # ─────────────────────────────────────────────────────────────────────────
    # B–F: 待實作（後續步驟）
    # ─────────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────────
    # B. prepare_factor_data
    # ─────────────────────────────────────────────────────────────────────────

    def prepare_factor_data(self, progress_cb: Optional[Callable] = None) -> dict:
        """
        計算全部 11 個因子的截面面板（date × tickers 寬表）。

        技術面（4）：compute_factor_matrix，SQLite 快取。
        基本面（4）：FinMindClient — ROE, ROA, EPS年增率, 月營收年增率。
        籌碼（3）   ：FinMindClient — 外資/投信/自營商淨買超。

        若無 FinMind Token，基本面與籌碼因子會顯示 "FinMind Token Not Found" 並跳過，
        不影響技術因子正常執行。

        Returns
        -------
        self.factor_panels : {factor_name: pd.DataFrame}
        """
        if not self.universe_data:
            self._log("[B] ⚠ 股票池為空，請先執行 build_universe()")
            return {}

        n_factors = len(PIPELINE_FACTORS)
        self._log(f"[B] 計算因子面板（{len(self.universe_data)} 檔股票，{n_factors} 個因子）")
        if not self._fm_client.has_token:
            self._log("[B] FinMind Token Not Found — 基本面/籌碼因子將跳過，僅計算技術因子")

        start_date = self._period_to_start_date()

        # 基本面 / 籌碼因子 → 使用 finmind_client 中的 panel builder
        _FUNDAMENTAL_FN = {
            "roe":         get_roe,
            "roa":         get_roa,
            "eps_growth":  lambda sid, sd, c: self._eps_growth_series(sid, sd, c),
            "revenue_yoy": get_revenue_growth,
        }
        _FLOW_KEY = {
            "foreign_net_buy": "foreign",
            "trust_net_buy":   "trust",
            "dealer_net_buy":  "dealer",
        }

        for i, fname in enumerate(PIPELINE_FACTORS):
            zh = FACTOR_ZH.get(fname, fname)
            if progress_cb:
                progress_cb(i / n_factors, f"計算因子：{zh}")
            self._log(f"[B] {i + 1}/{n_factors}  {zh}")

            try:
                # ── 技術因子 ──────────────────────────────────────────────
                if fname in _TECH_COL_MAP:
                    panel = self._build_tech_panel(fname)

                # ── 基本面因子 ────────────────────────────────────────────
                elif fname in _FUNDAMENTAL_FN:
                    if not self._fm_client.has_token:
                        self._log(f"      SKIP  FinMind Token Not Found")
                        continue
                    panel = build_fundamental_panel(
                        self.universe_data,
                        _FUNDAMENTAL_FN[fname],
                        start_date,
                        client=self._fm_client,
                    )

                # ── 籌碼因子 ──────────────────────────────────────────────
                elif fname in _FLOW_KEY:
                    if not self._fm_client.has_token:
                        self._log(f"      SKIP  FinMind Token Not Found")
                        continue
                    panel = build_flow_panel(
                        self.universe_data,
                        _FLOW_KEY[fname],
                        start_date,
                        client=self._fm_client,
                    )

                else:
                    panel = pd.DataFrame()

                if not panel.empty:
                    self.factor_panels[fname] = panel
                    self._log(f"      OK  {panel.shape[1]} 檔 × {len(panel)} 日")
                else:
                    self._log(f"      SKIP  無有效資料")

            except Exception as e:
                self._log(f"      ERROR  {e}")

        if progress_cb:
            progress_cb(1.0, "因子計算完成")

        n_ok = len(self.factor_panels)
        self._log(f"[B] 完成：{n_ok}/{n_factors} 個因子面板有效")
        return self.factor_panels

    @staticmethod
    def _eps_growth_series(stock_id: str, start_date: str, client: "FinMindClient") -> pd.Series:
        """EPS 季增率（4 季 pct_change），帶 45 日公告延遲"""
        from modules.finmind_client import get_eps
        eps = get_eps(stock_id, start_date, client)
        if len(eps) < 5:
            return pd.Series(dtype=float)
        # 年增率（同期 4 季前）
        growth = eps.pct_change(4).replace([float("inf"), float("-inf")], float("nan")) * 100
        return growth.dropna()

    # ── B 輔助：起始日期 ──────────────────────────────────────────────────────

    def _period_to_start_date(self) -> str:
        days = {"1y": 365, "2y": 730, "3y": 1095}.get(self.period, 730)
        return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # ── B 輔助：技術因子面板 ──────────────────────────────────────────────────

    def _build_tech_panel(self, factor_name: str) -> pd.DataFrame:
        """
        從 compute_factor_matrix 提取指定欄位，組成 date×tickers 面板。
        _TECH_COL_MAP 對應 pipeline 命名 → compute_factor_matrix 欄位名。
        """
        col = _TECH_COL_MAP[factor_name]
        return build_factor_panel(self.universe_data, col)

    # （_build_fundamental_panel / _build_flow_panel 已移至 finmind_client.py）

    # ─────────────────────────────────────────────────────────────────────────
    # C. run_ic_analysis
    # ─────────────────────────────────────────────────────────────────────────

    def run_ic_analysis(self, min_stocks: int = 5) -> dict:
        """
        對所有因子計算截面 IC / ICIR / t-stat，並輸出兩個 CSV。

        輸出：
            factor_ic_summary.csv    — 每個因子的彙總統計
            factor_ic_timeseries.csv — 每日 IC 時序（date × factors）

        Returns
        -------
        self.ic_results : {factor_name: stats_dict}
        """
        if not self.factor_panels:
            self._log("[C] ⚠ 無因子面板，請先執行 prepare_factor_data()")
            return {}
        if not self.universe_data:
            self._log("[C] ⚠ 股票池為空")
            return {}

        self._log(f"[C] 截面 IC 分析  lag={self.lag}d  min_stocks={min_stocks}")

        # 建立前瞻報酬面板（一次建立，所有因子共用）
        self.return_panel = build_return_panel(self.universe_data, lag=self.lag)
        self._log(f"    報酬面板：{self.return_panel.shape[1]} 檔 × {len(self.return_panel)} 日")

        for fname, f_panel in self.factor_panels.items():
            try:
                ic_series = calc_cross_sectional_ic_series(
                    f_panel, self.return_panel, min_stocks=min_stocks
                )
                stats = calc_ic_stats(ic_series, factor_name=fname)
                self.ic_results[fname]    = stats
                self.ic_series_all[fname] = ic_series

                sig_mark = "[SIG]" if stats["significant"] else "—"
                self._log(
                    f"    {FACTOR_ZH.get(fname, fname):14s}"
                    f"  IC={stats['mean_ic']:+.4f}"
                    f"  ICIR={stats['icir']:+.3f}"
                    f"  t={stats['t_stat']:+.2f}"
                    f"  {sig_mark}"
                )

            except Exception as e:
                self._log(f"    ERROR {fname}: {e}")

        # ── 匯出 CSV ─────────────────────────────────────────────────────
        self._export_ic_csvs()

        n_sig = sum(1 for s in self.ic_results.values() if s.get("significant"))
        self._log(f"[C] 完成：{len(self.ic_results)} 個因子，{n_sig} 個統計顯著（|t|>2）")
        return self.ic_results

    def _export_ic_csvs(self):
        """輸出 factor_ic_summary.csv 與 factor_ic_timeseries.csv"""
        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # ── 1. factor_ic_summary.csv ──────────────────────────────────────
        rows = []
        for fname, s in self.ic_results.items():
            rows.append({
                "因子英文名":  fname,
                "因子中文名":  FACTOR_ZH.get(fname, fname),
                "Mean IC":     round(s.get("mean_ic",      0), 4),
                "Std IC":      round(s.get("std_ic",       0), 4),
                "ICIR":        round(s.get("icir",         0), 4),
                "t-stat":      round(s.get("t_stat",       0), 4),
                "p-value":     round(s.get("p_value",      1), 4),
                "顯著(|t|>2)": "是" if s.get("significant") else "否",
                "正向比例":    round(s.get("pct_positive",  0), 3),
                "有效截面數":  s.get("n_obs", 0),
                "lag(日)":     self.lag,
            })

        summary_df = pd.DataFrame(rows)
        # 依 |Mean IC| 降序排列，方便閱讀
        summary_df["_abs_ic"] = summary_df["Mean IC"].abs()
        summary_df = summary_df.sort_values("_abs_ic", ascending=False).drop(columns="_abs_ic")

        p1 = out_dir / "factor_ic_summary.csv"
        summary_df.to_csv(p1, index=False, encoding="utf-8-sig")
        self._log(f"[C] 已輸出 → {p1}")

        # ── 2. factor_ic_timeseries.csv ───────────────────────────────────
        ts_dict = {}
        for fname, ic_s in self.ic_series_all.items():
            if isinstance(ic_s, pd.Series) and not ic_s.empty:
                ts_dict[FACTOR_ZH.get(fname, fname)] = ic_s

        if ts_dict:
            ts_df = pd.DataFrame(ts_dict)
            ts_df.index.name = "date"
            p2 = out_dir / "factor_ic_timeseries.csv"
            ts_df.to_csv(p2, encoding="utf-8-sig")
            self._log(f"[C] 已輸出 → {p2}  ({len(ts_df)} 列 × {len(ts_df.columns)} 欄)")

    # ─────────────────────────────────────────────────────────────────────────
    # D. run_factor_portfolio
    # ─────────────────────────────────────────────────────────────────────────

    def run_factor_portfolio(self, min_stocks: int = 5) -> dict:
        """
        對所有因子建立五分位組合，計算 Long-Short 績效，輸出兩個 CSV。

        輸出：
            quantile_return.csv    — 每日 Q1~Q5 + LS 報酬（所有因子合併）
            long_short_return.csv  — Long-Short 每日報酬與累積報酬

        Returns
        -------
        self.portfolio_results : {factor_name: result_dict}
        """
        if not self.factor_panels:
            self._log("[D] ⚠ 無因子面板，請先執行 prepare_factor_data()")
            return {}
        if self.return_panel is None or self.return_panel.empty:
            self._log("[D] 建立報酬面板...")
            self.return_panel = build_return_panel(self.universe_data, lag=self.lag)

        self._log(f"[D] 分位組合分析  n_quantiles={self.n_quantiles}  lag={self.lag}d")

        for fname, f_panel in self.factor_panels.items():
            try:
                q_df = build_quantile_portfolios(
                    f_panel, self.return_panel,
                    n_quantiles=self.n_quantiles,
                    min_stocks=min_stocks,
                )
                if q_df.empty:
                    self._log(f"    SKIP {FACTOR_ZH.get(fname, fname)}：有效截面不足")
                    continue

                cum_df  = calc_cumulative_returns(q_df)
                metrics = calc_all_quantile_metrics(q_df)

                self.portfolio_results[fname] = {
                    "quantile_df":   q_df,
                    "cumulative_df": cum_df,
                    "metrics":       metrics,
                }

                # 印出 L/S 摘要
                ls_m = metrics.get("LS", {})
                if ls_m.get("annual_return") is not None:
                    self._log(
                        f"    {FACTOR_ZH.get(fname, fname):14s}"
                        f"  L/S 年化={ls_m['annual_return']*100:+.1f}%"
                        f"  Sharpe={ls_m['sharpe']:+.2f}"
                        f"  MaxDD={ls_m['max_drawdown']*100:.1f}%"
                    )

            except Exception as e:
                self._log(f"    ERROR {fname}: {e}")

        self._export_portfolio_csvs()
        self._log(f"[D] 完成：{len(self.portfolio_results)} 個因子分位組合")
        return self.portfolio_results

    def _export_portfolio_csvs(self):
        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # ── 1. quantile_return.csv：所有因子的每日分位報酬合併 ──────────────
        q_frames = []
        for fname, res in self.portfolio_results.items():
            df = res["quantile_df"].copy()
            df.columns = [f"{FACTOR_ZH.get(fname, fname)}_{c}" for c in df.columns]
            q_frames.append(df)

        if q_frames:
            q_all = pd.concat(q_frames, axis=1)
            q_all.index.name = "date"
            p1 = out_dir / "quantile_return.csv"
            q_all.to_csv(p1, encoding="utf-8-sig")
            self._log(f"[D] 已輸出 → {p1}")

        # ── 2. long_short_return.csv：各因子 L/S 每日報酬 + 累積報酬 ────────
        ls_frames = {}
        cum_frames = {}
        for fname, res in self.portfolio_results.items():
            q_df   = res["quantile_df"]
            cum_df = res["cumulative_df"]
            zh     = FACTOR_ZH.get(fname, fname)
            if "LS" in q_df.columns:
                ls_frames[f"{zh}_日報酬"]  = q_df["LS"]
                cum_frames[f"{zh}_累積報酬"] = cum_df["LS"]

        if ls_frames:
            ls_df = pd.DataFrame({**ls_frames, **cum_frames})
            ls_df.index.name = "date"
            p2 = out_dir / "long_short_return.csv"
            ls_df.to_csv(p2, encoding="utf-8-sig")
            self._log(f"[D] 已輸出 → {p2}")

    # ─────────────────────────────────────────────────────────────────────────
    # E. export_research_package
    # ─────────────────────────────────────────────────────────────────────────

    def export_research_package(self) -> str:
        """
        將所有 CSV + 圖表打包為完整研究套件。

        目錄結構：
            output_dir/
            ├── universe_summary.csv
            ├── skipped_stocks.csv
            ├── factor_ic_summary.csv
            ├── factor_ic_timeseries.csv
            ├── quantile_return.csv
            ├── long_short_return.csv
            ├── research_summary.json
            └── charts/
                ├── ic_bar.html
                ├── ic_timeseries.html
                ├── ls_comparison.html
                └── quantile_{factor}.html  × 每個因子

        Returns
        -------
        str  output_dir 的絕對路徑
        """
        self._log("[E] 匯出研究套件...")
        out_dir   = Path(self.output_dir)
        chart_dir = out_dir / "charts"
        chart_dir.mkdir(parents=True, exist_ok=True)

        try:
            import plotly.graph_objects as go

            # ── 圖表 1：IC Bar Chart ──────────────────────────────────────
            if self.ic_results:
                names  = [FACTOR_ZH.get(k, k) for k in self.ic_results]
                ics    = [self.ic_results[k].get("mean_ic", 0) for k in self.ic_results]
                colors = ["#16A34A" if v > 0.03 else
                          "#F59E0B" if v > 0    else "#DC2626"
                          for v in ics]
                fig1 = go.Figure(go.Bar(
                    x=names, y=ics,
                    marker_color=colors,
                    text=[f"{v:+.4f}" for v in ics],
                    textposition="outside",
                ))
                fig1.add_hline(y=0.03,  line_dash="dot", line_color="#16A34A",
                               annotation_text="IC=0.03 門檻")
                fig1.add_hline(y=-0.03, line_dash="dot", line_color="#DC2626")
                fig1.update_layout(
                    title=f"截面 IC 比較（lag={self.lag}日）",
                    yaxis_title="Mean IC",
                    template="plotly_white", height=400,
                    margin=dict(l=10, r=10, t=50, b=10),
                )
                fig1.write_html(str(chart_dir / "ic_bar.html"))

            # ── 圖表 2：IC 時序圖 ─────────────────────────────────────────
            if self.ic_series_all:
                fig2 = go.Figure()
                palette = ["#1E40AF","#16A34A","#7C3AED","#F59E0B",
                           "#DC2626","#0891B2","#BE185D","#065F46","#92400E"]
                for idx, (fname, ic_s) in enumerate(self.ic_series_all.items()):
                    if isinstance(ic_s, pd.Series) and not ic_s.empty:
                        roll = ic_s.rolling(20, min_periods=10).mean()
                        fig2.add_trace(go.Scatter(
                            x=roll.index, y=roll.values,
                            name=FACTOR_ZH.get(fname, fname),
                            line=dict(color=palette[idx % len(palette)], width=1.5),
                        ))
                fig2.add_hline(y=0.03,  line_dash="dot", line_color="#16A34A")
                fig2.add_hline(y=-0.03, line_dash="dot", line_color="#DC2626")
                fig2.add_hline(y=0, line_color="#94A3B8", line_width=1)
                fig2.update_layout(
                    title="IC 時序（20日滾動均值）",
                    yaxis_title="IC", template="plotly_white", height=380,
                    margin=dict(l=10, r=10, t=50, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                fig2.write_html(str(chart_dir / "ic_timeseries.html"))

            # ── 圖表 3：L/S 累積報酬比較 ─────────────────────────────────
            if self.portfolio_results:
                fig3 = go.Figure()
                palette3 = ["#1E40AF","#16A34A","#7C3AED","#F59E0B",
                            "#DC2626","#0891B2","#BE185D","#065F46","#92400E"]
                for idx, (fname, res) in enumerate(self.portfolio_results.items()):
                    cum_df = res.get("cumulative_df", pd.DataFrame())
                    if "LS" in cum_df.columns:
                        ls = cum_df["LS"].dropna()
                        fig3.add_trace(go.Scatter(
                            x=ls.index, y=ls.values * 100,
                            name=FACTOR_ZH.get(fname, fname),
                            line=dict(color=palette3[idx % len(palette3)], width=2),
                        ))
                fig3.add_hline(y=0, line_color="#475569")
                fig3.update_layout(
                    title="Long-Short 累積報酬比較",
                    yaxis_title="累積報酬 (%)",
                    template="plotly_white", height=400,
                    margin=dict(l=10, r=10, t=50, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                fig3.write_html(str(chart_dir / "ls_comparison.html"))

            # ── 圖表 4：各因子分位報酬長條圖 ─────────────────────────────
            for fname, res in self.portfolio_results.items():
                metrics = res.get("metrics", {})
                q_labels = [f"Q{q}" for q in range(1, self.n_quantiles + 1)] + ["LS"]
                valid = [
                    (lab, metrics[lab]["annual_return"] * 100)
                    for lab in q_labels
                    if metrics.get(lab, {}).get("annual_return") is not None
                ]
                if not valid:
                    continue
                labs, rets = zip(*valid)
                colors_q = []
                for lab, ret in zip(labs, rets):
                    if lab == "LS":
                        colors_q.append("#8B5CF6" if ret >= 0 else "#EF4444")
                    else:
                        colors_q.append("#16A34A" if ret >= 0 else "#DC2626")

                fig4 = go.Figure(go.Bar(
                    x=list(labs), y=list(rets),
                    marker_color=colors_q,
                    text=[f"{r:.1f}%" for r in rets],
                    textposition="outside",
                ))
                fig4.add_hline(y=0, line_color="#475569")
                fig4.update_layout(
                    title=f"{FACTOR_ZH.get(fname, fname)} — 各分位年化報酬",
                    yaxis_title="年化報酬 (%)",
                    template="plotly_white", height=360,
                    margin=dict(l=10, r=10, t=50, b=10),
                )
                safe = fname.replace("/", "_")
                fig4.write_html(str(chart_dir / f"quantile_{safe}.html"))

            self._log(f"[E] 圖表已輸出 → {chart_dir}")

        except ImportError:
            self._log("[E] ⚠ plotly 未安裝，跳過圖表產生")
        except Exception as e:
            self._log(f"[E] 圖表產生失敗：{e}")

        # ── 輸出 research_summary.json ────────────────────────────────────
        summary = self.generate_research_summary()
        json_path = out_dir / "research_summary.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
        self._log(f"[E] 已輸出 → {json_path}")

        abs_path = str(out_dir.resolve())
        self._log(f"[E] 研究套件完整輸出至 → {abs_path}")
        return abs_path

    def make_zip_bytes(self) -> bytes:
        """
        將 output_dir 所有檔案打包為 ZIP，回傳 bytes（供 Streamlit 下載）。
        不需要先 export_research_package，但建議先呼叫以確保所有檔案已產生。
        """
        buf = BytesIO()
        out_dir = Path(self.output_dir)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fpath in out_dir.rglob("*"):
                if fpath.is_file():
                    zf.write(fpath, fpath.relative_to(out_dir))
        buf.seek(0)
        return buf.read()

    # ─────────────────────────────────────────────────────────────────────────
    # F. generate_research_summary
    # ─────────────────────────────────────────────────────────────────────────

    def generate_research_summary(self) -> dict:
        """
        彙整研究結果為 JSON-serializable dict。

        格式：
        {
          "research_title": "...",
          "generated_at":   "...",
          "sample_period":  "...",
          "universe_size":  N,
          "n_factors":      9,
          "lag_days":       1,
          "best_factor":    "...",
          "best_ic":        0.08,
          "best_icir":      1.21,
          "long_short_sharpe": 1.15,
          "n_significant_factors": 3,
          "factor_ranking": [...],
          "key_findings":   [...]
        }
        """
        s = self.universe_result.get("summary", {})
        universe_size = s.get("n_stocks", len(self.universe_data))
        date_start    = s.get("date_start", "")
        date_end      = s.get("date_end",   "")
        confidence    = s.get("confidence_score", 0.0)

        # ── 最佳因子（依 |Mean IC| 排序）──────────────────────────────────
        best_factor = ""
        best_ic     = 0.0
        best_icir   = 0.0
        if self.ic_results:
            best_factor = max(
                self.ic_results,
                key=lambda k: abs(self.ic_results[k].get("mean_ic", 0)),
            )
            best_ic   = self.ic_results[best_factor].get("mean_ic",  0.0)
            best_icir = self.ic_results[best_factor].get("icir",     0.0)

        # ── 最佳因子的 L/S Sharpe ─────────────────────────────────────────
        ls_sharpe = None
        if best_factor in self.portfolio_results:
            ls_m = self.portfolio_results[best_factor]["metrics"].get("LS", {})
            ls_sharpe = ls_m.get("sharpe")

        # ── 顯著因子數 ────────────────────────────────────────────────────
        n_sig = sum(1 for s in self.ic_results.values() if s.get("significant"))

        # ── 因子排名表 ────────────────────────────────────────────────────
        factor_ranking = []
        for fname, stats in sorted(
            self.ic_results.items(),
            key=lambda kv: abs(kv[1].get("mean_ic", 0)),
            reverse=True,
        ):
            ls_m = self.portfolio_results.get(fname, {}).get("metrics", {}).get("LS", {})
            factor_ranking.append({
                "factor":      fname,
                "factor_zh":   FACTOR_ZH.get(fname, fname),
                "mean_ic":     round(float(stats.get("mean_ic", 0)), 4),
                "icir":        round(float(stats.get("icir",    0)), 4),
                "t_stat":      round(float(stats.get("t_stat",  0)), 4),
                "significant": bool(stats.get("significant", False)),
                "ls_sharpe":   round(float(ls_m["sharpe"]), 3) if ls_m.get("sharpe") is not None else None,
                "ls_annual_return": round(float(ls_m["annual_return"]), 4) if ls_m.get("annual_return") is not None else None,
            })

        # ── key_findings 自動生成 ─────────────────────────────────────────
        findings = []

        if best_factor:
            ic_strength = (
                "強（|IC|>0.10）" if abs(best_ic) > 0.10 else
                "中等（|IC|>0.05）" if abs(best_ic) > 0.05 else
                "弱但有效（|IC|>0.03）" if abs(best_ic) > 0.03 else
                "未達門檻（|IC|<0.03）"
            )
            findings.append(
                f"最佳因子：{FACTOR_ZH.get(best_factor, best_factor)}"
                f"（IC={best_ic:+.4f}，{ic_strength}，ICIR={best_icir:.3f}）"
            )

        if n_sig > 0:
            sig_names = [
                FACTOR_ZH.get(k, k)
                for k, v in self.ic_results.items()
                if v.get("significant")
            ]
            findings.append(
                f"{n_sig} 個因子統計顯著（|t|>2）：{', '.join(sig_names)}"
            )
        else:
            findings.append("所有因子均未達統計顯著水準（|t|<2），可能需要更大股票池或更長樣本期")

        if ls_sharpe is not None:
            ls_eval = (
                "優良（Sharpe>1.0）" if ls_sharpe > 1.0 else
                "可接受（Sharpe 0.5~1.0）" if ls_sharpe > 0.5 else
                "偏低（Sharpe<0.5，需評估交易成本）"
            )
            findings.append(
                f"最佳因子 Long-Short 年化 Sharpe={ls_sharpe:.3f}（{ls_eval}）"
            )

        findings.append(
            f"股票池：{universe_size} 檔，信心分數 {confidence:.2f}，"
            f"資料期間 {date_start} ~ {date_end}"
        )

        summary = {
            "research_title":        "台股截面多因子研究",
            "generated_at":          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sample_period":         f"{date_start} ~ {date_end}",
            "universe_size":         universe_size,
            "n_factors":             len(self.factor_panels),
            "lag_days":              self.lag,
            "confidence_score":      confidence,
            "best_factor":           FACTOR_ZH.get(best_factor, best_factor),
            "best_factor_en":        best_factor,
            "best_ic":               round(float(best_ic),   4),
            "best_icir":             round(float(best_icir), 4),
            "long_short_sharpe":     round(float(ls_sharpe), 3) if ls_sharpe is not None else None,
            "n_significant_factors": n_sig,
            "factor_ranking":        factor_ranking,
            "key_findings":          findings,
        }

        self._summary = summary
        return summary
