"""
scripts/run_research_study.py
台股截面因子研究自動化執行腳本

用法：
    python scripts/run_research_study.py
    python scripts/run_research_study.py --period 2y --universe 50
    python scripts/run_research_study.py --period 3y --universe 80 --lag 5 --output exports/my_study

執行前請確認：
    - 從專案根目錄執行（pyproject.toml 所在位置）
    - pip install -e . 已執行（或確認 modules/ 在 sys.path）
"""

# ── 標準函式庫 ────────────────────────────────────────────────────────────────
import argparse
import sys
import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# ── 確保專案根目錄在 sys.path（從任意位置執行腳本時用）─────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── 第三方函式庫 ──────────────────────────────────────────────────────────────
import pandas as pd

# ── 本地模組（lazy import：在 main() 裡才 import，避免啟動時 crash）──────────────
# from modules.research_pipeline import ResearchPipeline   ← 在 main() 裡 import


# ═════════════════════════════════════════════════════════════════════════════
# 1. 預設股票池（如果使用者未指定 --tickers）
# ═════════════════════════════════════════════════════════════════════════════

DEFAULT_TICKERS = [
    # 半導體
    "2330", "2454", "2303", "2308", "3711",
    # IC 設計
    "6770", "2449", "3034", "4967",
    # 伺服器 / AI
    "2317", "3231", "2382", "6669",
    # 電子製造
    "2354", "2353", "2356",
    # 金融
    "2882", "2881", "2886", "2884",
    # 大型 ETF（流動性基準）
    "0050",
]


