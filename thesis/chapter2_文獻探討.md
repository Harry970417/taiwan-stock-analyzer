第二章　文獻探討



2.1　因子投資理論發展



現代投資組合理論（Modern Portfolio Theory）的奠基工作可追溯至 Markowitz（1952）的開創性研究。Markowitz 以均值與變異數作為報酬與風險的雙重度量，建立投資人在效率前緣（Efficient Frontier）上進行最佳化選擇的理論框架，確立了分散投資（diversification）的學術基礎。在此基礎上，Sharpe（1964）提出資本資產定價模型（Capital Asset Pricing Model, CAPM），以單一市場因子解釋個別資產的期望報酬，並導出 Beta 係數作為系統性風險的標準度量。然而 CAPM 的核心命題——市場因子是唯一的定價因子——在隨後數十年間遭受大量實證挑戰，促使研究者引入額外的定價因子以解釋 CAPM 殘差中的截面報酬異常，進而開啟多因子資產定價模型的研究時代。

Fama 與 French（1993）在美國股市的大規模截面研究中，發現規模效應（size effect）與帳面市值比效應（book-to-market effect）無法被 CAPM 充分解釋，進而提出三因子模型，以市場超額報酬（Mkt-Rf）、規模因子（SMB）及帳面市值比因子（HML）三個共同風險因子解釋截面報酬差異。Carhart（1997）在研究共同基金績效持續性時，引入過去 12 個月報酬率作為動量因子（MOM），建立四因子模型，指出基金績效差異中有相當部分可由對動量因子的暴露程度（factor loading）解釋。此後，Fama 與 French（2015）進一步擴充為五因子模型，加入獲利因子（RMW）與投資因子（CMA），以系統性解釋獲利異常現象。

上述理論演進確立了「因子投資」作為現代量化資產管理的核心方法論。然而，此研究脈絡同時引發一個尚未獲得充分解答的後設問題：在因子數量持續擴張的當代，如何有效區分具真實定價意涵的因子與數據挖掘產物，成為實證資產定價的核心方法論挑戰，並直接促成了 IC 框架在機構投資實踐中的廣泛採用。



2.2　資訊係數（IC）理論與因子有效性評估



因子有效性的度量問題，在學術研究層面由 Grinold（1989）的基礎性貢獻提出系統性解答。Grinold 以資訊比率（Information Ratio, IR）作為主動投資組合管理效益的核心衡量，並將其分解為資訊係數（Information Coefficient, IC）與廣度（Breadth）的乘積，即著名的主動管理基本定律（Fundamental Law of Active Management）：IR = IC × √Breadth。其中，IC 定義為因子預測值排名與實現報酬排名之間的 Spearman等級相關係數，衡量因子在截面維度上對個股相對報酬排序的預測一致性；廣度則代表獨立的截面預測次數。此框架確立了截面 IC 作為因子品質（factor quality）最直觀度量的學術地位，為機構投資人提供了脫離具體模型假設的因子評估工具。

Grinold 與 Kahn（1999）進一步指出，在實際應用中，|IC| > 0.05 對應良好信號品質，|IC| > 0.03 即具備實際可利用的資訊含量，而 ICIR（IC 均值除以 IC 標準差）則衡量因子信號的時序一致性，優於單純比較 IC 均值。此框架在北美及歐洲機構投資人的量化組合管理實踐中獲得廣泛採用，成為因子篩選的主流標準。

然而，IC 框架作為因子篩選工具存在若干方法論限制，其中最突出者為多重比較問題（multiple testing problem）。Harvey、Liu 與 Zhu（2016）的元分析系統性檢視學術文獻中超過 316 個「統計顯著」因子，指出在未進行多重比較校正的條件下，傳統 t 統計量 > 2.0 的顯著性門檻已無法有效區分真實因子溢酬與數據挖掘產物，建議將發現新因子的顯著性門檻提高至 t > 3.0。此研究——俗稱「Factor Zoo」問題——對量化投資研究方法論產生了深遠影響，促使研究者在 IC 統計顯著性之外，尋求更為穩健的因子有效性評估標準。本研究正是在此脈絡下，同時引入 IC 統計量、ICIR、Long-Short Sharpe Ratio（Sharpe, 1966）與最大回撤四個維度作為因子評估架構，嘗試提供比單一 IC 顯著性篩選更為完整的評估框架。



2.3　盈餘公告後股價漂移（PEAD）與盈餘動能研究



