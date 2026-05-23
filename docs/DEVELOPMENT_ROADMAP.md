# NeuroOntoGen 开发大纲与路线图

> **For Hermes:** Use subagent-driven-development skill to implement this roadmap task-by-task.

**Goal:** 将 NeuroOntoGen 从空仓库推进为一个可复现、可测试、可演示的 SDK-first 神经符号本体生成引擎。

**Architecture:** 项目以 Python SDK 为核心，先实现 LinkML/Pydantic/rdflib/pySHACL 组成的最小闭环，再逐步引入 LLM structured extraction、self-repair、OWL reasoning、clustering discovery、CLI、Notebook 与未来 MCP adapter。所有功能遵循“Schema first, LLM never validates itself, SHACL before database”的工程原则。

**Tech Stack:** Python 3.10+, LinkML, Pydantic, rdflib, pySHACL, owlready2, scikit-learn, sentence-transformers, SpaCy, pytest, Typer/Click, Jupyter.

---

## 0. 路线图定位

本文档基于：

- `docs/PRD.md`
- `docs/TECHNICAL_ARCHITECTURE.md`
- 本地指导文档 `LLM构建本体的挑战与流派.md`
- 原始草案 `/Users/fqn/Documents/Onto_development_roadmap_draft.md`

进行整理与优化，作为 NeuroOntoGen 的正式开发大纲。

优化原则：

1. **先 SDK，后 CLI/MCP**：核心逻辑必须先在 SDK 内可测试。
2. **先 SHACL，后 OWL**：MVP 不被 Java / HermiT / Pellet 集成阻塞。
3. **先可复现闭环，后高级能力**：第一目标是跑通 LinkML → JSON/Pydantic → RDF → SHACL → bounded repair。
4. **每阶段都有可验证产物**：避免“写了代码但没有证明能运行”。
5. **学术与商业共同服务**：Notebook/benchmark 支撑论文，CLI/MCP 支撑开发者和企业生态。

---

## 1. 总体阶段规划

```text
+----------------------------------------------------------------------------------+
|                          NeuroOntoGen Development Timeline                        |
+----------------------------------------------------------------------------------+
| Phase 0: 文档与仓库基线                                                           |
|  └─ PRD / 技术架构 / 开发路线图 / README 基线                                      |
+----------------------------------------------------------------------------------+
| Phase 1: Python SDK 骨架与 Schema 编译闭环                                         |
|  └─ pyproject, src layout, LinkML schema, JSON Schema / SHACL / TTL 派生            |
+----------------------------------------------------------------------------------+
| Phase 2: ABox 数据模型、提取接口与 RDF 序列化                                      |
|  └─ Pydantic payload, prompt builder, structured extraction adapter, rdflib TTL     |
+----------------------------------------------------------------------------------+
| Phase 3: SHACL 裁判与最小自修复闭环                                                |
|  └─ pySHACL validation, violation parsing, bounded repair with mocked LLM           |
+----------------------------------------------------------------------------------+
| Phase 4: OWL 推理、冷启动聚类与 Prompt 抗脆弱评测                                  |
|  └─ owlready2/HermiT, AP clustering, cross-prompt stability metrics                 |
+----------------------------------------------------------------------------------+
| Phase 5: CLI、Notebook、Benchmark、CI 与发布准备                                   |
|  └─ Typer/Click CLI, reproducible notebook, smoke benchmark, GitHub Actions         |
+----------------------------------------------------------------------------------+
| Phase 6: Agent 生态与商业化接口                                                    |
|  └─ MCP Server, graph DB connectors, audit artifacts, optional private deployment   |
+----------------------------------------------------------------------------------+
```

建议排期：

| 阶段 | 时间 | 目标 |
|---|---:|---|
| Phase 0 | 0.5 周 | 固化文档与仓库方向。 |
| Phase 1 | 1–2 周 | 建立 SDK 骨架与 schema 编译产物。 |
| Phase 2 | 1 周 | 跑通 ABox JSON → RDF/Turtle。 |
| Phase 3 | 1–2 周 | 跑通 SHACL validation + mock self-repair。 |
| Phase 4 | 2 周 | 加入 OWL / clustering / prompt robustness。 |
| Phase 5 | 1–2 周 | 完成 CLI、Notebook、benchmark、CI。 |
| Phase 6 | 后续 | MCP、图数据库与企业集成。 |

