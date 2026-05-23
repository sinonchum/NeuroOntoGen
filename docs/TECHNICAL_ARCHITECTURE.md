# NeuroOntoGen 技术架构与详细设计

> 版本：v0.1  
> 状态：技术设计草案  
> 对应 PRD：`docs/PRD.md`  
> 核心目标：将 LLM 的柔性抽取能力与 LinkML / SHACL / OWL 等确定性符号系统结合，形成可验证、可修复、可持久化的本体与知识图谱生成底座。

---

## 1. 核心技术栈（Technology Matrix）

### 1.1 语言与运行环境

| 项目 | 选择 | 说明 |
|---|---|---|
| 编程语言 | Python 3.10+ | 兼容主流语义网、ML、LLM SDK 生态。 |
| 包管理 | `pyproject.toml` | 建议使用 PEP 621 标准项目元数据。 |
| 测试框架 | `pytest` | 用于 SDK、validator、repair loop、CLI smoke tests。 |
| 类型校验 | `mypy` / `pyright` 可选 | 中后期提高 SDK 稳定性。 |

### 1.2 核心框架集成

| 技术 | 角色 | 用途 |
|---|---|---|
| `linkml` | TBox 建模与格式派生 | 负责 YAML schema 建模、JSON Schema / SHACL / OWL 等派生。 |
| `rdflib` | RDF 操作层 | 负责 RDF Graph 构造、三元组操作、Turtle 导出。 |
| `owlready2` | OWL 推理适配 | 负责 HermiT / Pellet 一致性推理，依赖 Java / JPype。 |
| `pyshacl` | SHACL 结构验证 | 负责封闭世界 CWA 数据模型合规性校验。 |
| `scikit-learn` | 聚类发现 | 负责 Affinity Propagation 冷启动概念聚类。 |
| `sentence-transformers` | 术语向量化 | 将候选术语映射为语义向量。 |
| `spacy` | 术语抽取 | 从文本中抽取名词短语和领域术语。 |
| `pydantic` | 强类型数据模型 | 定义内部 API 类型与 JSON Schema 转换。 |

---

## 2. 推荐项目结构

```text
NeuroOntoGen/
├── README.md
├── pyproject.toml
├── schemas/
│   └── company_schema.yaml
├── src/
│   └── neuro_onto_gen/
│       ├── __init__.py
│       ├── core/
│       │   ├── models.py
│       │   ├── validator.py
│       │   ├── repair_agent.py
│       │   ├── serializer.py
│       │   └── extraction.py
│       ├── schema/
│       │   └── compiler.py
│       ├── clustering/
│       │   └── discovery.py
│       ├── evaluation/
│       │   └── prompt_stability.py
│       └── cli.py
├── tests/
│   ├── test_models.py
│   ├── test_validator.py
│   ├── test_repair_agent.py
│   └── fixtures/
│       ├── company_schema.yaml
│       ├── valid_abox.ttl
│       └── invalid_abox.ttl
├── docs/
│   ├── PRD.md
│   └── TECHNICAL_ARCHITECTURE.md
└── notebooks/
    └── end_to_end_demo.ipynb
```

设计原则：

- `src/neuro_onto_gen/core/` 放置最小神经符号闭环；
- `schema/compiler.py` 负责 LinkML 派生，不与 LLM 抽取耦合；
- `serializer.py` 单独负责 Pydantic → RDF/Turtle；
- `validator.py` 只做验证，不负责调用 LLM；
- `repair_agent.py` 编排验证失败后的诊断 prompt 与重试；
- CLI / MCP 未来只作为 SDK adapter，不复制核心逻辑。

---

## 3. 声明式 YAML 骨架：LinkML TBox Schema 示例

建议在项目根目录下定义：

```text
schemas/company_schema.yaml
```

示例：

```yaml
id: http://example.org/neuro-onto-gen/company
name: CompanyOntology
prefixes:
  ex: http://example.org/company/
  linkml: https://w3id.org/linkml/

imports:
  - linkml:types

classes:
  Employee:
    description: "An active staff member of the corporation"
    attributes:
      empId:
        range: string
        required: true
      hasAccessLevel:
        range: integer
        required: true

  SecureAsset:
    description: "A digital or physical asset requiring clearance"
    attributes:
      assetId:
        range: string
        required: true
      requiredClearance:
        range: integer
        required: true

slots:
  operates:
    domain: Employee
    range: SecureAsset
    multivalued: true
```