盈餘公告後股價漂移（Post-Earnings Announcement Drift, PEAD）是金融學術文獻中記錄最為完整、歷時最為長久的市場異常現象之一。Ball 與 Brown（1968）的開創性研究首次以系統性統計方法記錄了盈餘意外（earnings surprise）與公告後股價反應之間的持續性關係，發現即便在盈餘公告日後數個月，具有正面盈餘意外的股票仍持續呈現超額正報酬，而負面盈餘意外者則持續呈現超額負報酬，此發現對半強式效率市場假說提出了直接的實證挑戰。

在度量工具層面，Latane 與 Jones（1979）提出標準化預期盈餘意外（Standardized Unexpected Earnings, SUE）指標，以當期 EPS 偏離歷史均值的幅度除以歷史標準差衡量盈餘動能，確認 SUE 高分位股票在公告後 60 個交易日內仍能維持正的截面超額報酬，並建立了盈餘成長率作為截面選股因子的方法論基礎。Bernard 與 Thomas（1989）進一步以 1974 至 1986 年逾 84,000 個公司季度觀測值對 PEAD 現象進行系統性分析，確認公告後 60 日的持有期間內，PEAD 策略的累積超額報酬達到統計顯著且在經濟意義上顯著的量值，且此報酬無法以風險溢酬或市場微結構效應完整解釋，研究者普遍以投資人對盈餘資訊的「低度反應」（underreaction）作為機制詮釋。

上述文獻對本研究具有直接的方法論意涵。EPS 年增率因子在先導實證階段呈現「截面 IC 不顯著但組合績效優異」的矛盾現象，與 PEAD 文獻的核心論點高度一致：若 EPS 成長信號的截面預測力高度集中於盈餘公告前後的特定時窗，則基於全樣本的無條件 IC 計算將因大量低預測力的非公告日觀測值而稀釋信號強度，導致 IC t 統計量系統性低估因子真實的截面排序能力（本研究先導階段 EPS 因子有效截面數僅 197 日，相較技術面因子之 446 至 474 日顯著偏低）。此觀察為 H2 提供了直接的文獻依據，並引出「事件條件 IC」（Event-Conditional IC）作為未來研究的方法論延伸方向。



2.4　IC 統計量與組合績效背離：套利限制與執行障礙



儘管 Grinold & Kahn（1999）框架確立了 IC 作為因子有效性的標準度量，近年來的實證研究逐漸揭示，IC 統計顯著性與可實現的組合超額報酬之間並非必然正向對應。此乖離的根源，學術文獻主要從交易成本、市場衝擊與套利限制三個維度加以解釋。

在交易成本層面，Chen 與 Velikov（2021）對文獻中廣泛記錄的截面報酬異常進行系統性重新評估，以逐筆交易資料估計實際換手成本後，發現大量被視為「已記錄實證的因子溢酬」在扣除實際交易成本後，其統計顯著性大幅衰減乃至消失。高 IC 的因子往往要求頻繁的截面重新排序，伴隨高換手率，在市場衝擊顯著的中小型股票上尤為明顯。在套利限制層面，Shleifer 與 Vishny（1997）的理論模型指出，即便市場存在可識別的錯誤定價，噪音交易者風險（noise trader risk）、資金限制與委託-代理問題，可能使理性套利者無法充分利用統計顯著的因子信號，導致錯誤定價持續存在甚至擴大。Miller（1977）從資訊異質性角度進一步指出，當投資人意見分歧且放空受到制度性限制時，市場價格將系統性反映樂觀者的估值，悲觀者的資訊無法有效進入價格，使得做空信號即便具備統計顯著的截面 IC，亦可能難以轉化為可執行的空頭報酬。在台灣市場的制度環境下，此套利限制問題尤為突出：台股融券機制相較於美國存在較高的執行門檻，包含強制回補機制、較高融券利率及有限的可借券量，使需要在 Q1 分位建立空頭部位的 Long-Short 策略面臨顯著的單邊執行障礙。

本研究先導階段所觀察到的 MACD 信號因子現象——IC 統計顯著（t = −3.31）但 Long-Short Sharpe 為負（−0.37）——正是此類套利障礙的典型體現，構成了本研究所提出之 IC-Portfolio Divergence 概念的核心實證基礎，並為 H1 與 H3 提供了直接的理論依據。



2.5　法人籌碼研究脈絡與台灣市場特殊性



機構投資人交易行為作為截面選股信號的研究，早期由 Grinblatt 與 Titman（1989）以共同基金季度持倉調整資料開展系統性分析，發現機構買入行為能對未來報酬具有一定程度的正向預測性，顯示機構投資人的選股能力整體優於隨機選擇。Nofsinger 與 Sias（1999）進一步記錄機構投資人的群聚行為（institutional herding），指出此類群聚行為與同期股票報酬顯著正相關，但亦存在過度追隨動能而導致事後反轉的風險，顯示機構信號的預測方向與持續性因法人類型與市場結構而異。

