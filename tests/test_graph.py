from pathlib import Path

import pytest

from novel_graph.analysis.llm_graph import build_llm_graph, graph_from_payload, reduce_llm_graphs
from novel_graph.analysis.simple_graph import build_lightweight_graph, summarize_graph
from novel_graph.domain.models import NovelInput, Provider
from novel_graph.pipelines.graph_scan import run_graph_scan, run_graph_scan_segments
from novel_graph.rendering.markdown_renderer import heuristic_graph_scan_markdown

SAMPLE_TEXT = """第一章 初见云绮君
秦烽在大齐王都见到了云绮君。云绮君身为公主，对秦烽说道愿意合作。

第二章 欧阳芷瑜心动
欧阳芷瑜在宴会上陪着秦烽，心动之余主动示好。秦烽看着欧阳芷瑜点头。

第三章 再会云绮君
秦烽再次见到云绮君，公主云绮君与秦烽并肩而行，气氛暧昧。

第四章 羽澶现身
舰灵羽澶在星舰中苏醒。羽澶陪伴秦烽出手，舰灵羽澶对秦烽说道已经锁定目标。
"""


def test_build_lightweight_graph_uses_character_candidates() -> None:
    graph = build_lightweight_graph(SAMPLE_TEXT)

    labels = {node.label for node in graph.nodes}
    assert "秦烽" in labels
    assert "云绮君" in labels
    assert "欧阳芷瑜" in labels
    assert "说着" not in labels

    assert graph.metadata["protagonist"] == "秦烽"
    heroine_names = {item["name"] for item in graph.metadata["heroine_candidates"]}
    assert "云绮君" in heroine_names

    summary = summarize_graph(graph)
    assert "秦烽" in summary
    assert "云绮君" in summary


def test_heuristic_graph_scan_markdown_renders_graph_sections(tmp_path: Path) -> None:
    novel_input = NovelInput(
        source_path=tmp_path / "sample.md",
        title="示例小说",
        raw_text=SAMPLE_TEXT,
        author="测试作者",
    )
    graph = build_lightweight_graph(SAMPLE_TEXT)

    markdown = heuristic_graph_scan_markdown(novel_input, graph)

    assert "原文知识图谱" in markdown
    assert "## 男主" in markdown
    assert "## 女主" in markdown
    assert "云绮君" in markdown
    assert "高频关系边" in markdown
    assert "剧情线索" in markdown
    assert "关键地点" in markdown
    assert "雷点/提示：" in markdown