### 3.1 设计说明

该 schema 表达了一个最小安全访问场景：

- `Employee`：员工实体；
- `SecureAsset`：需要权限的资产；
- `operates`：员工操作资产的对象关系；
- `hasAccessLevel` 与 `requiredClearance` 可用于后续规则推理：员工权限级别是否足以操作资产。

### 3.2 后续可派生产物

从该 LinkML schema 应派生：

| 产物 | 用途 |
|---|---|
| JSON Schema | 约束 LLM structured output。 |
| SHACL Shapes | 校验 ABox RDF 是否满足字段、类型、基数约束。 |
| OWL / Turtle | 表达 TBox 类、属性、关系及后续推理规则。 |
| Pydantic model | SDK 内部强类型对象与 API schema。 |

---

## 4. Pydantic ABox 数据模型与 JSON Schema 约束

### 4.1 最小 Pydantic 模型

建议放置于：

```text
src/neuro_onto_gen/core/models.py
```

示例：

```python
from typing import List, Literal

from pydantic import BaseModel, Field


class ExtractedEmployee(BaseModel):
    emp_id: str = Field(..., description="Unique ID of the employee, e.g. EMP-101")
    access_level: int = Field(..., description="Access clearance level as an integer")


class ExtractedSecureAsset(BaseModel):
    asset_id: str = Field(..., description="Unique ID of the secure asset, e.g. ASSET-9")
    required_clearance: int = Field(..., description="Required clearance level as an integer")


class ExtractedRelation(BaseModel):
    subject_emp_id: str = Field(..., description="Employee ID acting as subject")
    object_asset_id: str = Field(..., description="Secure asset ID acting as object")
    predicate: Literal["operates"] = "operates"


class ABoxPayload(BaseModel):
    employees: List[ExtractedEmployee]
    assets: List[ExtractedSecureAsset]
    relations: List[ExtractedRelation]
```

### 4.2 对原草案的技术修正

原始草案中：

```python
class ABoxPayload(BaseModel):
    employees: List[ExtractedEmployee]
    relations: List
```

建议改为：

```python
relations: List[ExtractedRelation]
```

原因：

- 避免关系对象无类型；
- 方便导出 JSON Schema；
- 方便 repair loop 判断具体字段；
- 方便 RDF serializer 生成 subject / predicate / object。

同时建议字段命名统一为 Python snake_case，例如：

- `emp_id`；
- `access_level`；
- `asset_id`；
- `required_clearance`。

再在 RDF serializer 中映射到 ontology predicate：

- `emp_id` → `ex:empId`；
- `access_level` → `ex:hasAccessLevel`；
- `required_clearance` → `ex:requiredClearance`。

---

## 5. LLM ABox Extractor 接口设计

建议放置于：

```text
src/neuro_onto_gen/core/extraction.py
```

### 5.1 抽象接口

```python
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def extract_abox_from_text(raw_text: str, pydantic_class: Type[T]) -> T:
    """Extract a structured ABox payload from raw text.

    The production implementation should call an LLM provider with strict
    structured-output / JSON Schema mode and parse the result into pydantic_class.
    """
    raise NotImplementedError
```

### 5.2 OpenAI structured output 示例

```python
from typing import Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def extract_abox_from_text(raw_text: str, pydantic_class: Type[T], model: str = "gpt-4o-mini") -> T:
    client = OpenAI()
    response = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are an ontology extraction engine. Return only schema-compliant data.",
            },
            {
                "role": "user",
                "content": raw_text,
            },
        ],
        response_format=pydantic_class,
    )
    return response.choices[0].message.parsed
```

### 5.3 设计注意事项

- 不要在核心 SDK 中硬编码单一模型 provider；
- MVP 可以先提供 OpenAI adapter，但核心接口应可替换；
- structured output 失败必须显式抛错，不得静默降级为自然语言解析；
- 所有 prompt template 应版本化，便于 benchmark 复现。

---

## 6. RDF/Turtle 序列化器设计

建议放置于：