台灣市場的研究脈絡提供了更為直接的實證基礎。Lin 與 Shiu（2003）以台灣外資投資行為進行系統性研究，發現外資淨買超對後續 1 至 5 個交易日的截面報酬具有統計顯著的正向預測能力，但此預測力在月頻層次顯著衰減，顯示外資信號的預測期限主要集中於短期，可能反映機構的資訊優勢在市場快速定價後即被消化。Barber、Lee、Liu 與 Odean（2009）以台灣市場全體投資人逐筆交易資料進行大規模研究，發現台灣散戶投資人的交易損失系統性轉移至機構投資人，有力支持了「台灣法人具有系統性資訊優勢」的研究前提。

然而，現有台灣法人籌碼研究存在兩項方法論限制：其一，多數研究採用事件研究或時間序列框架，而非截面因子分析，難以回答法人籌碼信號是否能在股票宇宙中系統性排序個股相對報酬的問題；其二，針對投信與自營商籌碼信號的截面預測力研究相對稀缺，三大法人之間的信號品質差異尚未獲得基於 IC 框架的嚴格比較。此研究缺口揭示了台灣市場在機構投資行為研究上的方法論侷限，亦為未來研究提供了截面 IC 框架的擴展方向。

為系統性呈現本研究與既有代表性研究之間的方法論定位差異，下表就六項關鍵研究（含本研究）之市場範圍、研究方法、主要發現與方法論限制進行橫向比較。



表 2-1　本研究與既有代表性研究之方法論定位比較



上述比較清晰揭示本研究在方法論定位上的三項差異化：（一）採四維度並列評估取代單一 IC 顯著性篩選；（二）以台灣本土資料直接驗證 IC 與 Portfolio 績效之對應關係；（三）在既有台灣市場研究尚未採用截面 IC 框架系統性比較多類型因子的空白下，提供首次四維度評估框架的實證應用。



2.6　文獻缺口與本研究定位



綜合前述文獻脈絡，本研究識別三項具體研究缺口，作為本研究學術定位的直接依據。



Gap 1：因子有效性評估維度不足

現有截面因子研究普遍存在評估維度單一化的問題。Fama 與 French（1993）及 Carhart（1997）等因子模型文獻，主要以五分位組合的歷史超額報酬驗證因子溢酬的存在性，評估核心為樣本內統計顯著性，鮮少同時報告組合的下方風險（Downside Risk）指標如最大回撤（Maximum Drawdown）。另一方面，以 IC 框架為基礎的機構量化研究（Grinold & Kahn, 1999）則主要關注 IC 均值與 ICIR 的統計顯著性，而未直接驗證 IC 是否能轉化為可實現的投資組合超額報酬。Harvey 等人（2016）雖指出因子篩選的多重比較問題，並提高了 IC 顯著性的統計門檻，但其研究焦點仍在因子的統計有效性層面，並未深入探討 IC 統計量與實際組合 Sharpe Ratio 之間可能存在的系統性背離。

此種評估維度的分裂，導致現有文獻無法有效回答以下問題：一個具有高 IC 統計顯著性的因子，在扣除交易成本、考量台灣市場放空限制後，能否在實際組合層面維持正的 Sharpe Ratio？反之，一個 IC 統計量未達顯著門檻的因子，是否可能因信號稀疏性（event-driven dilution）而被 IC 框架低估，從而在組合績效層面反而優於「統計顯著」因子？本研究透過同時計算 IC 均值、ICIR、t 統計量、Long-Short 年化 Sharpe Ratio 與最大回撤五項指標，建立因子有效性的四維度並列評估框架，以填補此一方法論缺口。



Gap 2：IC 與組合績效關聯性之直接實證缺乏

Grinold（1989）的基本定律從理論層面建立了 IC 與資訊比率（IR）之間的正向關係，隱含 IC 較高的因子應能產生較高的組合超額報酬。然而，此理論命題有若干重要的成立前提，包括：信號為線性預測、截面覆蓋率充分、放空可無摩擦執行，以及換手成本可忽略。在實際市場條件下，上述前提往往無法同時成立。Chen 與 Velikov（2021）已從交易成本層面提供了部分反例，而 Shleifer 與 Vishny（1997）的套利限制理論則提供了放空障礙角度的機制解釋。儘管如此，現有文獻對於「IC 統計顯著性是否為組合正報酬的充分條件」這一命題，迄今尚缺乏在單一市場、相同樣本期間對多個因子同時進行直接比較的系統性實證研究。

