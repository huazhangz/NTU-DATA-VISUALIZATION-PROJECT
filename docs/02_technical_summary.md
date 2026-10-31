# 文档 2：初步研究与分析技术摘要

范围：CDC PLACES County Data (GIS Friendly Format), 2025 release（`i46a-9kgh`），从清洗到全部 preliminary analysis 的技术记录。数值以 `02_analysis/outputs/` 中的当前输出为准（2026-10-31 复查后重新生成）。

## 1. 数据与输入完整性

- 原始表 3,143 × 167，SHA-256 `a47cad3a…5ef`。清洗表 3,143 × 332，SHA-256 `58a324b2…f201`。
- 清洗规则 R00–R13：源值逐格保留为文本（R01）；不删行（R02）；空白不插补（R04）；FIPS 不转整数（R05）；不缩尾（R07）。仅追加 `derived__*` 列（R09–R13）：
  - 区间上下限（160 列）；
  - WKT 中心点经纬度；
  - 原始行号；
  - 州内短名重名标记（12 个 FIPS）；
  - FIPS `35013` 的显示名修正。
- 独立校验：24 PASS / 1 WARNING（V26，Loving County `48301` 无行）/ 1 NOT TESTED（V23，外部字节对照，已按范围关闭）。
- EDA 输入验收 16 PASS / 0 FAIL。所有分析脚本运行前都核对输入哈希，与验收记录不符即停止。
- 发布缺口：
  - 2023 指标在 KY、PA 全部空白；
  - 7 项 HRSN 指标另在 CO、FL、OR、SD、TN、TX、VT、WA、WY 空白（2,299 县有值）；
  - 5 项 2022 指标（COLON_SCREEN、DENTAL、MAMMOUSE、SLEEP、TEETHLOST）3,143 县全有值。
  - 缺失一律保留为 NA。
- 估计性质：以 BRFSS 调查和人口普查人口数据为基础的多层次回归与后分层（MRP）小域模型估计（见清洗报告 `01_source_provenance.md`）。每个点估计附 95% 区间。

## 2. 核心 EDA（DIABETES、OBESITY、LPA；2023，age-adjusted）

各项 n = 2,956；KY、PA 缺 187 行（5.95%）。

| 指标 | 中位数 | IQR | P10–P90 | 范围 |
| --- | ---: | --- | --- | --- |
| Diabetes | 10.7% | 9.5–12.5 | 8.7–14.2 | 6.0–23.8 |
| Obesity | 38.2% | 35.1–40.6 | 31.4–43.0 | 17.1–54.0 |
| Physical inactivity | 26.5% | 23.4–30.5 | 20.5–34.3 | 12.2–48.9 |

- 州级结果用县级等权中位数，不按人口加权。
- 尾部县只作诊断性复核，不剔除。

## 3. 核心关系分析

| 配对（n = 2,956） | Pearson r | Spearman ρ | OLS R² |
| --- | ---: | ---: | ---: |
| Diabetes × Obesity | 0.683 | 0.653 | 0.467 |
| Diabetes × Inactivity | 0.873 | 0.863 | 0.763 |
| Obesity × Inactivity | 0.746 | 0.717 | 0.556 |

- **趋势线：** 交互散点图使用 LOWESS（tricube 核，span 0.25，局部线性，无稳健迭代），只作描述。
- **联合高值：**
  - 定义：三项均 ≥ 各自 P75，阈值为 12.5%、40.6%、30.5%，用 `≥` 包含并列值；
  - 由于并列值，各项实际达标比例为 25.1%–25.5%；
  - 计数：0 项 1,788，1 项 471，2 项 320，3 项 377（12.75%）；
  - 独立性下的期望比例为三项达标比例之积，约 1.6%（≈ 48 县），观测值约为期望的 7.9 倍；
  - 377 县中 89.4% 位于 Census South。

## 4. 扩展分析（全部 40 项）

### 4.1 指标间共变

- **方法：**
  - 35 项 2023 指标两两计算 Spearman ρ，样本为两两完整县（pairwise complete），最少 500 县；
  - HRSN 配对 n = 2,299，其余 n = 2,956，两类 ρ 不在同一样本上，不宜精细比较；
  - 2022 指标不参与相关，避免混合年份。
- **595 对的强度分布（|ρ| 阈值 0.7 / 0.4 / 0.2）：** 强 236，中等 225，弱 78，几乎无关 56。
  - 强正相关 234 对；
  - ρ ≤ −0.4 的有 48 对，主要涉及 BINGE、CANCER、CHOLSCREEN。
- **与核心指标最相关：**
  - Diabetes：GHLTH 0.92，MOBILITY 0.92，SELFCARE 0.91，VISION 0.91，FOODINSECU 0.91；
  - Inactivity：MOBILITY 0.89，GHLTH 0.87，DIABETES 0.86；
  - Obesity：LPA 0.72，CSMOKING 0.71，BPHIGH 0.70。
- **可靠性检查：**
  - 最强配对为 VISION × SELFCARE（ρ = 0.98）；
  - 两列已与原始 CSV 逐格核对一致（脚本内自动断言）；
  - 在 38 个至少有 20 县的州内分别计算，州内 ρ 中位数 0.99，最低 0.95；
  - 解读：概念不同的指标在几乎所有州内都近乎完全同步，与 MRP 模型共享的个体与县级协变量（如年龄、性别、种族、教育及县级贫困）一致；
  - 结论：|ρ| ≥ 0.9 视为主要由模型结构造成，图中以 † 标注，不作实质解读。

### 4.2 州级轮廓