```text
src/neuro_onto_gen/core/serializer.py
```

### 6.1 Pydantic → RDF/Turtle

```python
from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD

from neuro_onto_gen.core.models import ABoxPayload

EX = Namespace("http://example.org/company/")


def serialize_pydantic_to_turtle(payload: ABoxPayload) -> str:
    """Serialize a typed ABox payload into Turtle."""
    graph = Graph()
    graph.bind("ex", EX)

    for employee in payload.employees:
        employee_uri = URIRef(EX[f"employee/{employee.emp_id}"])
        graph.add((employee_uri, RDF.type, EX.Employee))
        graph.add((employee_uri, EX.empId, Literal(employee.emp_id, datatype=XSD.string)))
        graph.add((employee_uri, EX.hasAccessLevel, Literal(employee.access_level, datatype=XSD.integer)))

    for asset in payload.assets:
        asset_uri = URIRef(EX[f"asset/{asset.asset_id}"])
        graph.add((asset_uri, RDF.type, EX.SecureAsset))
        graph.add((asset_uri, EX.assetId, Literal(asset.asset_id, datatype=XSD.string)))
        graph.add((asset_uri, EX.requiredClearance, Literal(asset.required_clearance, datatype=XSD.integer)))

    for relation in payload.relations:
        subject_uri = URIRef(EX[f"employee/{relation.subject_emp_id}"])
        object_uri = URIRef(EX[f"asset/{relation.object_asset_id}"])
        graph.add((subject_uri, EX.operates, object_uri))

    return graph.serialize(format="turtle")
```

### 6.2 设计注意事项

- URI 构造必须稳定；
- ID 字段需做 URI-safe normalization；
- 生产版本应支持 base IRI 配置；
- serializer 不应调用 LLM，也不应做业务修复。

---

## 7. pySHACL 双重裁判与 ABox 验证核心逻辑

建议放置于：

```text
src/neuro_onto_gen/core/validator.py
```

### 7.1 Validator Class

```python
from pathlib import Path
from typing import Tuple

from pyshacl import validate as shacl_validate
from rdflib import Graph


class NeuroSymbolicValidator:
    def __init__(self, tbox_owl_path: str | Path, shacl_shapes_path: str | Path):
        self.tbox_graph = Graph()
        self.tbox_graph.parse(str(tbox_owl_path), format="turtle")
        self.shacl_shapes_path = str(shacl_shapes_path)

    def run_shacl_validation(self, abox_turtle_data: str) -> Tuple[bool, str]:
        """Run pySHACL validation over an ABox Turtle string.

        Args:
            abox_turtle_data: Turtle-formatted ABox data.

        Returns:
            A tuple of (conforms, report_text).
        """
        abox_graph = Graph()
        abox_graph.parse(data=abox_turtle_data, format="turtle")

        combined_data = abox_graph + self.tbox_graph

        conforms, _results_graph, results_text = shacl_validate(
            data_graph=combined_data,
            shacl_graph=self.shacl_shapes_path,
            inference="rdfs",
            serialize_results_graph=True,
            serialize_results_format="turtle",
        )
        return bool(conforms), str(results_text)
```

### 7.2 设计注意事项

- `tbox_owl_path` 变量名可保留，但 MVP 中实际可以先使用 Turtle；
- `shacl_graph` 可传路径，也可传 `Graph`，为了简单先传路径；
- `results_graph` 后续应保留并解析结构化 violation，而不只依赖 text；
- SHACL 是 MVP 主裁判；OWL reasoner 可作为 M2/M3 后续增强。

---

## 8. 自修复控制器设计（Self-Repair Controller）

建议放置于：

```text
src/neuro_onto_gen/core/repair_agent.py
```

### 8.1 核心循环