本研究先導分析所觀察到的 IC-Portfolio Divergence 現象——MACD 信號因子 IC 最顯著（t = −3.31）但 Sharpe 為負；EPS 年增率 IC 不顯著（t = 1.85）但 Sharpe 高達 3.08——提供了 IC 與組合績效出現系統性背離的直接實證案例。此現象在現有文獻中尚未獲得針對台灣市場的系統性記錄與解釋，亦未有研究從 PEAD 信號稀疏性（event-conditional IC dilution）與套利限制（short-sale constraints）的複合機制角度，對相同樣本中不同因子類型的 IC-Sharpe 背離程度進行橫向量化比較。此為本研究 H1 與 H3 的核心研究動機。



Gap 3：台灣市場截面因子有效性直接實證缺乏

現有台灣股票市場的量化研究，主要以時間序列框架驗證外資或機構投資人的短期預測能力（Lin & Shiu, 2003），抑或以事件研究方法檢視特定企業事件後的股價反應，而鮮少從截面 IC 角度系統性比較多類型因子（技術面、基本面）在相同樣本期間、相同方法論框架下的預測能力差異。在此研究空白下，本研究所提出的四維度並列評估框架——IC 均值、ICIR、Long-Short Sharpe Ratio、最大回撤——尚未在台灣市場的本土化實證中獲得系統性驗證，構成本研究 H1、H2、H3 的共同研究基礎。



2.7　概念性研究框架（Conceptual Framework）



本研究的理論架構建立於以下核心命題：因子信號能否轉化為可實現的投資組合超額報酬，取決於信號在截面 IC 層次的統計有效性，以及若干將統計有效性轉化為組合績效的傳導機制是否暢通。以下以概念模型圖呈現本研究的分析框架：



圖 2-1　本研究概念性研究框架（Conceptual Framework）

┌──────────────────────────────────────────────────────────────┐
│        本研究概念性研究框架 (Conceptual Framework)             │
├──────────────────────────────────────────────────────────────┤
│ 因子信號 (Factor Signal)                                      │
│ ┌───────────────────────────┐  ┌──────────────────────────┐  │
│ │        技術面因子           │  │        基本面因子           │  │
│ │  MACD / RSI / 動量 / 量比  │  │  EPS YoY / 月營收 YoY    │  │
│ │                           │  │  ROE / EPS 年增率        │  │
│ └──────────────┬────────────┘  └─────────────┬────────────┘  │
│                └───────────────┬──────────────┘              │
│                                ▼                             │
│           截面 IC 分析 (Cross-Sectional IC)                   │
│      ┌────────────────────────────────────────────┐          │
│      │ IC 均值（方向性）│ ICIR（一致性）│ t-stat（顯著性）│          │
│      └────────────────────────────────────────────┘          │
│                     │                                        │
│       ┌─────────────┴─────────────┐                          │
│       │  傳導機制 (Transmission)   │                          │
│  暢通 ▼                      受阻 ▼                           │
│ ┌──────────────┐  ┌──────────────────────────────────┐       │
│ │信號線性・覆蓋廣│  │① 套利限制（台股放空障礙）           │       │
│ │執行成本低     │  │② 交易成本（高換手率）               │       │
│ │無前瞻偏誤     │  │③ 信號稀疏（事件驅動稀釋）           │       │
│ └──────┬───────┘  └──────────────────┬───────────────┘       │
│        ▼                             ▼                       │
│ ┌──────────────┐  ┌──────────────────────────────────┐       │
│ │ IC → 組合績效 │  │  IC → 組合績效「背離」              │       │
│ │ Sharpe 正相關 │  │  IC-Portfolio Divergence          │       │
│ └──────┬───────┘  └──────────────────┬───────────────┘       │
│        └──────────────┬──────────────┘                       │
│                       ▼                                      │
│           五分位 Long-Short 組合績效                           │
│      ┌──────────────────────────────────────────┐            │
│      │  年化 Sharpe  │  最大回撤  │  年化報酬     │            │
│      └──────────────────────────────────────────┘            │
│                                                              │
│ 本研究驗證命題：                                               │
│  H1: IC 統計量高者，Sharpe 是否必然較高？                       │
│  H2: 事件驅動型因子（EPS）的 IC 是否被系統性低估？               │
│  H3: 放空障礙是否阻斷 IC 向組合績效的傳導？                      │
└──────────────────────────────────────────────────────────────┘



