# NeuroOntoGen 产品需求文档（PRD）

> 版本：v0.1  
> 状态：研发基准草案  
> 定位：神经符号级本体自动构建、校验与自修复底座

---

## 1. 产品概述与核心价值

### 1.1 背景与定位

在企业级数据治理、医疗临床标准对齐、金融风险控制以及安全 Agent 编排等场景下，知识图谱与本体（Ontology）是维护业务逻辑一致性与可解释性的核心底座。

然而，纯大模型（LLM）构建知识图谱极易因概率预测机制产生以下致命问题：

- 语义幻觉；
- 关系不一致；
- 类 / 子类 / 实例混淆；
- 继承关系退化；
- Prompt 改写后输出拓扑剧烈抖动。

**NeuroOntoGen** 定位为一个开箱即用的 **神经符号级本体自动构建与校验底座**。它将大语言模型的自然语言理解能力与经典语义网标准深度融合，包括：

- OWL；
- SWRL；
- SHACL；
- LinkML；
- JSON Schema；
- RDF / Turtle；
- 图数据库。

目标是确保生成的：

- **TBox**：术语箱 / 本体 schema；
- **ABox**：断言箱 / 实例事实；

具备可验证、可修复、可审计的逻辑与结构确定性。

> 注：PRD 原文中提到“100% 的逻辑与结构确定性”。在产品和学术表达中，建议将其降格为“通过符号验证器获得确定性校验结果”，避免绝对化承诺。

### 1.2 核心痛点

#### P1. 不确定性拦截

目标：杜绝 LLM 直接吐出未经验证的“伪三元组”。

要求：

- 所有生成数据必须通过 SHACL 结构验证；
- 所有逻辑关系必须通过 OWL 一致性校验；
- 不合规数据不得入库；
- 不合规时自动启动 LLM 自修复闭环。

#### P2. 业务演进滞后

目标：让业务专家能够低成本维护领域模型。

要求：

- 使用 LinkML YAML 表达业务模型；
- 自动派生 JSON Schema、SHACL Shapes、OWL / Turtle；
- 减少手工维护多套 schema 的成本。

#### P3. Prompt 脆性与敏感性

目标：避免本体结构依赖 prompt 字面形式。

要求：

- 用代码护栏（Code-enforced Guardrails）替代自然语言约束；
- 引入提示词解耦测试；
- 对同义但句法不同的 prompt 进行交叉鲁棒性评测。

#### P4. 冷启动概念缺失

目标：在陌生领域没有 TBox 先验时，动态发现候选概念结构。

要求：

- 使用 SpaCy 抽取术语；
- 使用 sentence-transformers 构建向量；
- 使用 Affinity Propagation 聚类自动发现类目数量；
- 使用 LLM 对聚类簇命名、合并、抽象并生成 TBox 草案。

### 1.3 用户群体与典型场景

#### 用户群体 A：知识工程师与数据科学家

需求：从海量异构文档中，高质量、FAIR 化、低延迟地提炼领域知识图谱。

典型场景：

- 数据治理；
- 临床术语对齐；
- 金融风控知识建模；
- 工业知识库构建；
- 科研文献 schema discovery。

#### 用户群体 B：企业级 Agent 开发者

需求：用可计算本体图谱对 Agent 行为进行硬约束。

典型场景：

- 工具调用权限控制；
- 对话状态约束；
- 角色权限约束；
- 安全 Agent 编排；
- 非 Prompt 级的物理安全边界。

---

## 2. 系统架构与核心工作流

系统整体采用双回路设计：

1. **正向提取生成回路**：LLM + LinkML / JSON Schema 结构限制；
2. **逆向验证自修复回路**：PySHACL 结构校验 + OWL Reasoner 逻辑纠偏。

### 2.1 神经符号协同构建总览