```python
from neuro_onto_gen.core.extraction import extract_abox_from_text
from neuro_onto_gen.core.models import ABoxPayload
from neuro_onto_gen.core.serializer import serialize_pydantic_to_turtle
from neuro_onto_gen.core.validator import NeuroSymbolicValidator


class SelfRepairController:
    def __init__(self, validator: NeuroSymbolicValidator, max_retries: int = 3):
        self.validator = validator
        self.max_retries = max_retries

    def execute_robust_pipeline(self, raw_text: str, initial_payload: ABoxPayload) -> str:
        """Execute the neuro-symbolic validation and self-repair loop."""
        current_payload = initial_payload

        for attempt in range(self.max_retries + 1):
            turtle_data = serialize_pydantic_to_turtle(current_payload)
            conforms, report = self.validator.run_shacl_validation(turtle_data)

            if conforms:
                return turtle_data

            if attempt >= self.max_retries:
                raise ValueError(
                    "[Fatal Error] Repair retries exhausted. "
                    "Generated ontology data is still non-conformant and has been blocked."
                )

            current_payload = self.call_llm_for_repair(
                original_text=raw_text,
                failed_payload=current_payload,
                shacl_report=report,
            )

        raise RuntimeError("Unreachable repair controller state")
```

### 8.2 Diagnostic Prompt 构造

```python
    def call_llm_for_repair(
        self,
        original_text: str,
        failed_payload: ABoxPayload,
        shacl_report: str,
    ) -> ABoxPayload:
        repair_prompt = f"""
You are repairing a schema-constrained ontology extraction result.

Original input text:
{original_text}

Previous invalid JSON payload:
{failed_payload.model_dump_json(indent=2)}

pySHACL validation report:
{shacl_report}

Repair instructions:
1. Inspect the SHACL violation focusNode, resultPath, sourceShape, and message.
2. If cardinality is exceeded, remove the unsupported extra value or relation.
3. If a required property is missing, recover it from the original text if possible.
4. If the source text does not support the missing value, do not hallucinate; leave the item out if schema permits, or return the closest valid minimal payload.
5. Return only JSON that conforms to the given Pydantic / JSON Schema.
"""
        return extract_abox_from_text(repair_prompt, ABoxPayload)
```

### 8.3 对原草案的技术修正

原文中要求：

> 保证输出的数据结构百分之百符合给定的 JSON Schema。

建议工程实现中改为：

> 要求模型输出 schema-compliant JSON，但最终合规性必须由 Pydantic / JSON Schema / SHACL 验证器判定。

原因：

- LLM 不能被信任为最终裁判；
- “百分之百”不应由 prompt 承诺，而应由代码验证；
- 修复失败必须被拦截，而不是被语言表述掩盖。

---

## 9. OWL Reasoner 设计边界

### 9.1 MVP 阶段

MVP 可先只做：

- LinkML → SHACL；
- ABox JSON → RDF/Turtle；
- PySHACL validation；
- Self-repair loop。

### 9.2 后续增强

OWL 推理模块可在后续加入：

```text
src/neuro_onto_gen/core/owl_reasoner.py
```

目标能力：

- 加载 TBox + ABox；
- 执行 Pellet / HermiT；
- 检查 inconsistent classes；
- 检查 disjointness violation；
- 推导 inverseOf / transitive / SWRL 规则关系；
- 将 OWL inconsistency 转换为 repair diagnostic。

### 9.3 风险

- owlready2 依赖 Java 环境；
- HermiT / Pellet 行为与平台相关；
- OWL 推理错误报告比 SHACL 更难映射回 JSON payload；
- 不建议作为第一版阻塞项。

---

## 10. Clustering Discovery 设计边界

建议放置于：

```text
src/neuro_onto_gen/clustering/discovery.py
```

核心步骤：

1. 使用 SpaCy 抽取候选术语；
2. 使用 sentence-transformers 生成 embedding；
3. 使用 Affinity Propagation 聚类；
4. 使用 LLM 对 cluster 命名；
5. 生成 LinkML TBox draft；
6. 由人类专家审查后进入正式 schema。

重要原则：

> AP clustering 只能用于 schema discovery，不应直接成为生产 TBox 的自动写入机制。

---

## 11. Prompt 解耦测试设计边界

建议放置于：

```text
src/neuro_onto_gen/evaluation/prompt_stability.py
```

核心能力：

- 支持多个语义等价 prompt 模板；
- 对同一输入批量运行；
- 将输出统一转为 canonical triples；
- 计算跨 prompt 的 triple-level F1；
- 标记 unstable triples。

示例模板对：

```text
Template A: Is X a subclass of Y?
Template B: Is Y a superclass of X?
```

输出指标：