- **方法：** 州内县级中位数减全国县级中位数（百分点），对 39 项指标计算。BPMED 只保留在表中，见 §4.3。
- **例：**

  | 指标 | 偏高的州 | 偏低的州 |
  | --- | --- | --- |
  | Diabetes | MS +3.7，LA +3.6 | VT −3.5 |
  | Depression | WV +8.4，TN +7.3 | NJ −7.6 |
  | Food insecurity | MS +10.8，LA +10.8 | RI −6.1 |
  | Binge drinking | ND +5.1 | UT −5.3 |
  | Routine checkup | RI +7.8 | NM −9.4 |

- **限制：** 小样本州（DC 1 县、DE 3 县、HI 5 县）方差大。

### 4.3 方法检查：粗率 − 年龄调整率

按 2000 年美国标准人口进行直接标准化后，比较各县粗率与调整率之差的中位数：

- **差值为正：** 年龄梯度强的慢性病，包括 HIGHCHOL +6.3、ARTHRITIS +5.3、BPHIGH +5.3。
- **差值为负：** 年轻人中较高的指标，包括 BINGE −2.1、MHLTH −1.5、LONELINESS −1.5。
- **核心指标：** DIABETES +2.5，LPA +1.5，OBESITY −0.1。

由此确认：县间比较必须使用 age-adjusted 值。BPMED 的中位差为 +20.0（以高血压患者为分母，年龄标准化效应大），因此排除在图表之外。

## 5. 复查与修正记录（2026-10-31）

| 问题 | 影响 | 处理 |
| --- | --- | --- |
| `basic_eda.py` 州中位数用不稳定排序，并列值顺序随运行变化；CSV 含浮点尾差（如 8.149999…） | 输出不可复现，数值不变 | 改为 mergesort 并以 `StateAbbr` 作次级键，结果 round(2)；连续两次运行逐字节一致 |
| `basic_eda.py` 覆盖率文字（2,956 / 187 / 5.95%）写死 | 数据变化时报告会失真 | 改为由数据计算 |
| `relationship_regressions.csv` 中糖尿病配对把糖尿病当作自变量，与散点图和报告方向相反 | 斜率与截距难以解读 | 糖尿病一律作因变量；R² 不变 |
| 独立性期望写作 1.56%（0.25³），未计入并列值 | 偏差很小 | 改为按实际达标比例相乘，约 1.6% |
| 三张核心交互图把所有地名后缀为 "County"，例如 "Orleans County"、"Harrisonburg County" | 路易斯安那 parish、弗吉尼亚独立市、阿拉斯加 borough、康涅狄格 planning region 名称错误 | 改用 Census 2023 官方全名（`places_to_2023_gazetteer.csv` 的 `census_name`） |
| LONELINESS 曾标为 "Social isolation" | 违反交接约定 | 统一标为 Loneliness |
| 扩展视图过度技术化：35×35 聚类热力图 + 树状图 + hexbin；年龄差山脊图 + 合成 z 分数指数 | 对受众信息量低，合成指数难以解释 | 删除这两个视图与 UPGMA 聚类、县级年龄差指数；改为“相关指标”条形图 + 散点图；年龄调整只在本文档 §4.3 说明 |
| 核心视图术语：LOWESS、R²、upper-quartile、quantile classes、95% CI | 受众难以理解 | 改为 smoothed trend、strength 用语、top 25%、5 个等量颜色组、likely range |

## 6. 最终可视化（5 个）

| 视图 | 编码 | 数据 |
| --- | --- | --- |
| `interactive_county_map/` | 分级填色地图，按五分位分 5 组，ColorBrewer Blues | 3 项核心指标，含 95% 区间 |
| `interactive_relationship/` | 散点图 + LOWESS，可按 Census region 筛选 | 2,956 县 |
| `interactive_overlap/` | 有序类别地图（0–3 项）+ 计数条形图 | P75 阈值 |
| `interactive_related_measures/` | 排序发散条形图（ρ），点击后显示配对散点图 | 34 项 2023 指标（不含 BPMED） |
| `interactive_state_tiles/` | 等面积州瓦片地图，发散色阶（每项指标按自身最大偏差对称缩放），联动排序点图 | 39 项指标 × 51 州 |

所有交互页面都提供 hover/focus 提示框和表格视图；扩展视图另支持亮/暗主题。缺失值用灰色或斜线显示，从不显示为 0。

## 7. 复现与测试

```bash
python3 02_analysis/validate_eda_input.py
python3 02_analysis/basic_eda.py
python3 02_analysis/relationship_analysis.py
python3 02_analysis/extended_analysis.py
python3 03_visualisations/final/build_county_map.py
python3 03_visualisations/final/build_relationship_scatter.py
python3 03_visualisations/final/build_overlap_map.py
python3 03_visualisations/final/build_extended_views.py
PYTHONPATH=scripts python3 -m pytest tests -q
```

- **pytest：** 10 passed。原有清洗测试 4 项，新增 6 项，覆盖：
  - 强度分级；
  - 输出形状与对称性；
  - 缺失保持为 NA；
  - 回归方向；
  - 排序确定性；
  - 页面数据为严格 JSON；
  - 首页链接完整；
  - 县名后缀。
- **浏览器测试：** Playwright/Chromium，1440×1000，亮、暗两种模式，共 12 次页面加载，另加 390 px 移动端。控制台零错误，无横向溢出，交互断言全部通过。

## 8. 解读边界

- 县级生态描述，不推断个体风险，不作因果推断。
- 模型估计之间的相关被共享协变量抬高。
- 未做空间自相关校正。
- 州中位数不是州患病率。
- 2022 与 2023 指标不构成时间序列。