---

## 2. Phase 0：文档与仓库基线

### 目标

把项目从“概念草案”变成可执行研发项目。

### 产物

- `docs/PRD.md`
- `docs/TECHNICAL_ARCHITECTURE.md`
- `docs/DEVELOPMENT_ROADMAP.md`
- `README.md` 初版
- `.gitignore` 已排除本地指导文档和 local notes

### 任务清单

#### Task 0.1：确认公开文档边界

**Objective:** 区分可进入 GitHub 的正式文档与只保留本地的策略/指导材料。

**Files:**

- Verify: `.gitignore`
- Verify: `docs/PRD.md`
- Verify: `docs/TECHNICAL_ARCHITECTURE.md`
- Verify: `docs/DEVELOPMENT_ROADMAP.md`

**Verification:**

```bash
git status --short --ignored
git check-ignore -v 'LLM构建本体的挑战与流派.md' 'LLM构建本体的挑战与流派.gdoc'
```

Expected:

- 本地指导文档被忽略；
- `docs/*.md` 作为正式项目文档可被追踪。

#### Task 0.2：README 对齐定位

**Objective:** README 明确项目一句话定位、核心 pipeline、MVP 范围。

**Files:**

- Modify: `README.md`

**README 必须包含：**

- One-liner；
- Why NeuroOntoGen；
- Architecture overview；
- MVP roadmap；
- Documentation links。

---

## 3. Phase 1：Python SDK 骨架与 Schema 编译闭环

### 目标

建立现代 Python 项目骨架，并实现最小 LinkML schema 编译闭环。

### 产物

```text
pyproject.toml
src/neuro_onto_gen/__init__.py
src/neuro_onto_gen/schema/compiler.py
schemas/company_schema.yaml
tests/test_schema_compiler.py
```

### 关键设计调整

原草案中建议：

```text
neuro_onto_gen/src/core
```

优化为标准 src-layout：

```text
src/neuro_onto_gen/core
```

原因：

- 符合现代 Python package 规范；
- 避免 import path 混乱；
- 便于 PyPI 发布；
- 便于 pytest 发现真实安装包问题。

### Task 1.1：创建 Python 包骨架

**Objective:** 建立可安装、可测试的 Python package。

**Files:**

- Create: `pyproject.toml`
- Create: `src/neuro_onto_gen/__init__.py`
- Create: `src/neuro_onto_gen/core/__init__.py`
- Create: `src/neuro_onto_gen/schema/__init__.py`
- Create: `tests/__init__.py`

**Dependencies MVP:**

```toml
[project]
requires-python = ">=3.10"
dependencies = [
  "pydantic>=2",
  "rdflib>=7",
  "pyshacl>=0.25",
  "linkml>=1.7",
  "typer>=0.12",
]

[project.optional-dependencies]
llm = ["openai>=1.0"]
clustering = ["scikit-learn", "sentence-transformers", "spacy"]
owl = ["owlready2", "jpype1"]
dev = ["pytest", "ruff"]
```

**Verification:**

```bash
python -m pip install -e '.[dev]'
python -c "import neuro_onto_gen; print(neuro_onto_gen.__name__)"
```

Expected:

```text
neuro_onto_gen
```

### Task 1.2：添加 Company LinkML schema fixture

**Objective:** 提供贯穿 MVP 的最小 TBox 示例。

**Files:**

- Create: `schemas/company_schema.yaml`
- Copy or mirror for tests: `tests/fixtures/company_schema.yaml`

**Core classes:**

- `Employee`
- `SecureAsset`
- slot `operates`

**Verification:**

```bash
python -m linkml_runtime.utils.schemaview schemas/company_schema.yaml
```

