# novel-graph

`novel-graph` 是一个基于 Python 3.12 的小说分析项目，目标不是只生成一篇“扫书稿”，而是先把 EPUB / TXT / Markdown 小说抽成可复用的知识图谱，再把这份图谱用于：

- 扫书 / 书评类总结
- 原文简单解说
- 后续人物关系图、剧情梳理、世界线整理

当前设计参考 MiroFish 的前半段思路：

`正文解析 -> 分段抽取 -> 图谱归约 -> 下游成稿`

## 当前架构

项目现在有两条主流程：

1. `direct`
   直接用提示词或启发式规则生成扫书 Markdown。
2. `graph`
   先生成“通用小说知识图谱”，再基于图谱输出 Markdown。

其中 `graph` 流程不再是旧版那种“只看男主 / 女主候选 / 后宫边”的轻量关系图，而是会尽量保留：

- 人物 `character_profiles`
- 地点 `location_profiles`
- 势力 `faction_profiles`
- 剧情线 `plot_threads`
- 关键关系 `relationship_highlights`
- 世界线顺序 `worldline_order`
- 分段推进摘要 `segment_overview`

这意味着图谱本身就是后续功能的核心中间层，而不是扫书过程中的一次性副产物。

## 适用场景

- 先快速看一段小说，生成扫书稿
- 对整本 EPUB 分段抽图谱，再归约成全书图谱
- 后续基于图谱继续写“原文简单解说”
- 需要把“人物 / 地点 / 势力 / 情节”一并保留下来，而不是只抽情感线

## 环境要求

- Python `3.12`
- `uv`

安装：

```bash
uv sync --dev
```

## 输入格式

当前支持：

- `.epub`
- `.txt`
- `.md` / `.markdown`

## 输出物

根据模式不同，CLI 会输出以下文件：

- `direct_scan.md`
  直接扫书结果
- `graph_scan.md`
  基于知识图谱生成的 Markdown
- `graph_snapshot.json`
  图谱快照

如果输入被分段，单段模式会输出：

- `graph_scan.partN.md`
- `graph_snapshot.partN.json`

如果使用全书聚合模式 `--segment-index 0` 且 `provider=openai`，还会在 `segments/` 下缓存每段图谱：

- `segments/graph_scan.partN.md`
- `segments/graph_snapshot.partN.json`

## 目录结构

- `src/novel_graph/io/`
  输入解析与输出写盘
- `src/novel_graph/services/`
  LLM 客户端、提示词读取
- `src/novel_graph/analysis/`
  图谱抽取、图谱归约、启发式规则、图谱摘要
- `src/novel_graph/pipelines/`
  `direct` / `graph` 两条执行链
- `src/novel_graph/rendering/`
  Markdown 渲染
- `src/novel_graph/prompts/`
  提示词模板
- `src/novel_graph/resources/`
  扫书规范、术语、文风参考
- `tests/`
  CLI、图谱、LLM 配置等测试

## LLM 配置

复制配置文件：

```bash
cp .env.example .env
```

`.env` 示例：

```env
# 默认 API：给 direct 和其他非图谱流程使用
OPENAI_API_KEY=your_main_key
OPENAI_BASE_URL=https://your-main-2api.example.com/v1
OPENAI_MODEL=gpt-5.4

# 可选：图谱提取 / 图谱归约专用 API
# 没配时，graph 流程自动回退到 OPENAI_*
GRAPH_OPENAI_API_KEY=your_graph_key
GRAPH_OPENAI_BASE_URL=https://your-cheap-2api.example.com/v1
GRAPH_OPENAI_MODEL=qwen-plus
```

说明：

- `OPENAI_*`
  默认给 `direct` 和非图谱流程使用
- `GRAPH_OPENAI_*`
  只给 `graph` 流程使用，包括：
  - 分段图谱抽取
  - 分段图谱归约
- 如果 `GRAPH_OPENAI_*` 没配，`graph` 会自动回退到 `OPENAI_*`
- `--model` 是全局覆盖参数
  如果你想让 `direct` 和 `graph` 用不同模型，不要传 `--model`，直接靠两组环境变量控制

## CLI

主命令：

```bash
uv run novel-graph scan <input_path> [options]
```

核心参数：