```text
                               +----------------------------------+
                               |     LinkML YAML TBox 定义         |
                               +----------------------------------+
                                                |
                                                v (编译与派生)
                             +------------------+------------------+
                             |                                     |
                             v                                     v
                  +---------------------+               +---------------------+
                  |   JSON Schema 约束  |               |  SHACL Shapes & OWL |
                  +---------------------+               +---------------------+
                             |                                     |
                             v (R-C-N-S-V-O 提示词)                |
                   +-------------------+                           |
                   |   LLM 柔性提取器  |                           |
                   +-------------------+                           |
                             |                                     |
                             v (ABox JSON)                         |
                   +-------------------+                           |
                   |   rdflib 序列化   |                           |
                   +-------------------+                           |
                             |                                     |
                             +------------------+------------------+
                                                |
                                                v
                               +----------------------------------+
                               |     双重符号裁判系统 Validator    |
                               |    - OWL 一致性检测 HermiT/Pellet |
                               |    - SHACL 结构验证 PySHACL       |
                               +----------------------------------+
                                         /              \
                          不通过: SHACL Violations     通过: 符合约束
                                       /                  \
                                      v                    v
                        +---------------------------+    +-----------------------+
                        |   LLM Agent 自修复闭环    |    |  持久化入图数据库 TTL  |
                        |   Self-Repair Loop        |    +-----------------------+
                        +---------------------------+
```

### 2.2 逆向自修复回路（Self-Repair Loop）

当 PySHACL 探测到 ABox 实体不符合基数、属性范围或格式限制时，触发自修复闭环。

```text
+------------------+      +--------------------+      +---------------------------------+
|   PySHACL 报错   | ---> | 提取错误节点、属性 | ---> | 构建 Diagnostic Prompt          |
| Non-conformance  |      | 与违反约束的原因   |      | 将原 ABox JSON 传入 LLM          |
+------------------+      +--------------------+      +---------------------------------+
                                                                       |
                                                                       v
+------------------+      +--------------------+      +---------------------------------+
|  重新转换为 RDF  | <--- |  LLM 输出修正 JSON | <--- | LLM 根据 SHACL 规范针对性修改   |
|  并进行二次校验  |      |  符合 JSON Schema  |      | 去除幻觉 / 补齐缺失属性          |
+------------------+      +--------------------+      +---------------------------------+
```

闭环原则：

- 修复输入必须包含原始 JSON 片段；
- 修复提示必须包含 `sh:resultMessage`、`sh:focusNode`、`sh:sourceShape`；
- 每轮修复后必须重新进行 JSON Schema、RDF serialization、SHACL validation；
- 默认最多重试 3 次；
- 超过重试次数后进入 Human-in-the-Loop。

---

## 3. 功能性需求与技术实现标准

### F1. TBox 元模型编译引擎（LinkML Generator）

#### 需求描述

系统必须支持以声明式 YAML 文件配置领域模型，并一键派生下游异构格式。

#### 核心功能

- 读取 `.yaml` LinkML Schema 配置；
- 输出用于约束 LLM 的 `.json` / JSON Schema；
- 输出用于 PySHACL 结构校验的 `.shacl.ttl`；
- 输出用于 OWL 逻辑声明的 `.owl` 或 `.ttl`；
- 支持 schema versioning；
- 支持可重复编译，保证同一输入产生稳定产物。

#### 验收标准

- 给定一个最小 LinkML schema，可以生成 JSON Schema、SHACL、OWL/Turtle；
- 生成文件可被对应工具加载；
- 编译命令可在 CLI 与 SDK 中共同调用。

---

### F2. R-C-N-S-V-O 模块化 ABox 提取器

#### 需求描述

提供高鲁棒性的大模型实体与关系抽取管道，将自然语言输入转化为受 JSON Schema 约束的 ABox JSON。

#### Prompt 模块

| 模块 | 名称 | 作用 |
|---|---|---|
| R | Role | 注入本体工程专家角色，限定模型语境。 |
| C | Context | 注入特定物理或业务领域上下文。 |
| N | Normalization | 对数值、单位、异常进行标准量纲转化。 |
| S | Specification | 将硬判定逻辑以 SWRL 或伪代码形式嵌入。 |
| V | Value Block | 使用 Markdown 表格或 key-value 输入文本数据。 |
| O | Output Schema | 绑定 JSON Schema，仅允许输出 Pydantic 兼容 JSON。 |

#### 核心功能

- 支持 structured output / JSON schema response format；
- 拒绝自然语言解释；
- 支持单位归一；
- 支持领域上下文注入；
- 支持规则感知抽取；
- 输出可直接进入 RDF serialization。

#### 验收标准

- 对同一输入文本输出合法 JSON；
- 输出可通过 JSON Schema 校验；
- 输出可被 rdflib 转换为 RDF/Turtle。

---

### F3. 双重符号裁判引擎（OWL Reasoner & PySHACL Validator）

#### 需求描述

对 LLM 提取的 ABox 三元组与属性进行物理拦截，判定结构正确性与深层逻辑相容性。