def test_graph_from_payload_builds_profiles_and_edges() -> None:
    graph = graph_from_payload(
        {
            "method": "mirofish-llm-graph-reduced",
            "protagonist": "秦烽",
            "heroine_pool_estimate": 12,
            "worldline_order": ["诸天常驻", "古代王朝"],
            "segment_overview": [
                {
                    "label": "古代王朝",
                    "summary": "男主先在古代线扶龙起家。",
                    "heroine_focus": "羽澶",
                    "key_characters": ["秦烽", "羽澶"],
                    "key_locations": ["大齐王都"],
                    "key_events": ["扶龙起家"],
                }
            ],
            "protagonist_profile": {
                "name": "秦烽",
                "role": "男主",
                "summary": "诸天推土机男主。",
                "tags": ["诸天推土机"],
                "risk_tags": ["无明显六雷硬证据"],
                "evidence": "秦烽如是说。",
            },
            "heroine_profiles": [
                {
                    "name": "羽澶",
                    "role": "舰灵",
                    "worldline": "诸天常驻",
                    "summary": "绑定在男主身边的舰灵女主。",
                    "tags": ["器灵/舰灵", "伴生女主"],
                    "risk_tags": ["无明显六雷硬证据"],
                    "relation_summary": "与男主高频绑定。",
                    "evidence": "舰灵羽澶在星舰中苏醒。",
                    "score": 90,
                }
            ],
            "character_profiles": [
                {
                    "name": "云绮君",
                    "entity_type": "character",
                    "role": "公主",
                    "worldline": "古代王朝",
                    "summary": "古代线的高位人物。",
                    "tags": ["高位角色"],
                    "evidence": "云绮君身为公主。",
                    "score": 76,
                    "importance": "major",
                }
            ],
            "supporting_profiles": [
                {
                    "name": "赵元谨",
                    "role": "皇帝",
                    "summary": "大齐皇帝。",
                    "tags": ["关键配角"],
                    "risk_tags": ["待复核"],
                    "evidence": "赵元谨主动示好。",
                    "score": 40,
                }
            ],
            "location_profiles": [
                {
                    "name": "大齐王都",
                    "entity_type": "location",
                    "role": "皇城",
                    "worldline": "古代王朝",
                    "summary": "古代线的核心舞台。",
                    "tags": ["王朝核心地带"],
                    "evidence": "秦烽在大齐王都见到云绮君。",
                    "score": 60,
                }
            ],
            "faction_profiles": [
                {
                    "name": "大齐皇室",
                    "entity_type": "faction",
                    "role": "皇室",
                    "worldline": "古代王朝",
                    "summary": "古代线的统治势力。",
                    "tags": ["皇室"],
                    "evidence": "云绮君身为公主。",
                    "score": 55,
                }
            ],
            "plot_threads": [
                {
                    "title": "扶龙起家",
                    "worldline": "古代王朝",
                    "stage": "起势",
                    "summary": "秦烽在古代线借势扩张。",
                    "importance": 80,
                    "involved_characters": ["秦烽", "云绮君"],
                    "key_locations": ["大齐王都"],
                    "related_factions": ["大齐皇室"],
                    "tags": ["古代扩张"],
                    "evidence": "男主先在古代线扶龙起家。",
                }
            ],
            "relationship_highlights": [
                {
                    "source": "秦烽",
                    "target": "羽澶",
                    "relation": "后宫候选",
                    "chapter_hits": 4,
                    "weight": 80,
                    "evidence": "羽澶陪伴秦烽出手。",
                    "tags": ["高频绑定"],
                }
            ],
        }
    )

    assert graph.metadata["protagonist"] == "秦烽"
    assert graph.metadata["heroine_profiles"][0]["name"] == "羽澶"
    assert graph.metadata["worldline_order"] == ["诸天常驻", "古代王朝"]
    assert graph.metadata["location_profiles"][0]["name"] == "大齐王都"
    assert graph.metadata["plot_threads"][0]["title"] == "扶龙起家"
    assert any(edge.relation == "后宫候选" for edge in graph.edges)
    assert any(node.category == "地点" and node.label == "大齐王都" for node in graph.nodes)
    assert any(node.category == "剧情" and node.label == "扶龙起家" for node in graph.nodes)


def test_run_graph_scan_openai_uses_llm_graph_payload(monkeypatch, tmp_path: Path) -> None:
    payload = {
        "protagonist": "秦烽",
        "heroine_pool_estimate": 10,
        "protagonist_profile": {
            "name": "秦烽",
            "role": "男主",
            "summary": "诸天推土机男主。",
            "tags": ["诸天推土机"],
            "risk_tags": ["无明显六雷硬证据"],
            "evidence": "秦烽如是说。",
        },
        "heroine_profiles": [
            {
                "name": "羽澶",
                "role": "舰灵",
                "worldline": "诸天常驻",
                "summary": "绑定在男主身边的舰灵女主。",
                "tags": ["器灵/舰灵"],
                "risk_tags": ["无明显六雷硬证据"],
                "relation_summary": "与男主高频绑定。",
                "evidence": "舰灵羽澶在星舰中苏醒。",
                "score": 90,
            }
        ],
        "location_profiles": [
            {
                "name": "星舰",
                "entity_type": "location",
                "role": "移动基地",
                "worldline": "诸天常驻",
                "summary": "羽澶苏醒并长期活动的地点。",
                "tags": ["常驻场景"],
                "evidence": "舰灵羽澶在星舰中苏醒。",
                "score": 62,
            }
        ],
        "plot_threads": [
            {
                "title": "舰灵绑定线",
                "worldline": "诸天常驻",
                "stage": "建立绑定",
                "summary": "羽澶与秦烽形成高频绑定。",
                "importance": 85,
                "involved_characters": ["秦烽", "羽澶"],
                "key_locations": ["星舰"],
                "related_factions": [],
                "tags": ["伴生线"],
                "evidence": "羽澶陪伴秦烽出手。",
            }
        ],
        "supporting_profiles": [],
        "relationship_highlights": [
            {
                "source": "秦烽",
                "target": "羽澶",
                "relation": "后宫候选",
                "chapter_hits": 4,
                "weight": 80,
                "evidence": "羽澶陪伴秦烽出手。",
                "tags": ["高频绑定"],
            }
        ],
    }

    def fake_generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        assert "知识图谱" in system_prompt
        assert "JSON Schema" in user_prompt
        return payload

    monkeypatch.setattr(
        "novel_graph.services.llm_client.LLMClient.generate_json",
        fake_generate_json,
    )

    novel_input = NovelInput(
        source_path=tmp_path / "sample.md",
        title="示例小说",
        raw_text=SAMPLE_TEXT,
        author="测试作者",
    )
    result = run_graph_scan(novel_input, provider=Provider.OPENAI)

    assert result.graph is not None
    assert result.graph.metadata["method"] == "mirofish-llm-graph"
    assert "羽澶" in result.markdown
    assert "图谱方法" in result.markdown
    assert "剧情线索" in result.markdown
    assert "关键地点" in result.markdown