Expected: schema 可被 LinkML 读取。

### Task 1.3：实现 schema compiler wrapper

**Objective:** 用一个 SDK 接口包装 LinkML 派生命令。

**Files:**

- Create: `src/neuro_onto_gen/schema/compiler.py`
- Test: `tests/test_schema_compiler.py`

**API 草案:**

```python
from pathlib import Path


def compile_schema(schema_path: Path, output_dir: Path) -> dict[str, Path]:
    """Compile a LinkML schema into JSON Schema, SHACL, and Turtle artifacts."""
```

**Verification:**

```bash
pytest tests/test_schema_compiler.py -v
```

Expected:

- output dir 生成 JSON Schema；
- output dir 生成 SHACL；
- output dir 生成 Turtle/OWL-compatible TBox；
- 产物非空。

---

## 4. Phase 2：ABox 数据模型、提取接口与 RDF 序列化

### 目标

实现从 typed ABox payload 到 RDF/Turtle 的确定性转换，为后续 SHACL 验证提供输入。

### 产物

```text
src/neuro_onto_gen/core/models.py
src/neuro_onto_gen/core/serializer.py
src/neuro_onto_gen/core/prompt_builder.py
src/neuro_onto_gen/core/extraction.py
tests/test_models.py
tests/test_serializer.py
tests/test_prompt_builder.py
```

### Task 2.1：定义 Pydantic ABox 模型

**Objective:** 将 LLM 输出约束为强类型 payload。

**Files:**

- Create: `src/neuro_onto_gen/core/models.py`
- Test: `tests/test_models.py`

**Models:**

- `ExtractedEmployee`
- `ExtractedSecureAsset`
- `ExtractedRelation`
- `ABoxPayload`

**Important:** `relations` 必须是 `list[ExtractedRelation]`，不要使用裸 `List`。

**Verification:**

```bash
pytest tests/test_models.py -v
```

Expected:

- `ABoxPayload.model_json_schema()` 可导出；
- 缺失必填字段时 Pydantic validation 失败；
- relation predicate 限制为 `operates`。

### Task 2.2：实现 RDF/Turtle serializer

**Objective:** 将 ABoxPayload 稳定转换为 Turtle。

**Files:**

- Create: `src/neuro_onto_gen/core/serializer.py`
- Test: `tests/test_serializer.py`

**API:**

```python
def serialize_pydantic_to_turtle(payload: ABoxPayload, base_iri: str = "http://example.org/company/") -> str:
    ...
```

**Verification:**

```bash
pytest tests/test_serializer.py -v
```

Expected:

- Turtle 可被 `rdflib.Graph().parse(data=..., format='turtle')` 重新解析；
- 包含 `Employee` triple；
- 包含 `SecureAsset` triple；
- 包含 `operates` object property triple。

### Task 2.3：实现 R-C-N-S-V-O prompt builder

**Objective:** 将 prompt 组织从散乱字符串变成可版本化模块。

**Files:**

- Create: `src/neuro_onto_gen/core/prompt_builder.py`
- Test: `tests/test_prompt_builder.py`

**Prompt sections:**

- Role
- Context
- Normalization
- Specification
- Value Block
- Output Schema

**Verification:**

```bash
pytest tests/test_prompt_builder.py -v
```

Expected:

- 每个 section 可单独注入；
- prompt 中包含 JSON Schema；
- value block 与 schema block 有明确分隔。

### Task 2.4：定义 LLM extractor provider abstraction

**Objective:** 不让核心 SDK 绑定单一模型供应商。

**Files:**

- Create: `src/neuro_onto_gen/core/extraction.py`
- Test: `tests/test_extraction.py`

**Design:**

```python
class ExtractorProtocol(Protocol):
    def extract(self, raw_text: str, output_model: type[T]) -> T: ...
```

MVP 可先用 fake extractor 或 OpenAI optional adapter。

**Verification:**

```bash
pytest tests/test_extraction.py -v
```

Expected: mock extractor 可返回合法 ABoxPayload。

---