#### F3.1 OWL 逻辑裁判（OWA）

使用 owlready2 运行 HermiT 或 Pellet 推理机。

核心功能：

- 检查是否触发逻辑冲突；
- 检查互斥类 `disjointWith` 是否被同时命中；
- 支持 `owl:inverseOf` 自动补全隐含三元组；
- 支持 SWRL 规则推理；
- 输出 inconsistent ontology 报告。

示例：

> 若 LLM 将同一实体判定为 `:LivingPerson` 与 `:DeceasedPerson`，而两者声明为互斥类，则 OWL Reasoner 必须拦截并报告 inconsistency。

#### F3.2 SHACL 结构裁判（CWA）

使用 pySHACL 将 ABox 放入封闭世界假设下检查。

核心功能：

- 校验字段类型，例如 string、integer、xsd:date；
- 校验必填字段；
- 校验基数限制，例如恰好 1 个 `hasTaxID`；
- 输出详细错误路径：
  - `FocusNode`；
  - `ResultPath`；
  - `Value`；
  - `SourceShape`；
  - `ResultMessage`。

#### 验收标准

- 能检测至少一种 SHACL violation；
- 能检测至少一种 OWL inconsistency；
- violation 报告可被 F4 自修复控制器解析。

---

### F4. Agent 级自修复闭环（Self-Repair Controller）

#### 需求描述

针对裁判系统抛出的 SHACL 违规报告，由 Agent 执行多轮自动纠错，直至 ABox 数据逻辑与格式收敛，或挂起交给人类专家。

#### 核心功能

- 捕获 pySHACL 输出中的：
  - `sh:resultMessage`；
  - `sh:focusNode`；
  - `sh:sourceShape`；
  - `sh:resultPath`；
- 构造自修复 prompt；
- 将原错误 JSON 片段与具体错误说明发送给 LLM；
- 设置 `max_retries`，默认 3 次；
- 每轮修复后重新进行：
  1. JSON Schema validation；
  2. RDF serialization；
  3. SHACL validation；
  4. 必要时 OWL consistency check；
- 若 3 次仍无法收敛，进入 Human-in-the-Loop。

#### Human-in-the-Loop 行为

- 本地管理后台挂起任务；
- 输出错误报告；
- 可选发送 Slack / Webhook；
- 人类专家可审查原文本、错误 JSON、SHACL 报告与修复历史。

#### 验收标准

- 对缺失必填字段的 ABox，至少能自动修复一次；
- 对不可修复问题，能在指定重试次数后挂起；
- 修复历史可追踪。

---

### F5. 陌生领域 AP 聚类冷启动引擎（Clustering Discovery）

#### 需求描述

在没有 TBox 先验模式的情况下，扫描无结构文本，动态发现隐藏类名与候选层级。

#### 核心功能

- 使用 SpaCy 挖掘名词术语；
- 使用 sentence-transformers 生成向量；
- 使用 scikit-learn Affinity Propagation 聚类；
- 自适应计算聚类数量 K，无需人工硬编码；
- 调用 LLM 审视聚类簇内部成员；
- 生成簇名称、类层级、候选属性；
- 输出结构化 TBox 元模型草案。

#### 验收标准

- 给定一组无 schema 文档，可生成候选术语列表；
- AP 聚类可返回非空簇；
- LLM 可为每个簇生成候选 class 名称；
- 产物可转换为 LinkML draft。

---

### F6. 提示词解耦测试引擎（Anti-Fragility Cross-Prompt Testing）

#### 需求描述

针对 LLM 对 prompt 表观文本过拟合的问题，设计对抗式测试套件，验证本体提取鲁棒性。

#### 核心功能

- 支持定义同义但语法不同的 prompt 模板对；
- 支持方向相反但语义等价的模板，例如：
  - `Is X a subclass of Y?`
  - `Is Y a superclass of X?`
- 对同一数据集进行多 prompt 交叉提取；
- 计算不同模板下输出结果的 F1 相似度；
- 标记脆弱三元组；
- 过滤高度受 prompt 字面影响的候选关系。

#### 验收标准

- 同一输入可在至少两个 prompt 模板下运行；
- 系统输出跨 prompt 一致性分数；
- 低一致性候选三元组可被标记为 unstable。

---

## 4. 非功能性需求

### 4.1 可复现性

- 所有 pipeline 配置必须版本化；
- Benchmark 输入、模型、prompt、schema、输出均可追踪；
- 实验结果可导出为 JSON / CSV / Markdown 表格。

