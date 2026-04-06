你将根据“多个分段知识图谱 JSON”合并出一份整本小说级别的总知识图谱 JSON。

这一轮相当于参考 MiroFish 的后半段工作流：
1. 读取各段实体与关系档案；
2. 做跨段别名归一、身份去重、世界线排序；
3. 输出可以直接服务后续扫书与原文简明解说的总图谱。

【硬性要求】
1. 只输出 JSON，不要输出 Markdown，不要写解释。
2. 你面对的是“分段图谱”，不是正文。只能依据已有图谱归并，不能凭空补正文细节。
3. 不要把图谱压缩回“只有男主和几个女主”。总图谱必须继续保留：
   - 大量人物
   - 核心地点
   - 关键势力
   - 主线剧情线
   - 关键关系
4. 同一人物若同时出现真名、化名、头衔、家世描述，必须归并为一个实体：
   - `name` 保留最稳定、最像正式称呼的版本
   - 其余写进 `aliases`
5. `character_profiles` 要优先覆盖全书核心人物，而不是只看某一段热度。
6. `plot_threads` 需要保留跨世界线、跨阶段的主线推进。
7. `segment_overview` 要按全书推进顺序总结大地图演化。
8. 若小说确实是后宫/恋爱向，才保留 `heroine_pool_estimate` 的规模判断；否则可写 0。

【输出 Schema】
```json
{{
  "method": "mirofish-llm-graph-reduced",
  "profile_method": "llm segment story graph -> reduce -> scan",
  "protagonist": "主角姓名或待复核",
  "heroine_pool_estimate": 60,
  "chunk_count": 93,
  "source_segments": 93,
  "worldline_order": ["主世界", "古代王朝", "末世废土", "修真世界"],
  "segment_overview": [
    {{
      "label": "古代王朝",
      "summary": "该阶段的剧情推进摘要",
      "heroine_focus": "若该线有明显情感焦点则填写",
      "key_characters": ["人物A", "人物B"],
      "key_locations": ["地点A"],
      "key_events": ["剧情线A", "剧情线B"]
    }}
  ],
  "protagonist_profile": {{
    "name": "主角姓名",
    "entity_type": "character",
    "role": "主角身份",
    "worldline": "常驻主线",
    "chapter_hits": 900,
    "score": 100,
    "summary": "2-4句全书级人物简介",
    "tags": ["主角标签"],
    "risk_tags": [],
    "aliases": ["别名"],
    "relation_summary": "",
    "evidence": "最关键证据",
    "gender": "male/female/unknown",
    "importance": "lead",
    "is_protagonist": true,
    "is_romance_interest": false,
    "segment_indexes": [1, 2, 3]
  }},
  "character_profiles": [
    {{
      "name": "人物姓名",
      "entity_type": "character",
      "role": "人物身份",
      "worldline": "所属世界线",
      "chapter_hits": 120,
      "score": 92,
      "summary": "全书级角色简介",
      "tags": ["身份标签", "剧情标签"],
      "risk_tags": [],
      "aliases": ["称谓"],
      "relation_summary": "与主角或主线的关系",
      "evidence": "关键证据",
      "gender": "male/female/unknown",
      "importance": "major",
      "is_protagonist": false,
      "is_romance_interest": false,
      "segment_indexes": [2, 3, 4]
    }}
  ],
  "location_profiles": [
    {{
      "name": "地点名",
      "entity_type": "location",
      "role": "皇城/星舰/宗门/秘境",
      "worldline": "所属世界线",
      "chapter_hits": 50,
      "score": 70,
      "summary": "地点定位与作用",
      "tags": ["地点标签"],
      "risk_tags": [],
      "aliases": [],
      "relation_summary": "与主线的关系",
      "evidence": "关键证据",
      "importance": "major",
      "segment_indexes": [5, 6]
    }}
  ],
  "faction_profiles": [
    {{
      "name": "势力名",
      "entity_type": "faction",
      "role": "宗门/王朝/军团/公司/家族",
      "worldline": "所属世界线",
      "chapter_hits": 48,
      "score": 68,
      "summary": "势力定位与作用",
      "tags": ["势力标签"],
      "risk_tags": [],
      "aliases": [],
      "relation_summary": "与主角或剧情的关系",
      "evidence": "关键证据",
      "importance": "supporting",
      "segment_indexes": [8, 9]
    }}
  ],
  "plot_threads": [
    {{
      "title": "剧情线标题",
      "worldline": "所属世界线",
      "stage": "起势/扩张/冲突升级/结盟/收束",
      "summary": "全书级剧情线简介",
      "importance": 88,
      "involved_characters": ["人物A", "人物B"],
      "key_locations": ["地点A"],
      "related_factions": ["势力A"],
      "tags": ["剧情标签"],
      "segment_indexes": [10, 11, 12],
      "evidence": "关键证据"
    }}
  ],
  "relationship_highlights": [
    {{
      "source": "实体A",
      "target": "实体B",
      "relation": "敌对/联盟/绑定/暧昧/统属/发生于等",
      "chapter_hits": 16,
      "weight": 120,
      "evidence": "关键证据",
      "tags": ["关系标签"],
      "segment_indexes": [12, 13]
    }}
  ]
}}
```

【保留规模】
1. `character_profiles` 尽量保留 20-40 个核心人物。
2. `location_profiles` 尽量保留 8-20 个关键地点。
3. `faction_profiles` 尽量保留 6-20 个关键势力。
4. `plot_threads` 尽量保留 8-24 条主线/支线。
5. `relationship_highlights` 尽量保留 20-40 条关键关系。

【输入标题】
{title}

【输入分段图谱 JSON】
{graph_json}
