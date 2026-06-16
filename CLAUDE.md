# 保研知识库项目

## 项目目标

构建南京邮电大学保研（推免）知识库，覆盖各学院的推免方案、复试录取细则等政策文件，用于 RAG 问答。

## 数据来源

- 原始 PDF/网页从各学院官网和教务处下载
- 清洗为 Markdown 后导入知识库平台

## 目录结构

```
school/
├── 原始PDF/                  # 从官网下载的原始文件
├── raw_data/                 # Markdown 预处理中间产物
├── dify_clean_payload/       # 知识库最终文件（47 个 md）
│   ├── 00_知识库索引.md      # 分类索引
│   ├── 0x_*推免方案.md       # 各学院推免方案（~18 份）
│   └── 2x_*复试录取细则.md   # 各学院复试细则（~20 份）
├── build_dify_ready_payload.py      # 原始转换脚本
├── optimize_dify_ready_payload_v2.py # V2 优化脚本
└── dify_api_broad_test_results.json  # API 测试结果
```

## 模型配置（旧 Dify 平台，已弃用）

- **Embedding**: Qwen/Qwen3-Embedding-0.6B @ SiliconFlow
- **Rerank**: BAAI/bge-reranker-v2-m3 @ SiliconFlow
- **API 地址**: https://api.siliconflow.cn/v1
- **API Key**: 在 SiliconFlow 控制台查看 https://cloud.siliconflow.cn/account/ak

## 重要提醒

- 复试细则中联系方式（邮箱、电话）可能漏抓，需要交叉验证
- 知识库文件的 frontmatter 包含 category、year、status、tags