def test_reduce_llm_graphs_merges_segment_worldlines() -> None:
    segment_graphs = [
        graph_from_payload(
            {
                "protagonist": "秦烽",
                "heroine_pool_estimate": 2,
                "worldline_order": ["古代王朝"],
                "segment_overview": [
                    {
                        "label": "古代王朝",
                        "summary": "扶龙起家。",
                        "heroine_focus": "秋韵",
                    }
                ],
                "protagonist_profile": {
                    "name": "秦烽",
                    "role": "男主",
                    "summary": "扶龙起家的两界商人。",
                    "tags": ["两界穿梭"],
                    "risk_tags": ["无明显六雷硬证据"],
                    "evidence": "秦烽在古代线扶龙。",
                },
                "heroine_profiles": [
                    {
                        "name": "秋韵",
                        "role": "侍女",
                        "worldline": "古代王朝",
                        "summary": "古代线贴身侍女。",
                        "tags": ["侍奉线"],
                        "risk_tags": ["待复核"],
                        "evidence": "照顾起居。",
                        "score": 70,
                    }
                ],
                "supporting_profiles": [],
                "relationship_highlights": [],
            }
        ),
        graph_from_payload(
            {
                "protagonist": "秦烽",
                "heroine_pool_estimate": 4,
                "worldline_order": ["末世废土"],
                "segment_overview": [
                    {
                        "label": "末世废土",
                        "summary": "在末世继续扩张势力。",
                        "heroine_focus": "林曦涵",
                    }
                ],
                "protagonist_profile": {
                    "name": "秦烽",
                    "role": "男主",
                    "summary": "末世线继续滚雪球。",
                    "tags": ["资源滚雪球"],
                    "risk_tags": ["无明显六雷硬证据"],
                    "evidence": "秦烽在末世扩张。",
                },
                "heroine_profiles": [
                    {
                        "name": "林曦涵",
                        "role": "皇后",
                        "worldline": "末世废土",
                        "summary": "末世线高位女主。",
                        "tags": ["高位女主"],
                        "risk_tags": ["无明显六雷硬证据"],
                        "evidence": "末世皇后。",
                        "score": 88,
                    }
                ],
                "supporting_profiles": [],
                "relationship_highlights": [],
            }
        ),
    ]

    novel_input = NovelInput(
        source_path=Path("sample.md"),
        title="示例小说",
        raw_text=SAMPLE_TEXT,
        author="测试作者",
    )
    graph = reduce_llm_graphs(novel_input, segment_graphs)

    assert graph.metadata["source_segments"] == 2
    assert "古代王朝" in graph.metadata["worldline_order"]
    assert "末世废土" in graph.metadata["worldline_order"]
    heroine_names = {item["name"] for item in graph.metadata["heroine_profiles"]}
    assert heroine_names == {"秋韵", "林曦涵"}


