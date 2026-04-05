你将根据“多个分段知识图谱 JSON”合并出一份可以概括整本小说的总知识图谱 JSON。

这一步相当于参考 MiroFish 的后半段工作流：
1. 读取各段人物与关系档案；
2. 做跨段别名归一、身份去重、世界线排序；
3. 输出全书级图谱，供扫书成稿使用。

【硬性要求】
1. 只输出 JSON，不要输出 Markdown，不要写解释。
2. 你面对的是“分段图谱”，不是正文。你只能依据这些图谱做跨段归并，不能凭空补正文中未出现的细节。
3. 这一步最重要的任务是“同人归一”：
   - 同一人物如果同时出现真实姓名、化名、头衔、家世描述，必须合并为一个节点
   - `name` 保留最稳定、最像真实人名的版本
   - 其余称谓放进 `aliases`
4. 不要把下列内容保留为独立人物，除非它们明确就是有人格的角色：
   - 身份描述：张家次女、某家千金、某皇后、某侍女
   - 抽象概念：计划、时空、法则、能量、利益、成就
   - 组织/地图：宗门、帝国、界天、国度、世界、星舰、势力
5. `heroine_profiles` 要尽量覆盖全书核心女主池，而不是只盯一段。可以多保留，但必须按全书重要性排序。
6. `relationship_highlights` 优先保留和男主直接相关、能概括全书路线的边。
7. 你要输出足够细粒度的信息，让最后的扫书可以同时看到：
   - 男主路线
   - 各世界线的高位女主
   - 后宫池规模
   - 重要配角与对手
   - 世界线推进顺序
8. `segment_overview` 需要把整本书的大地图推进概括出来，每条 1-3 句，按时间顺序排序。

【输出 Schema】
```json
{{
  "method": "mirofish-llm-graph-reduced",
  "profile_method": "llm segment graph -> reduce -> scan",
  "protagonist": "男主姓名",
  "heroine_pool_estimate": 60,
  "chunk_count": 93,
  "source_segments": 93,
  "worldline_order": ["主世界", "古代王朝", "末世废土", "星濛世界", "修真世界", "星海大世界"],
  "segment_overview": [
    {{
      "label": "古代王朝",
      "summary": "这一阶段的主线推进摘要",
      "heroine_focus": "该世界线的核心女主/准女主"
    }}
  ],
  "protagonist_profile": {{
    "name": "男主姓名",
    "role": "男主",
    "worldline": "全书主线/诸天常驻",
    "chapter_hits": 900,
    "score": 100,
    "summary": "2-4句全书级男主简介",
    "tags": ["诸天推土机", "资源滚雪球", "高位女主收集"],
    "risk_tags": ["无明显六雷硬证据"],
    "aliases": ["化名/别称"],
    "evidence": "最能证明男主路线的片段级证据"
  }},
  "heroine_profiles": [
    {{
      "name": "女主姓名",
      "role": "舰灵/皇后/圣女/师尊等",
      "worldline": "所属世界线",
      "chapter_hits": 120,
      "score": 92,
      "summary": "2-4句全书级人物简介",
      "tags": ["高位女主", "皇室线"],
      "risk_tags": ["无明显六雷硬证据"],
      "aliases": ["称谓/头衔/化名"],
      "segment_indexes": [1, 2, 3],
      "relation_summary": "与男主的全书关系线",
      "evidence": "最关键证据"
    }}
  ],
  "supporting_profiles": [
    {{
      "name": "关键配角姓名",
      "role": "身份",
      "worldline": "所属世界线",
      "chapter_hits": 60,
      "score": 60,
      "summary": "1-3句全书级配角简介",
      "tags": ["关键配角"],
      "risk_tags": ["待复核"],
      "aliases": ["称谓/头衔"],
      "segment_indexes": [5, 6],
      "relation_summary": "与男主的关系",
      "evidence": "关键证据"
    }}
  ],
  "relationship_highlights": [
    {{
      "source": "人物A",
      "target": "人物B",
      "relation": "后宫候选/深度绑定/政略联姻/师徒转道侣/敌转后宫/核心盟友等",
      "chapter_hits": 80,
      "weight": 160,
      "evidence": "关键证据",
      "tags": ["高频绑定", "暧昧"],
      "segment_indexes": [10, 11, 12]
    }}
  ]
}}
```

【排序要求】
1. `worldline_order` 按全书推进顺序排序。
2. `heroine_profiles` 按全书重要性排序，不要只按某一段热度排序。
3. `supporting_profiles` 优先保留：
   - 世界线关键盟友
   - 关键反派/对手
   - 能概括男主扩张路线的人物
4. `relationship_highlights` 至少要覆盖：
   - 男主与核心常驻女主
   - 男主与世界线标志性女主
   - 男主与首个关键盟友/首个关键对手

【输入标题】
{title}

【输入分段图谱 JSON】
{graph_json}