## 5. Phase 3：SHACL 裁判与最小自修复闭环

### 目标

跑通 “ABox Turtle → SHACL validation → violation report → repair controller” 的核心神经符号闭环。

### 产物

```text
src/neuro_onto_gen/core/validator.py
src/neuro_onto_gen/core/repair_agent.py
tests/test_validator.py
tests/test_repair_agent.py
tests/fixtures/valid_abox.ttl
tests/fixtures/invalid_abox.ttl
```

### Task 3.1：实现 SHACL validator

**Objective:** 对 ABox Turtle 执行 pySHACL 校验。

**Files:**

- Create: `src/neuro_onto_gen/core/validator.py`
- Test: `tests/test_validator.py`

**API:**

```python
class NeuroSymbolicValidator:
    def run_shacl_validation(self, abox_turtle_data: str) -> tuple[bool, str]: ...
```

**Verification:**

```bash
pytest tests/test_validator.py -v
```

Expected:

- valid ABox returns `conforms=True`；
- invalid ABox returns `conforms=False`；
- report 包含 focus node / result path 或可解析 violation 信息。

### Task 3.2：实现 violation parser

**Objective:** 从 pySHACL 报告中提取结构化修复上下文。

**Files:**

- Create or Modify: `src/neuro_onto_gen/core/validator.py`
- Test: `tests/test_validator.py`

**Output fields:**

- `focus_node`
- `result_path`
- `source_shape`
- `message`

**Verification:**

```bash
pytest tests/test_validator.py::test_parse_shacl_violations -v
```

Expected: 至少能解析一个 violation。

### Task 3.3：实现 bounded self-repair controller

**Objective:** 在 mock LLM 下测试修复闭环，而不是立即依赖真实模型。

**Files:**

- Create: `src/neuro_onto_gen/core/repair_agent.py`
- Test: `tests/test_repair_agent.py`

**Behavior:**

- 第一次 validation 失败；
- 使用 fake repairer 返回修复 payload；
- 第二次 validation 成功；
- 超过 `max_retries` 抛错。

**Verification:**

```bash
pytest tests/test_repair_agent.py -v
```

Expected:

- repair loop converges with fake repairer；
- retry exhaustion raises `ValueError`；
- 修复失败不会入库。

---

## 6. Phase 4：OWL 推理、冷启动聚类与 Prompt 抗脆弱评测

### 目标

扩展 MVP，使系统覆盖 PRD 中的高级能力，但不影响 Phase 1–3 的稳定闭环。

### 产物

```text
src/neuro_onto_gen/core/owl_reasoner.py
src/neuro_onto_gen/clustering/discovery.py
src/neuro_onto_gen/evaluation/prompt_stability.py
tests/test_owl_reasoner.py
tests/test_clustering_discovery.py
tests/test_prompt_stability.py
```

### Task 4.1：OWL reasoner adapter

**Objective:** 用 owlready2 / HermiT / Pellet 检查逻辑不一致。

**Files:**

- Create: `src/neuro_onto_gen/core/owl_reasoner.py`
- Test: `tests/test_owl_reasoner.py`

**Caveat:** 该任务依赖 Java / JPype，CI 中可先标记为 optional / integration test。

**Verification:**

```bash
pytest tests/test_owl_reasoner.py -v -m integration
```

Expected:

- disjoint classes 冲突可被检测；
- reasoner unavailable 时给出清晰 skip 或 error。

### Task 4.2：AP clustering discovery

**Objective:** 为无 TBox 先验的陌生领域提供 schema discovery 草案。

**Files:**

- Create: `src/neuro_onto_gen/clustering/discovery.py`
- Test: `tests/test_clustering_discovery.py`

**Pipeline:**

1. term extraction；
2. embedding；
3. Affinity Propagation；
4. cluster labeling；
5. LinkML draft generation。

**Verification:**

```bash
pytest tests/test_clustering_discovery.py -v
```

Expected:

- 输入术语列表返回非空 clusters；
- AP 自动给出 cluster count；
- 输出可转换为 schema draft。