def test_run_graph_scan_segments_uses_aggregated_graph(monkeypatch, tmp_path: Path) -> None:
    def fake_build_llm_graph(novel_input: NovelInput, model: str | None = None):
        if "第1/2段" in novel_input.title:
            return graph_from_payload(
                {
                    "protagonist": "秦烽",
                    "heroine_pool_estimate": 2,
                    "worldline_order": ["古代王朝"],
                    "segment_overview": [{"label": "古代王朝", "summary": "扶龙起家。"}],
                    "protagonist_profile": {
                        "name": "秦烽",
                        "role": "男主",
                        "summary": "古代线起家。",
                        "tags": ["两界穿梭"],
                        "risk_tags": ["无明显六雷硬证据"],
                        "evidence": "扶龙。",
                    },
                    "heroine_profiles": [
                        {
                            "name": "秋韵",
                            "role": "侍女",
                            "worldline": "古代王朝",
                            "summary": "古代线女主。",
                            "tags": ["侍奉线"],
                            "risk_tags": ["待复核"],
                            "evidence": "照顾起居。",
                        }
                    ],
                    "supporting_profiles": [],
                    "relationship_highlights": [],
                }
            )
        return graph_from_payload(
            {
                "protagonist": "秦烽",
                "heroine_pool_estimate": 4,
                "worldline_order": ["末世废土"],
                "segment_overview": [{"label": "末世废土", "summary": "末世扩张。"}],
                "protagonist_profile": {
                    "name": "秦烽",
                    "role": "男主",
                    "summary": "末世线扩张。",
                    "tags": ["资源滚雪球"],
                    "risk_tags": ["无明显六雷硬证据"],
                    "evidence": "扩张。",
                },
                "heroine_profiles": [
                    {
                        "name": "林曦涵",
                        "role": "皇后",
                        "worldline": "末世废土",
                        "summary": "末世线高位女主。",
                        "tags": ["高位女主"],
                        "risk_tags": ["无明显六雷硬证据"],
                        "evidence": "皇后。",
                    }
                ],
                "supporting_profiles": [],
                "relationship_highlights": [],
            }
        )

    monkeypatch.setattr("novel_graph.pipelines.graph_scan.build_llm_graph", fake_build_llm_graph)
    monkeypatch.setattr(
        "novel_graph.pipelines.graph_scan.reduce_llm_graphs",
        lambda novel_input, graphs, model=None: reduce_llm_graphs(novel_input, graphs),
    )

    segment_inputs = [
        NovelInput(
            source_path=tmp_path / "sample.md",
            title="示例小说（第1/2段）",
            raw_text=SAMPLE_TEXT,
            author="测试作者",
        ),
        NovelInput(
            source_path=tmp_path / "sample.md",
            title="示例小说（第2/2段）",
            raw_text=SAMPLE_TEXT,
            author="测试作者",
        ),
    ]
    novel_input = NovelInput(
        source_path=tmp_path / "sample.md",
        title="示例小说",
        raw_text=SAMPLE_TEXT,
        author="测试作者",
    )
    result = run_graph_scan_segments(novel_input, segment_inputs, provider=Provider.OPENAI)

    assert result.graph is not None
    assert result.graph.metadata["source_segments"] == 2
    assert "世界线推进" in result.markdown
    assert "原文知识图谱" in result.markdown
    assert "林曦涵" in result.markdown


