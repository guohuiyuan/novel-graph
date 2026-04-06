你将根据“小说正文分段”直接生成一份局部知识图谱 JSON。

目标不是普通摘要，而是参考 MiroFish 的图谱思路，把当前正文分段抽成后续可复用的“原文知识图谱”：
1. 先抽取人物、地点、势力、剧情线、关键关系。
2. 再把这些实体补成可复用档案。
3. 最后输出结构化 JSON，供后续两个下游同时使用：
   - 扫书/卖点总结
   - 原文简单解说

【下游风格参考，仅作辅助】  
{requirements}

【术语参考】  
{term_reference}

【硬性要求】
1. 只输出 JSON，不要输出 Markdown，不要写解释。
2. 这是“分段抽取”，只能基于当前分段正文，不要脑补全书后续。
3. 图谱必须覆盖四类核心信息：
   - `character_profiles`: 人物
   - `location_profiles`: 地点 / 区域 / 世界线落点
   - `faction_profiles`: 势力 / 家族 / 阵营 / 组织
   - `plot_threads`: 当前分段里稳定成立的剧情线 / 任务线 / 冲突线
4. 不要只盯着“男主/女主”，即使是后宫文，也必须保留大量原文人物、情节、地点。
5. 若能明确识别主角，请填写 `protagonist` 与 `protagonist_profile`；若证据不足可写 `待复核`。
6. 若人物只是称谓、头衔、泛指身份，没有稳定人名，不要强行当作独立人物；必要时可把称谓放进 `aliases`。
7. 地点、势力、剧情线不能因为“不是人”就丢掉。后续原文解说需要这些信息。
8. `relationship_highlights` 不只限于爱情关系，也可以是敌对、师徒、联盟、统属、绑定、交易、发生于等关系。
9. 如果当前分段明显存在情感线/后宫线，可在人物档案里用 `is_romance_interest=true` 标记；否则保持 `false`。
10. 不要硬编码题材。任何小说 EPUB 都要按“正文证据”抽取。
11. `summary` / `relation_summary` 必须是可复用的自然语言短描述，不要只堆标签。
12. `segment_overview` 要总结这一分段涉及的世界线推进，便于后续跨段归约。
13. 不要把 `待复核` / `待识别` / `未知` 当成实体名字写进 `character_profiles`、`location_profiles`、`faction_profiles`、`plot_threads`。字段可待复核，但实体名不能是占位词。
14. 如果当前分段无法稳定识别主角姓名，`protagonist` 可以写 `待复核`，但不要强行把明显配角猜成主角。

【字段说明】
- `importance`: `lead` / `major` / `supporting` / `minor`
- `entity_type`: 只在实体档案里使用，建议为 `character` / `location` / `faction`
- `tags`: 卖点标签、身份标签、剧情标签
- `risk_tags`: 口味提示、雷点提示、或 `待复核`

【JSON Schema】
```json
{{
  "method": "mirofish-llm-graph",
  "profile_method": "llm chunk -> story graph",
  "protagonist": "主角姓名或待复核",
  "heroine_pool_estimate": 0,
  "chunk_count": 1,
  "source_segments": 1,
  "worldline_order": ["主世界", "古代王朝"],
  "segment_overview": [
    {{
      "label": "古代王朝",
      "summary": "这一阶段发生了什么",
      "heroine_focus": "若有明显情感焦点可写，没有就空字符串",
      "key_characters": ["人物A", "人物B"],
      "key_locations": ["地点A"],
      "key_events": ["剧情线A", "剧情线B"]
    }}
  ],
  "protagonist_profile": {{
    "name": "主角姓名",
    "entity_type": "character",
    "role": "主角身份",
    "worldline": "主世界/常驻世界线",
    "chapter_hits": 20,
    "score": 100,
    "summary": "2-4句角色简介",
    "tags": ["主角标签"],
    "risk_tags": [],
    "aliases": ["别名/化名"],
    "relation_summary": "",
    "evidence": "关键原文短句",
    "gender": "male/female/unknown",
    "importance": "lead",
    "is_protagonist": true,
    "is_romance_interest": false
  }},
  "character_profiles": [
    {{
      "name": "人物姓名",
      "entity_type": "character",
      "role": "公主/师尊/队友/反派/舰灵等",
      "worldline": "所属世界线",
      "chapter_hits": 6,
      "score": 82,
      "summary": "2-4句人物简介",
      "tags": ["身份标签", "剧情标签"],
      "risk_tags": ["待复核"],
      "aliases": ["称谓/头衔"],
      "relation_summary": "与主角或主线的关系",
      "evidence": "关键原文短句",
      "gender": "male/female/unknown",
      "importance": "major",
      "is_protagonist": false,
      "is_romance_interest": false
    }}
  ],
  "location_profiles": [
    {{
      "name": "地点名",
      "entity_type": "location",
      "role": "皇城/宗门/星舰/秘境/都市区域",
      "worldline": "所属世界线",
      "chapter_hits": 4,
      "score": 60,
      "summary": "地点定位和剧情作用",
      "tags": ["地点标签"],
      "risk_tags": [],
      "aliases": [],
      "relation_summary": "与主线/人物的关联",
      "evidence": "关键原文短句",
      "importance": "major"
    }}
  ],
  "faction_profiles": [
    {{
      "name": "势力名",
      "entity_type": "faction",
      "role": "皇室/宗门/军团/公司/家族",
      "worldline": "所属世界线",
      "chapter_hits": 4,
      "score": 58,
      "summary": "势力定位和作用",
      "tags": ["势力标签"],
      "risk_tags": [],
      "aliases": [],
      "relation_summary": "与主角/剧情的关系",
      "evidence": "关键原文短句",
      "importance": "supporting"
    }}
  ],
  "plot_threads": [
    {{
      "title": "剧情线标题",
      "worldline": "所属世界线",
      "stage": "建立关系/冲突升级/夺权扩张/探索秘境等",
      "summary": "2-4句剧情线简介",
      "importance": 80,
      "involved_characters": ["人物A", "人物B"],
      "key_locations": ["地点A"],
      "related_factions": ["势力A"],
      "tags": ["剧情标签"],
      "evidence": "关键原文短句"
    }}
  ],
  "relationship_highlights": [
    {{
      "source": "实体A",
      "target": "实体B",
      "relation": "敌对/联盟/绑定/暧昧/统属/发生于/交易等",
      "chapter_hits": 3,
      "weight": 30,
      "evidence": "关键原文短句",
      "tags": ["关系标签"]
    }}
  ]
}}
```

【规模要求】
1. `character_profiles` 优先保留当前分段最稳定、最有剧情价值的人物，建议 8-20 个。
2. `location_profiles` 建议 3-10 个。
3. `faction_profiles` 建议 2-8 个。
4. `plot_threads` 建议 3-10 条。
5. `relationship_highlights` 建议 8-20 条。

【输入标题】
{title}

【输入正文分段】
{text_excerpt}