### 4.2 可解释性

每个三元组至少应保留：

- 来源文本 span；
- 生成模型；
- 生成 prompt template；
- validation status；
- repair history；
- confidence / stability score。

### 4.3 可扩展性

系统应支持：

- 新领域 LinkML schema；
- 新 LLM provider；
- 新图数据库 backend；
- 新 benchmark dataset；
- 新 prompt template；
- 新 validator adapter。

### 4.4 安全与治理

- 不合规数据不得入库；
- Prompt 不应成为唯一安全边界；
- 所有写入图数据库的操作应留审计日志；
- 企业部署场景应支持私有化。

---

## 5. MVP 范围建议

### MVP 必做

1. LinkML schema → JSON Schema / SHACL / TTL 编译；
2. R-C-N-S-V-O ABox extraction；
3. JSON Schema validation；
4. RDF / Turtle serialization；
5. PySHACL validation；
6. 最小 self-repair loop；
7. 一个端到端 Jupyter Notebook；
8. 一个 CLI smoke test。

### MVP 暂缓

1. 完整 OWL / HermiT / Pellet 深层推理；
2. SWRL 复杂规则；
3. AP 聚类冷启动；
4. MCP Server；
5. 多图数据库 connector；
6. Slack / Webhook 报警；
7. 企业级管理后台。

暂缓不代表不重要，而是避免第一版范围过大。MVP 应先证明：

> LLM 输出可以被 LinkML/SHACL 硬约束，并在违规时自动修复。

---

## 6. 推荐技术栈

| 层级 | 技术 |
|---|---|
| Schema / TBox | LinkML, OWL, RDF/Turtle |
| LLM Output Constraint | JSON Schema, Pydantic |
| Extraction | OpenAI / Claude / local LLM adapters |
| RDF Serialization | rdflib |
| SHACL Validation | pySHACL |
| OWL Reasoning | owlready2 + HermiT / Pellet |
| Clustering | SpaCy, sentence-transformers, scikit-learn AP |
| Evaluation | Exact Match, Fuzzy Match F1, cross-prompt stability |
| SDK | Python package |
| CLI | Typer / Click |
| Notebook | Jupyter |
| Future Agent Interface | MCP Server |

---

## 7. 研发里程碑

### M0. 文档与项目骨架

- PRD 固化；
- README 起草；
- Python package skeleton；
- `docs/`、`notebooks/`、`tests/`、`examples/` 建立。

### M1. Schema 编译闭环

- LinkML schema 示例；
- JSON Schema 导出；
- SHACL 导出；
- TTL / OWL 导出。

### M2. ABox 提取闭环

- R-C-N-S-V-O prompt builder；
- structured JSON output；
- JSON Schema validation；
- RDF serialization。

### M3. SHACL 裁判与自修复

- pySHACL validation；
- violation parser；
- diagnostic prompt builder；
- self-repair controller。

### M4. Benchmark 与 Notebook

- 至少一个公开或自建小数据集；
- Exact Match / Fuzzy Match；
- 端到端 notebook；
- 错误分析。

### M5. 扩展能力

- OWL reasoner；
- AP clustering discovery；
- anti-fragility cross-prompt testing；
- MCP Server。

---

## 8. 风险与约束

| 风险 | 影响 | 缓解 |
|---|---|---|
| “100% 确定性”表述过强 | 学术或商业审查中易被质疑 | 改为“符号验证器给出确定性校验结果” |
| OWL reasoner 集成复杂 | MVP 进度受阻 | MVP 先以 pySHACL 为主，OWL 推理后置 |
| LLM 修复可能循环失败 | 自动化闭环不稳定 | max_retries + Human-in-the-Loop |
| AP 聚类质量不稳定 | 冷启动 TBox 噪声高 | 作为辅助 discovery，不直接入生产 schema |
| Prompt 解耦测试成本高 | 增加评测复杂度 | 先设计最小双模板一致性测试 |
| 多格式派生不一致 | schema drift | LinkML 作为唯一源头，所有格式自动编译 |

---

## 9. 一句话产品定义

> NeuroOntoGen 是一个 SDK-first 的神经符号本体生成引擎：用 LLM 从文本中柔性抽取候选知识，用 LinkML/SHACL/OWL 提供可计算护栏，并通过自修复闭环把不可靠生成转化为可验证、可审计、可持久化的知识图谱资产。