### Task 4.3：Cross-prompt robustness testing

**Objective:** 量化 prompt 表观变化对三元组输出的影响。

**Files:**

- Create: `src/neuro_onto_gen/evaluation/prompt_stability.py`
- Test: `tests/test_prompt_stability.py`

**Metrics:**

- triple-level precision；
- triple-level recall；
- triple-level F1；
- stable triple ratio；
- unstable triples list。

**Verification:**

```bash
pytest tests/test_prompt_stability.py -v
```

Expected: 语义等价 prompt 的输出可计算一致性分数。

---

## 7. Phase 5：CLI、Notebook、Benchmark、CI 与发布准备

### 目标

让项目可被审稿人、开发者和未来企业用户快速跑通。

### 产物

```text
src/neuro_onto_gen/cli.py
notebooks/end_to_end_demo.ipynb
examples/company/README.md
examples/company/valid_abox.ttl
examples/company/invalid_abox.ttl
.github/workflows/ci.yml
README.md
```

### Task 5.1：CLI smoke commands

**Objective:** 提供一键本地诊断入口。

**Files:**

- Create: `src/neuro_onto_gen/cli.py`
- Test: `tests/test_cli.py`

**Commands:**

```bash
neuro-onto-gen compile-schema schemas/company_schema.yaml build/schema
neuro-onto-gen validate-turtle examples/company/valid_abox.ttl build/schema/company_schema.shacl.ttl
neuro-onto-gen validate-turtle examples/company/invalid_abox.ttl build/schema/company_schema.shacl.ttl
```

**Verification:**

```bash
pytest tests/test_cli.py -v
```

Expected: CLI help、schema compilation、valid example validation 和 invalid example validation smoke commands 可运行；non-conforming graph 返回非零退出码并打印 structured violations。

### Task 5.1a：Runnable company examples

**Objective:** 让用户 clone 后无需自己编写 Turtle 文件即可跑通 CLI smoke test。

**Files:**

- Create: `examples/company/README.md`
- Create: `examples/company/valid_abox.ttl`
- Create: `examples/company/invalid_abox.ttl`
- Test: `tests/test_examples.py`

**Verification:**

```bash
pytest tests/test_examples.py -v
```

Expected: valid example exits `0` with `conforms: true`；invalid example exits `1` and reports missing `requiredClearance`。

### Task 5.2：End-to-end Notebook

**Objective:** 支撑学术审稿复现和 demo track 展示。

**Files:**

- Create: `notebooks/end_to_end_demo.ipynb`

**Notebook steps:**

1. Load LinkML schema；
2. Compile artifacts；
3. Build ABox payload；
4. Serialize to Turtle；
5. Validate with SHACL；
6. Show violation；
7. Run mock or real repair；
8. Display final TTL。

**Verification:**

```bash
jupyter nbconvert --to notebook --execute notebooks/end_to_end_demo.ipynb --output /tmp/neuro_onto_gen_demo.ipynb
```

Expected: Notebook 可从头执行到尾。

### Task 5.3：Benchmark skeleton

**Objective:** 建立学术评测入口。

**Files:**

- Create: `benchmarks/README.md`
- Create: `benchmarks/run_benchmark.py`
- Create: `src/neuro_onto_gen/evaluation/metrics.py`
- Test: `tests/test_evaluation_metrics.py`
- Test: `tests/test_benchmark_runner.py`

**Metrics:**

- Exact Match；
- Fuzzy Match F1；
- SHACL conformance rate；
- repair success rate；
- prompt stability score。

**Verification:**

```bash
python benchmarks/run_benchmark.py --dataset examples/company --quick
python benchmarks/run_benchmark.py --dataset examples/company --quick --output-markdown /tmp/neuro_onto_gen_benchmark.md
```

Expected: 输出 JSON summary；可选输出 Markdown summary；CI smoke check 执行 quick benchmark。

### Task 5.4：GitHub Actions CI

**Objective:** 每次 push 自动验证核心闭环。

**Files:**

