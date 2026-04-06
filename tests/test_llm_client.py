from novel_graph.services.llm_client import LLMClient


def test_llm_client_uses_graph_profile_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "default-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://default.example.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "default-model")
    monkeypatch.setenv("GRAPH_OPENAI_API_KEY", "graph-key")
    monkeypatch.setenv("GRAPH_OPENAI_BASE_URL", "https://graph.example.com/v1")
    monkeypatch.setenv("GRAPH_OPENAI_MODEL", "graph-model")

    graph_client = LLMClient(profile="graph")
    default_client = LLMClient()

    assert graph_client.api_key == "graph-key"
    assert graph_client.base_url == "https://graph.example.com/v1"
    assert graph_client.model == "graph-model"

    assert default_client.api_key == "default-key"
    assert default_client.base_url == "https://default.example.com/v1"
    assert default_client.model == "default-model"


def test_llm_client_graph_profile_falls_back_to_default_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "default-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://default.example.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "default-model")
    monkeypatch.delenv("GRAPH_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GRAPH_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("GRAPH_OPENAI_MODEL", raising=False)

    graph_client = LLMClient(profile="graph")

    assert graph_client.api_key == "default-key"
    assert graph_client.base_url == "https://default.example.com/v1"
    assert graph_client.model == "default-model"
