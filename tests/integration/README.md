# 集成测试

- 需真实依赖时（如 LLM、DB），从 `config/settings.yaml` 加载配置。
- **真实 LLM 测试**：默认使用 **DeepSeek** 配置（`llm.provider: deepseek`，`api_key`、`base_url` 在本地 `config/settings.yaml` 中配置）。
- 运行：`pytest tests/integration/ -v -m integration`；无配置或 skip 条件满足时会跳过。