# ═════════════════════════════════════════════════════════════════════════════
# 2. argparse 設定
# ═════════════════════════════════════════════════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_research_study",
        description="台股截面因子研究自動化執行腳本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python scripts/run_research_study.py
  python scripts/run_research_study.py --period 3y --universe 80
  python scripts/run_research_study.py --tickers 2330,2454,2317 --lag 5
        """,
    )

    # 資料期間
    p.add_argument(
        "--period", default="2y",
        choices=["1y", "2y", "3y"],
        help="資料抓取期間（預設 2y）",
    )

    # 股票池大小（從 DEFAULT_TICKERS 取前 N 檔）
    p.add_argument(
        "--universe", type=int, default=len(DEFAULT_TICKERS),
        metavar="N",
        help=f"股票池大小，從預設清單取前 N 檔（預設 {len(DEFAULT_TICKERS)}）",
    )

    # 自訂股票代號（逗號分隔）
    p.add_argument(
        "--tickers", default=None,
        metavar="2330,2454,...",
        help="自訂股票代號（逗號分隔），設定後忽略 --universe",
    )

    # 持有天數（IC lag）
    p.add_argument(
        "--lag", type=int, default=1,
        choices=[1, 5, 20],
        help="因子預測持有天數 lag（預設 1 日）",
    )

    # 分組數
    p.add_argument(
        "--quantiles", type=int, default=5,
        metavar="N",
        help="分位組合數量（預設 5 組）",
    )

    # 最小日均量（千股）
    p.add_argument(
        "--min-volume", type=float, default=100.0,
        metavar="K_SHARES",
        help="最小日均量（千股，預設 100）",
    )

    # 輸出目錄
    p.add_argument(
        "--output", default="exports/research_package",
        metavar="DIR",
        help="結果輸出目錄（預設 exports/research_package）",
    )

    # FinMind token
    p.add_argument(
        "--token", default="",
        metavar="TOKEN",
        help="FinMind API Token（選填，免費版可空白）",
    )

    # 乾跑模式（只驗證設定，不執行研究）
    p.add_argument(
        "--dry-run", action="store_true",
        help="乾跑模式：只顯示設定，不實際執行",
    )

    return p


# ═════════════════════════════════════════════════════════════════════════════
# 3. 輔助：進度列印
# ═════════════════════════════════════════════════════════════════════════════

def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _section(title: str):
    print(f"\n{'=' * 60}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'=' * 60}", flush=True)


# ═════════════════════════════════════════════════════════════════════════════
# 4. main()
# ═════════════════════════════════════════════════════════════════════════════

def main():
    # ensure UTF-8 output on Windows (avoids cp950 UnicodeEncodeError)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = _build_parser()
    args = parser.parse_args()

    # ── 解析股票清單 ──────────────────────────────────────────────────────────
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = DEFAULT_TICKERS[: args.universe]

    # ── 顯示執行設定 ──────────────────────────────────────────────────────────
    _section("研究設定")
    _log(f"股票池   : {len(tickers)} 檔 → {', '.join(tickers[:6])}{'...' if len(tickers) > 6 else ''}")
    _log(f"資料期間 : {args.period}")
    _log(f"IC lag   : {args.lag} 日")
    _log(f"分位數   : {args.quantiles}")
    _log(f"最小日均量: {args.min_volume:.0f} 千股")
    _log(f"輸出目錄 : {args.output}")
    _log(f"FinMind  : {'使用 Token' if args.token else '免費版（有速率限制）'}")

    if args.dry_run:
        _log("── 乾跑模式，結束 ──")
        return 0

    # ── 載入 Pipeline（lazy import）──────────────────────────────────────────
    try:
        from modules.research_pipeline import ResearchPipeline
    except ImportError as e:
        print(f"[ERROR] 無法載入 ResearchPipeline：{e}")
        print("請確認從專案根目錄執行，或已執行 pip install -e .")
        return 1

    # ── 初始化 Pipeline ────────────────────────────────────────────────────
    pipeline = ResearchPipeline(
        tickers      = tickers,
        period       = args.period,
        output_dir   = args.output,
        lag          = args.lag,
        n_quantiles  = args.quantiles,
        finmind_token= args.token,
        log_cb       = _log,
    )

    t0 = time.time()

    # ── Step A: 建立股票池 ─────────────────────────────────────────────────
    _section("Step A：建立股票池")
    # TODO: 由 modules/research_pipeline.py 實作
    pipeline.build_universe(min_avg_volume_k=args.min_volume)

    # ── Step B: 計算因子資料 ───────────────────────────────────────────────
    _section("Step B：計算因子面板")
    # TODO: 由 modules/research_pipeline.py 實作
    pipeline.prepare_factor_data()

    # ── Step C: 截面 IC 分析 ───────────────────────────────────────────────
    _section("Step C：截面 IC 分析")
    # TODO: 由 modules/research_pipeline.py 實作
    pipeline.run_ic_analysis()

    # ── Step D: 分位組合分析 ───────────────────────────────────────────────
    _section("Step D：分位組合分析")
    # TODO: 由 modules/research_pipeline.py 實作
    pipeline.run_factor_portfolio()

    # ── Step E: 匯出研究套件 ───────────────────────────────────────────────
    _section("Step E：匯出研究套件")
    # TODO: 由 modules/research_pipeline.py 實作
    export_path = pipeline.export_research_package()

    # ── Step F: 研究摘要 ───────────────────────────────────────────────────
    _section("Step F：研究摘要")
    # TODO: 由 modules/research_pipeline.py 實作
    summary = pipeline.generate_research_summary()

    # ── 顯示最終摘要 ───────────────────────────────────────────────────────
    elapsed = time.time() - t0
    _section("研究完成")
    _log(f"耗時     : {elapsed:.1f} 秒")
    _log(f"輸出目錄 : {export_path}")
    _log(f"最佳因子 : {summary.get('best_factor', 'N/A')}  "
         f"IC={summary.get('best_ic', 0):.4f}  "
         f"ICIR={summary.get('best_icir', 0):.3f}")
    _log(f"L/S Sharpe: {summary.get('long_short_sharpe', 0):.3f}")

    print("\n研究報告資料已產生，可匯入 docs/research_proposal.md 或 Page 14 研究報告。")
    return 0


# ═════════════════════════════════════════════════════════════════════════════
# 5. 入口
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(main())