上述概念框架的核心論點如下：因子信號在截面 IC 層次的統計顯著性，是組合正報酬的必要但非充分條件。當傳導機制暢通時（信號線性、覆蓋率高、執行成本低），IC 統計顯著性與組合 Sharpe 之間應呈正向對應，此為 Grinold（1989）基本定律的隱含預設。然而，當傳導機制受到套利限制（台股放空障礙）、高換手率（交易成本侵蝕）或事件驅動型信號稀疏性（PEAD 信號被日頻 IC 稀釋）三種機制阻斷時，IC 統計顯著性將無法線性轉化為組合超額報酬，即出現 IC-Portfolio Divergence 現象。本研究的核心貢獻，在於以台灣市場的直接實證資料，對上述傳導機制的暢通程度與阻斷條件進行首次系統性量化分析，並據此提出一套在 IC 統計評估之外更為完整的因子有效性評估框架。





本章參考文獻



Ball, R., & Brown, P. (1968). An empirical evaluation of accounting income numbers. Journal of Accounting Research, 6(2), 159–178. https://doi.org/10.2307/2490232



Barber, B. M., Lee, Y.-T., Liu, Y.-J., & Odean, T. (2009). Just how much do individual investors lose by trading? Review of Financial Studies, 22(2), 609–632. https://doi.org/10.1093/rfs/hhn046



Bernard, V. L., & Thomas, J. K. (1989). Post-earnings-announcement drift: Delayed price response or risk premium? Journal of Accounting and Economics, 11(2–3), 305–340. https://doi.org/10.1016/0165-4101(89)90018-9



Carhart, M. M. (1997). On persistence in mutual fund performance. Journal of Finance, 52(1), 57–82. https://doi.org/10.1111/j.1540-6261.1997.tb03808.x



Chen, A. Y., & Velikov, M. (2021). Zeroing in on the expected returns of anomalies. Journal of Financial and Quantitative Analysis, 58(3), 968–1004. https://doi.org/10.1017/S002210902100042X



Fama, E. F., & French, K. R. (1993). Common risk factors in the returns on stocks and bonds. Journal of Financial Economics, 33(1), 3–56. https://doi.org/10.1016/0304-405X(93)90023-5



Fama, E. F., & French, K. R. (2015). A five-factor asset pricing model. Journal of Financial Economics, 116(1), 1–22. https://doi.org/10.1016/j.jfineco.2014.10.010



Grinblatt, M., & Titman, S. (1989). Mutual fund performance: An analysis of quarterly portfolio holdings. Journal of Business, 62(3), 393–416. https://doi.org/10.1086/296468



Grinold, R. C. (1989). The fundamental law of active management. Journal of Portfolio Management, 15(3), 30–37. https://doi.org/10.3905/jpm.1989.409211



Grinold, R. C., & Kahn, R. N. (1999). Active portfolio management: A quantitative approach for producing superior returns and controlling risk (2nd ed.). McGraw-Hill.



Harvey, C. R., Liu, Y., & Zhu, H. (2016). … and the cross-section of expected returns. Review of Financial Studies, 29(1), 5–68. https://doi.org/10.1093/rfs/hhv059



Latane, H. A., & Jones, C. P. (1979). Standardized unexpected earnings—1971–77. Journal of Finance, 34(3), 717–724. https://doi.org/10.1111/j.1540-6261.1979.tb02137.x



Lin, A. Y., & Shiu, Y.-M. (2003). Foreign ownership in the Taiwan stock market—An empirical analysis. Journal of Multinational Financial Management, 13(1), 19–41. https://doi.org/10.1016/S1042-444X(02)00020-4



Markowitz, H. (1952). Portfolio selection. Journal of Finance, 7(1), 77–91. https://doi.org/10.1111/j.1540-6261.1952.tb01525.x



Miller, E. M. (1977). Risk, uncertainty, and divergence of opinion. Journal of Finance, 32(4), 1151–1168. https://doi.org/10.1111/j.1540-6261.1977.tb03317.x



Nofsinger, J. R., & Sias, R. W. (1999). Herding and feedback trading by institutional and individual investors. Journal of Finance, 54(6), 2263–2295. https://doi.org/10.1111/0022-1082.00188



Sharpe, W. F. (1964). Capital asset prices: A theory of market equilibrium under conditions of risk. Journal of Finance, 19(3), 425–442. https://doi.org/10.1111/j.1540-6261.1964.tb02865.x



Sharpe, W. F. (1966). Mutual fund performance. Journal of Business, 39(1), 119–138. https://doi.org/10.1086/294846



Shleifer, A., & Vishny, R. W. (1997). The limits of arbitrage. Journal of Finance, 52(1), 35–55. https://doi.org/10.1111/j.1540-6261.1997.tb03807.x

