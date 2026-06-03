# 10 安全与治理

## 1. 安全边界

Evoloop 2.0 的核心安全原则是：Agent 没有默认外部能力。所有读取、写入、检索、网络和外部系统操作都必须经 ToolService 授权。

## 2. Tool 沙箱

```text
Agent request tool
  -> ToolService checks ToolSpec exists
  -> ToolPolicy checks role/node/workspace permission
  -> argument schema validation
  -> call handler
  -> ToolResult
  -> emit tool.call.completed / failed / denied
```

`denied` 是权限结果，不是普通失败。前端和审计应能区分。

## 3. 数据隔离

- Workspace 是默认租户隔离键。
- Task、Material、Artifact、Evidence、RuleCandidate 都必须带 workspace_id。
- GBrain source 路由必须绑定 Workspace/Domain Pack。
- 前端 API 不能通过 artifact_id 读取其他 Workspace 产物。

## 4. 敏感信息处理

禁止进入事件和日志：

- `.env` 内容。
- token、secret、key、authorization。
- 完整本地路径。
- 未授权材料全文。
- 原始用户上传文件二进制。

LLM telemetry 只能记录模型、耗时、状态、token 数等安全字段。

## 5. 法则治理

可信法则影响后续任务，因此必须有治理流程：

1. CandidateRule 初始为 pending。
2. 高风险 scope/protection 必须显示二次确认。
3. 与全局法则冲突时必须阻断一键入库。
4. 审核通过记录 reviewer、时间、修改内容和 evidence_id。
5. 归档法则不能直接硬删除，应进入 archive source 或 soft delete。

## 6. 第三方扩展包治理

扩展包加载前必须校验：

- manifest schema。
- SlotContract 兼容性。
- ToolPolicy 最小权限。
- 是否声明外部网络访问。
- 是否包含未授权 prompt 注入或路径读取。

未来可以增加扩展包签名和 trust level。

## 7. 审计事件

必须持久化：

- ToolCall 全生命周期。
- DAG plan approve / modify。
- 用户 takeover。
- Artifact final save。
- Evidence freeze。
- Rule review and store。
- GBrain write result。
