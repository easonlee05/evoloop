# 01 Workspace 与领域包

## 1. Workspace 是平台隔离单元

Workspace 承载用户或团队的领域选择、知识源配置、扩展包、任务历史、法则作用域和安全策略。所有任务都必须归属于某个 Workspace。

建议模型：

```text
Workspace
  id
  display_name
  owner
  active_domain_pack
  enabled_expansion_packs[]
  gbrain_sources[]
  tool_policy_overrides
  default_task_templates[]
  created_at / updated_at
```

## 2. 领域包与扩展包

领域包定义“这个 Workspace 的默认专业语境”。扩展包定义额外 Agent、Tool 权限、任务模板和规则作用域。

```text
DomainPack
  manifest.yaml
  contracts/
  agents/
  task_templates/
  prompts/
  rule_scopes.yaml
  tool_policy.yaml
```

| 类型 | 例子 | 作用 |
|---|---|---|
| Core Pack | 通用产品协作 | 提供基础 Slot 和 fallback Agent。 |
| Domain Pack | 电商、云原生、SaaS 客服 | 定义领域默认知识源和任务模板。 |
| Expansion Pack | SRE、可观测、活动运营、安全审计 | 追加或覆盖专业 Agent。 |

## 3. 加载流程

```text
Workspace 打开
  -> 读取 workspace config
  -> 加载 Core Pack
  -> 加载 Domain Pack
  -> 加载 Expansion Packs
  -> Registry 校验 SlotContract
  -> 合并 ToolPolicy
  -> 绑定 GBrain source
  -> 生成 active runtime profile
```

## 4. Override 与 Append

- **Override**：扩展包替换基础 Slot 的实现，但必须兼容 SlotContract。
- **Append**：扩展包新增 Agent Slot，不影响已有基础 Slot。
- **Fallback**：扩展包缺失或加载失败时，Core Pack 保证基本任务仍可运行。

## 5. 防污染策略

领域包选择不能完全交给 LLM 自动判断。建议采用前端初始化向导：

1. 用户创建 Workspace。
2. 选择行业/工作类型。
3. 系统展示将启用的 Agent 和规则源。
4. 用户确认后固化到 Workspace config。
5. 后续任务默认继承该领域上下文。

这样可以避免云原生任务误加载电商规则，也避免电商 PRD 被 SRE 专家过度技术化。

## 6. 与 GBrain Source 的绑定

```text
Workspace.active_domain_pack = cloud_native
  -> rules-global
  -> rules-domain/cloud_native
  -> knowledge-platform
  -> knowledge-business/{workspace_id}
```

Workspace 不直接拥有知识检索实现，只声明应该查哪些 GBrain source。