- Create: `.github/workflows/ci.yml`
- Test: `tests/test_ci_workflow.py`

**CI jobs:**

- install package；
- run Ruff；
- run pytest；
- run CLI schema compilation smoke check；
- run CLI valid and invalid Turtle validation smoke checks；
- skip OWL integration unless Java available。

**Verification:**

```bash
pytest tests/test_ci_workflow.py -v
python -m pytest -q
ruff check .
gh run list --branch main --limit 1
```

Expected: workflow contract tests pass locally, and the remote GitHub Actions run completes successfully after push.

---

## 8. Phase 6：Agent 生态与商业化接口

### 目标

在 SDK 稳定后，暴露 Agent-native 与企业集成能力。

### 产物

```text
src/neuro_onto_gen/mcp/server.py
src/neuro_onto_gen/connectors/neo4j.py
src/neuro_onto_gen/audit/logging.py
docs/MCP_USAGE.md
```

### MCP Tools

| Tool | Purpose |
|---|---|
| `get-schema` | 返回当前 TBox / LinkML / SHACL 摘要。 |
| `extract-abox` | 从文本生成候选 ABox。 |
| `validate-and-repair` | 执行 SHACL/OWL 验证与 bounded repair。 |

### 企业集成方向

- Neo4j connector；
- GraphDB / RDF store connector；
- audit log；
- human review artifact；
- private deployment profile。

### 注意

Phase 6 不应在 Phase 1–3 稳定前启动，否则会变成“接口先行、核心不稳”。

---

## 9. 开发优先级排序

### P0：必须先完成

1. Python package skeleton；
2. Pydantic ABox model；
3. RDF serializer；
4. SHACL validator；
5. mock self-repair loop；
6. pytest tests。

### P1：紧随其后

1. LinkML compiler wrapper；
2. OpenAI / provider extractor adapter；
3. CLI validate / run；
4. Notebook demo；
5. GitHub Actions CI。

### P2：高级能力

1. OWL reasoner；
2. AP clustering；
3. prompt robustness；
4. benchmark suite；
5. MCP server。

---

## 10. Definition of Done

### MVP Done

MVP 只有在以下条件全部满足时才算完成：

- [ ] `pip install -e '.[dev]'` 成功；
- [ ] `pytest` 全部通过；
- [ ] 最小 `ABoxPayload` 可序列化为 TTL；
- [ ] valid TTL 通过 pySHACL；
- [ ] invalid TTL 被 pySHACL 拦截；
- [ ] self-repair loop 在 mock LLM 下可从失败转为成功；
- [ ] repair 超过 `max_retries` 后硬性失败；
- [ ] CLI 至少支持 validate；
- [ ] Notebook 可执行；
- [ ] README 说明如何复现。

### Academic Baseline Done

学术基线只有在以下条件满足时才算完成：

- [ ] 有至少一个公开或可发布示例数据集；
- [ ] 有 Exact Match / Fuzzy Match F1；
- [ ] 有 SHACL conformance rate；
- [ ] 有 repair success rate；
- [ ] 有 prompt stability metric；
- [ ] Notebook 可作为 reviewer reproduction package。

### Developer Release Done

开发者发布只有在以下条件满足时才算完成：

- [ ] PyPI package metadata 完整；
- [ ] CLI help 清晰；
- [ ] README 有 quickstart；
- [ ] GitHub Actions 通过；
- [ ] examples 可复制运行；
- [ ] API 文档包含核心模块。

---

## 11. 当前下一步建议

从当前仓库状态看，下一步不应直接实现 OWL、AP clustering 或 MCP，而应先完成 Phase 1–3 的最小闭环。

推荐立即执行顺序：

1. 创建 `pyproject.toml` 与 `src/neuro_onto_gen/` 包骨架；
2. 添加 `schemas/company_schema.yaml`；
3. 实现 `core/models.py`；
4. 实现 `core/serializer.py`；
5. 添加最小 serializer tests；
6. 再实现 pySHACL validator。

完成这些后，NeuroOntoGen 才具备真正的“代码级研发起点”。