def test_build_llm_graph_auto_splits_on_gateway_timeout(
    monkeypatch, tmp_path: Path
) -> None:
    split_text = """Chapter 1
Qin Feng meets Yun Xuanjun in the court and starts to cooperate with her.

Chapter 2
Qin Feng spends more time with Yun Xuanjun and stabilizes his foothold.

Chapter 3
Yu Meng wakes in the starship and starts binding tightly to Qin Feng.

Chapter 4
Qin Feng and Yu Meng continue acting together and expand to the next stage.
"""

    payload_a = {
        "protagonist": "Qin Feng",
        "heroine_pool_estimate": 1,
        "protagonist_profile": {
            "name": "Qin Feng",
            "role": "male lead",
            "summary": "A cross-world protagonist.",
            "tags": ["cross-world"],
            "risk_tags": ["none"],
            "evidence": "Qin Feng keeps expanding.",
        },
        "heroine_profiles": [
            {
                "name": "Yun Xuanjun",
                "role": "princess",
                "worldline": "ancient court",
                "summary": "A high-value heroine from the court line.",
                "tags": ["royal"],
                "risk_tags": ["none"],
                "relation_summary": "Works with Qin Feng early on.",
                "evidence": "She cooperates with Qin Feng.",
                "score": 82,
            }
        ],
        "supporting_profiles": [],
        "relationship_highlights": [
            {
                "source": "Qin Feng",
                "target": "Yun Xuanjun",
                "relation": "core heroine",
                "chapter_hits": 2,
                "weight": 50,
                "evidence": "They cooperate in the court.",
                "tags": ["binding"],
            }
        ],
        "worldline_order": ["ancient court"],
        "segment_overview": [{"label": "ancient court", "summary": "Early court expansion."}],
    }
    payload_b = {
        "protagonist": "Qin Feng",
        "heroine_pool_estimate": 2,
        "protagonist_profile": {
            "name": "Qin Feng",
            "role": "male lead",
            "summary": "A cross-world protagonist.",
            "tags": ["cross-world"],
            "risk_tags": ["none"],
            "evidence": "Qin Feng keeps expanding.",
        },
        "heroine_profiles": [
            {
                "name": "Yu Meng",
                "role": "ship spirit",
                "worldline": "starship",
                "summary": "A bound heroine from the starship line.",
                "tags": ["ship spirit"],
                "risk_tags": ["none"],
                "relation_summary": "Stays bound to Qin Feng.",
                "evidence": "Yu Meng wakes in the starship.",
                "score": 88,
            }
        ],
        "supporting_profiles": [],
        "relationship_highlights": [
            {
                "source": "Qin Feng",
                "target": "Yu Meng",
                "relation": "core heroine",
                "chapter_hits": 2,
                "weight": 60,
                "evidence": "They keep acting together.",
                "tags": ["binding"],
            }
        ],
        "worldline_order": ["starship"],
        "segment_overview": [{"label": "starship", "summary": "Starship expansion."}],
    }

    def fake_generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        if '"segment_graphs"' in user_prompt:
            raise RuntimeError("504 Gateway time-out")
        if "Chapter 1" in user_prompt and "Chapter 4" in user_prompt:
            raise RuntimeError("504 Gateway time-out")
        if "Chapter 1" in user_prompt or "Chapter 2" in user_prompt:
            return payload_a
        if "Chapter 3" in user_prompt or "Chapter 4" in user_prompt:
            return payload_b
        raise AssertionError(user_prompt)

    monkeypatch.setattr(
        "novel_graph.services.llm_client.LLMClient.generate_json",
        fake_generate_json,
    )

    novel_input = NovelInput(
        source_path=tmp_path / "sample.md",
        title="split sample",
        raw_text=split_text,
        author="tester",
    )

    graph = build_llm_graph(
        novel_input,
        split_token_budget=20,
        min_split_token_budget=8,
        max_split_depth=2,
    )

    heroine_names = {item["name"] for item in graph.metadata["heroine_profiles"]}
    assert heroine_names == {"Yun Xuanjun", "Yu Meng"}
    assert graph.metadata["method"] == "mirofish-llm-graph-split-reduced"
    assert graph.metadata["source_segments"] == 1
    assert graph.metadata["chunk_count"] >= 2


def test_build_llm_graph_raises_on_gateway_placeholder_payload(monkeypatch, tmp_path: Path) -> None:
    payload = {
        "protagonist": "待识别",
        "protagonist_profile": {
            "name": "待识别",
            "role": "男主",
            "summary": "输入正文分片已被占位符替代，无法识别。",
            "evidence": "???? ???",
        },
        "heroine_profiles": [],
        "supporting_profiles": [],
        "relationship_highlights": [],
    }

    def fake_generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        return payload

    monkeypatch.setattr(
        "novel_graph.services.llm_client.LLMClient.generate_json",
        fake_generate_json,
    )

    novel_input = NovelInput(
        source_path=tmp_path / "sample.md",
        title="示例小说",
        raw_text=SAMPLE_TEXT,
        author="测试作者",
    )

    with pytest.raises(RuntimeError, match="第三方网关.*损坏中文输入/输出"):
        build_llm_graph(novel_input)
