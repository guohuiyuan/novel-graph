# novel-graph

`novel-graph` 是一个 Python 3.12 项目，使用 `uv` 进行包管理。

目标：先把小说输入转换成可发布的“扫书”Markdown，后续扩展书评、人物关系图、故事解说。

## 目前完成

支持两条扫书流程：

1. `direct`：直接用提示词（或启发式规则）生成扫书。
2. `graph`：先做简易知识图谱（角色共现关系），再结合图谱生成扫书。

设计上参考了 MiroFish 前半段“文本解析 -> 结构抽取 -> 图谱摘要”的思路，但实现保持最小可用，便于后续迭代。

## 项目结构

- `src/novel_graph/io/`: 输入解析（含 EPUB）和输出写入
- `src/novel_graph/analysis/`: 关键词规则与简易图谱构建
- `src/novel_graph/pipelines/`: direct / graph 两条流程
- `src/novel_graph/rendering/`: 启发式 Markdown 渲染
- `src/novel_graph/prompts/`: 提示词文件（独立维护）
- `src/novel_graph/resources/`: 扫书要求、名词解释、文风参考

## 环境

- Python `3.12`
- `uv`

## 安装

```bash
uv sync --dev
```

## 快速使用

### 启发式（本地可直接跑）

```bash
uv run novel-graph scan examples/inputs/demo_excerpt.md --mode both --provider heuristic --output-dir examples/generated
```

输出文件：

- `examples/generated/direct_scan.md`
- `examples/generated/graph_scan.md`
- `examples/generated/graph_snapshot.json`

### 用你给的 EPUB 输入示例

如果在 `novel-graph` 目录下执行：

```bash
uv run novel-graph scan "../既然回到了过去，那就改变那必将毁灭的、我推的那个Vtuber团体的未来。_匿名_20260404_113116.epub" --mode both --provider heuristic --output-dir output
```

### OpenAI 模式

先复制配置文件并填写 API：

```bash
cp .env.example .env
```

`.env` 示例：

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://jj20cm.us.ci/v1
OPENAI_MODEL=gpt-5.4
```

运行：

```bash
uv run novel-graph scan "../既然回到了过去，那就改变那必将毁灭的、我推的那个Vtuber团体的未来。_匿名_20260404_113116.epub" --mode both --provider openai --output-dir output
```

### 大文本分段扫描（推荐）

默认按约 `40000 token` 一段进行分段，可通过参数指定扫描第几段，避免整本小说一次性截断：

```bash
uv run novel-graph scan "../xxx.epub" --mode both --provider openai --segment-tokens 40000 --segment-index 1 --output-dir output
```

说明：

- `--segment-tokens`：每段近似 token 上限，默认 `40000`
- `--segment-index`：从 `1` 开始，选择要扫描的段号
- 设为 `--segment-tokens 0` 可关闭分段，直接全量输入

## 扫书规范来源

当前资源文件按以下材料提炼：

- `../扫书要求.md`
- `../后宫文防御、雷点、郁闷点和名词详解（2025）/article.md`
- `../完结粮草：60+女主的无限后宫 推背感强 曹贼爽文 356万字/article.md`

对应项目内资源：

- `src/novel_graph/resources/scan_requirements.md`
- `src/novel_graph/resources/term_reference.md`
- `src/novel_graph/resources/style_reference.md`

提示词文件：

- `src/novel_graph/prompts/direct_scan.md`
- `src/novel_graph/prompts/graph_scan.md`

## 测试

```bash
uv run pytest
```

## Roadmap

- [ ] 书评生成流程
- [ ] 人物关系图可视化
- [ ] 故事解说文案
- [ ] 更完整的实体关系抽取