- `--mode`
  `direct` / `graph` / `both`
- `--provider`
  `heuristic` / `openai`
- `--output-dir`
  输出目录
- `--model`
  全局覆盖模型名
- `--segment-tokens`
  分段近似 token 上限，默认 `40000`
- `--segment-index`
  从 `1` 开始选择某一段；设为 `0` 表示聚合所有分段

## 推荐工作流

### 1. 快速验证环境

先准备一个短文本文件，例如 `quickstart.md`：

```text
主角穿越后进入王朝线，先做交易积累资源，再逐步扩张势力。
```

然后运行：

```bash
uv run novel-graph scan quickstart.md --mode both --provider heuristic --output-dir output_quickstart
```

适合检查：

- 安装是否正常
- CLI 是否能运行
- 输出目录是否正常生成

### 2. 单段调试图谱

```bash
uv run novel-graph scan "../你的小说.epub" --mode graph --provider openai --segment-tokens 4000 --segment-index 1 --output-dir output
```

适合检查：

- 当前提示词是否稳定
- 图谱 JSON 是否符合预期
- 主角 / 地点 / 剧情线抽取是否正常

### 3. 全书图谱聚合

```bash
uv run novel-graph scan "../你的小说.epub" --mode graph --provider openai --segment-tokens 40000 --segment-index 0 --output-dir output
```

这是当前最推荐的完整流程。

它会：

1. 按章节近似分段
2. 对每段抽局部知识图谱
3. 归约为整本书的总图谱
4. 输出 `graph_scan.md` 和 `graph_snapshot.json`

### 4. 同时生成 direct + graph

```bash
uv run novel-graph scan "../你的小说.epub" --mode both --provider openai --segment-tokens 40000 --segment-index 0 --output-dir output
```

适合对比：

- 纯提示词扫书
- 图谱驱动扫书

## graph 流程现在会输出什么

`graph_snapshot.json` 的 `metadata` 中，重点字段包括：

- `protagonist`
- `protagonist_profile`
- `character_profiles`
- `heroine_profiles`
- `supporting_profiles`
- `location_profiles`
- `faction_profiles`
- `plot_threads`
- `relationship_highlights`
- `worldline_order`
- `segment_overview`
- `graph_stats`

对应的 `graph_scan.md` 不再只是“男主 / 女主 / 后宫候选”，而会显式渲染：

- 世界线推进
- 剧情线索
- 关键地点
- 关键势力
- 高频关系边
- 关键配角 / 核心人物

这也是后续“原文简单解说”的基础。

## heuristic 与 openai 的区别

### heuristic

优点：

- 不需要 API
- 可快速离线验证

限制：

- 仍然偏启发式
- 对整本长篇、复杂 EPUB、跨世界线结构不够稳
- 更适合本地 smoke test，不适合最终图谱

### openai

优点：

- 支持分段图谱抽取与跨段归约
- 能保留更多人物、地点、势力、剧情线
- 更适合真实 EPUB 和后续解说工作流

限制：

- 消耗 token
- 对提示词质量和模型稳定性敏感

## 当前推荐配置

如果你想压低图谱成本，推荐这样分流：

- `direct` 走质量更高的默认 API
- `graph` 走更便宜、上下文更扛的大模型 API

也就是：

- `OPENAI_*` 配贵一点的
- `GRAPH_OPENAI_*` 配便宜一点的

## 测试

运行全部测试：

```bash
uv run pytest
```

如果只想测图谱和 CLI：

```bash
uv run pytest tests/test_graph.py tests/test_cli.py tests/test_llm_client.py
```

## 当前限制

- `--model` 还是全局覆盖，不区分 direct / graph
- 单个分段里如果正文证据不足，主角识别仍可能回退到保守值
- `graph_scan.md` 仍然带有扫书口吻；后续可以继续拆出“纯图谱摘要”和“原文简单解说稿”两个单独渲染器
- `graph_scan.md` 目前是图谱驱动的 markdown 视图，不是可视化关系图

## Roadmap

- [ ] 基于 `graph_snapshot.json` 单独生成“原文简单解说”
- [ ] 图谱可视化
- [ ] 书评 / 长评生成
- [ ] 更稳定的人物别名归一
- [ ] 更细粒度的剧情阶段抽取