| 指标 | 含义 |
|---|---|
| `prompt_pair_f1` | 两个 prompt 输出的三元组相似度。 |
| `stable_triple_ratio` | 多模板下稳定出现的三元组比例。 |
| `unstable_triples` | 仅在少数 prompt 下出现的候选关系。 |

---

## 12. MVP 实现顺序

建议按以下顺序实现，避免过早引入复杂 OWL / AP / MCP：

### Step 1. 项目骨架

- `pyproject.toml`；
- `src/neuro_onto_gen/`；
- `tests/`；
- `schemas/company_schema.yaml`。

### Step 2. Pydantic 数据模型

- `ExtractedEmployee`；
- `ExtractedSecureAsset`；
- `ExtractedRelation`；
- `ABoxPayload`。

### Step 3. RDF Serializer

- `serialize_pydantic_to_turtle(payload)`；
- 单元测试验证 Turtle 中含有 employee、asset、operates triple。

### Step 4. SHACL Validator

- `NeuroSymbolicValidator`；
- fixture：valid ABox / invalid ABox；
- 单元测试验证 invalid ABox 被拦截。

### Step 5. Self-Repair Controller

- 先 mock `extract_abox_from_text`；
- 测试第一次失败、第二次修复成功；
- 测试超过 `max_retries` 抛错。

### Step 6. LLM Extractor Adapter

- 增加 OpenAI structured output adapter；
- 明确 provider abstraction；
- 不让 SDK 核心依赖特定 provider。

### Step 7. CLI Smoke Test

- `neuro-onto-gen validate`；
- `neuro-onto-gen extract`；
- `neuro-onto-gen repair`。

---

## 13. 技术验收清单

### 13.1 Schema 层

- [ ] LinkML schema 可解析；
- [ ] JSON Schema 可生成；
- [ ] SHACL Shapes 可生成；
- [ ] Turtle / OWL 基础 TBox 可生成。

### 13.2 Extraction 层

- [ ] ABoxPayload JSON Schema 可导出；
- [ ] LLM 输出可被 Pydantic parse；
- [ ] 非 schema-compliant 输出会失败并被拦截。

### 13.3 Serialization 层

- [ ] Employee 转为 RDF resource；
- [ ] SecureAsset 转为 RDF resource；
- [ ] operates 转为 object property triple；
- [ ] 输出 Turtle 可被 rdflib 重新 parse。

### 13.4 Validation 层

- [ ] valid ABox 通过 pySHACL；
- [ ] missing required property 被 pySHACL 报错；
- [ ] wrong datatype 被 pySHACL 报错；
- [ ] violation report 可被 repair controller 接收。

### 13.5 Repair 层

- [ ] repair loop 可在 mock LLM 下收敛；
- [ ] `max_retries` 生效；
- [ ] 修复失败会抛错并阻止入库；
- [ ] 修复历史可记录。

---

## 14. 与 PRD 的对应关系

| PRD 功能 | 技术模块 |
|---|---|
| F1 TBox 元模型编译引擎 | `schema/compiler.py`, `schemas/*.yaml` |
| F2 R-C-N-S-V-O ABox 提取器 | `core/extraction.py`, `core/models.py` |
| F3 双重符号裁判引擎 | `core/validator.py`, future `core/owl_reasoner.py` |
| F4 自修复闭环 | `core/repair_agent.py` |
| F5 AP 聚类冷启动 | `clustering/discovery.py` |
| F6 Prompt 解耦测试 | `evaluation/prompt_stability.py` |

---

## 15. 关键工程原则

1. **Schema first**：LinkML / Pydantic schema 是系统边界，不是 prompt 附属品。  
2. **LLM never validates itself**：LLM 只能生成和修复，不能担任最终裁判。  
3. **Prompt is not a guardrail**：安全约束必须由代码、schema、SHACL、OWL 执行。  
4. **SHACL before database**：任何数据入库前必须经过 SHACL。  
5. **Repair must be bounded**：自修复必须有 `max_retries` 和失败挂起机制。  
6. **MVP avoids OWL blocking**：第一版不要被 Java / OWL reasoner 集成拖住。  
7. **SDK before CLI/MCP**：核心逻辑必须先在 SDK 内可测试，再暴露给 CLI 和 MCP。
