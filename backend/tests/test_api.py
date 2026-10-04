"""
Tests for the Flask API (Phase 6), using Flask's built-in test client
(no real server or browser needed).
"""

import pytest

import ai.nl_to_regex as nl_to_regex
import app as app_module


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)   # start with AI switched off
    app_module.app.config["TESTING"] = True
    app_module.ai_request_times.clear()                 # every test starts with no AI requests
    return app_module.app.test_client()


def test_home_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"AutomataAI" in response.data


def test_convert_returns_every_stage(client):
    data = client.post("/api/convert", json={"regex": "(a|b)*abb"}).get_json()
    assert data["parse"]["postfix"] == "ab|*a.b.b."
    assert len(data["nfa"]["states"]) == 14
    assert data["dfa"]["states"] == ["A", "B", "C", "D", "E"]
    assert len(data["dfa"]["subset_table"]) == 5
    assert len(data["min_dfa"]["states"]) == 4
    assert data["min_dfa"]["table_states"] == ["A", "B", "C", "D", "E"]


def test_convert_invalid_regex_gives_400_with_message(client):
    response = client.post("/api/convert", json={"regex": "a||b"})
    assert response.status_code == 400
    assert "left side" in response.get_json()["error"]
    assert response.get_json()["position"] == 3


def test_convert_rejects_too_long_regex(client):
    response = client.post("/api/convert", json={"regex": "a" * 500})
    assert response.status_code == 400


def test_simulate(client):
    data = client.post("/api/simulate", json={"regex": "(a|b)*abb", "string": "aabb"}).get_json()
    assert data["accepted"]
    assert len(data["path"]) == 5


def test_simulate_epsilon_means_empty_string(client):
    data = client.post("/api/simulate", json={"regex": "a*", "string": "ε"}).get_json()
    assert data["accepted"]


def test_equivalence(client):
    data = client.post("/api/equivalence", json={"regex1": "a*", "regex2": "a+"}).get_json()
    assert not data["equivalent"]
    assert data["counterexample"] == ""


def test_verify_works_without_ai(client):
    data = client.post("/api/verify", json={
        "regex": "(a|b)*abb",
        "positives": ["abb"],
        "negatives": ["ab"],
        "expected": "(a|b)*abb",
    }).get_json()
    assert data["verdict"] == "correct"


def test_ai_status_off_without_key(client):
    assert client.get("/api/ai/status").get_json()["configured"] is False


def test_ai_buttons_report_not_configured(client):
    response = client.post("/api/ai/nl-to-regex", json={"description": "ends with abb"})
    assert response.status_code == 503
    assert response.get_json()["ai_not_configured"] is True



def test_explain_without_key_gives_builtin_explanation(client):
    pipeline = client.post("/api/convert", json={"regex": "(ab)*ε"}).get_json()
    for stage, data in [
        ("postfix", pipeline["parse"]),
        ("nfa", {"steps": pipeline["nfa"]["steps"], "table": pipeline["nfa"]["table"]}),
        ("dfa", {"closures": pipeline["dfa"]["closures"], "subset_table": pipeline["dfa"]["subset_table"]}),
        ("min_dfa", {"passes": pipeline["min_dfa"]["passes"], "groups": pipeline["min_dfa"]["groups"]}),
    ]:
        response = client.post("/api/ai/explain", json={"stage": stage, "data": data, "regex": "(ab)*ε"})
        assert response.status_code == 200
        body = response.get_json()
        assert body["source"] == "built-in"
        assert "WHAT THIS STEP DOES" in body["explanation"]
    # it uses the real data, e.g. the actual postfix string
    response = client.post("/api/ai/explain", json={"stage": "postfix", "data": pipeline["parse"]})
    assert "ab.*ε." in response.get_json()["explanation"]


def test_builtin_explanations_for_simulate_and_verify(client):
    run = client.post("/api/simulate", json={"regex": "(a|b)*abb", "string": "aabb"}).get_json()
    text = client.post("/api/ai/explain", json={"stage": "simulate", "data": {"input": "aabb", **run}}).get_json()
    assert "read 'a'" in text["explanation"]
    verification = client.post("/api/verify", json={"regex": "a*", "expected": "a+"}).get_json()
    text = client.post("/api/ai/explain", json={"stage": "verify", "data": verification}).get_json()
    assert "Not equivalent" in text["explanation"]


def test_builtin_explainer_survives_bad_data(client):
    response = client.post("/api/ai/explain", json={"stage": "dfa", "data": {"subset_table": "junk"}})
    assert response.status_code == 200


def test_nl_to_regex_with_fake_llm(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key-for-tests")
    monkeypatch.setattr(nl_to_regex, "ask_llm", lambda system, message, max_tokens=None: "(a|b)*abb")
    data = client.post("/api/ai/nl-to-regex", json={"description": "ends with abb"}).get_json()
    assert data["regex"] == "(a|b)*abb"
    assert len(data["pipeline"]["min_dfa"]["states"]) == 4


# ---------------------------------------------------------------------------
# New features
# ---------------------------------------------------------------------------

def test_convert_includes_new_stages(client):
    data = client.post("/api/convert", json={"regex": "(a|b)*abb"}).get_json()
    assert data["direct_dfa"]["comparison"]["direct_states"] == 4
    assert data["direct_dfa"]["comparison"]["equivalent"] is True
    assert data["regex_back"]["verified"] is True
    assert data["properties"]["infinite"] is True
    assert data["properties"]["shortest_strings"][0] == "abb"


def test_convert_with_character_class(client):
    data = client.post("/api/convert", json={"regex": "[ab]*abb"}).get_json()
    assert data["parse"]["expanded"] == "(a|b)*abb"
    assert len(data["min_dfa"]["states"]) == 4


def test_simulate_on_nfa(client):
    data = client.post("/api/simulate", json={"regex": "(a|b)*abb", "string": "abb", "automaton": "nfa"}).get_json()
    assert data["kind"] == "nfa"
    assert data["accepted"]
    assert len(data["sets"]) == 4


def test_operations_route(client):
    data = client.post("/api/operations", json={
        "regex1": "(a|b)*abb", "regex2": "(a|b)*b", "operation": "difference",
    }).get_json()
    assert data["symbol"] == "L1 − L2"
    assert data["properties"]["empty"]          # every string ending in abb also ends in b


def test_operations_complement_with_alphabet(client):
    data = client.post("/api/operations", json={
        "regex1": "a*", "operation": "complement", "alphabet": "b",
    }).get_json()
    assert data["properties"]["shortest_strings"][0] == "b"


def test_operations_bad_input(client):
    assert client.post("/api/operations", json={"regex1": "a", "regex2": "b", "operation": "x"}).status_code == 400
    assert client.post("/api/operations", json={"regex1": "a|", "regex2": "b", "operation": "union"}).status_code == 400


def test_quiz_route(client):
    data = client.get("/api/quiz?level=easy").get_json()
    assert data["regex"]
    assert len(data["questions"]) == 8


@pytest.mark.parametrize("stage", ["direct_dfa", "regex_back", "properties"])
def test_builtin_explanations_for_new_stages(client, stage):
    pipeline = client.post("/api/convert", json={"regex": "(a|b)*abb"}).get_json()
    response = client.post("/api/ai/explain", json={"stage": stage, "data": pipeline[stage]})
    assert "WHAT THIS STEP DOES" in response.get_json()["explanation"]


def test_builtin_explanation_for_operations_and_nfa_run(client):
    operation = client.post("/api/operations", json={"regex1": "a*", "regex2": "b*", "operation": "union"}).get_json()
    text = client.post("/api/ai/explain", json={"stage": "operations", "data": operation}).get_json()["explanation"]
    assert "product automaton" in text
    run = client.post("/api/simulate", json={"regex": "ab", "string": "ab", "automaton": "nfa"}).get_json()
    text = client.post("/api/ai/explain", json={"stage": "simulate", "data": {"input": "ab", **run}}).get_json()["explanation"]
    assert "active" in text


def test_ai_test_route_without_key(client):
    response = client.post("/api/ai/test")
    assert response.status_code == 503


def test_ai_test_route_with_fake_llm(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key-for-tests")
    monkeypatch.setattr(app_module, "ask_llm", lambda system, message, max_tokens=None: "OK")
    data = client.post("/api/ai/test").get_json()
    assert data["ok"] is True and data["reply"] == "OK"


@pytest.mark.parametrize("provider", ["gemini", "groq"])
def test_free_provider_presets(monkeypatch, provider):
    from ai import llm_client
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("LLM_API_KEY", "x")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert llm_client.is_configured()
    assert llm_client.get_model() == llm_client.DEFAULT_MODELS[provider]
    assert provider in llm_client.PRESET_BASE_URLS


# ---------------------------------------------------------------------------
# Server protection: automaton size limit, AI rate limit, pipeline cache
# ---------------------------------------------------------------------------

def test_exponential_regex_is_refused_with_a_clear_message(client):
    response = client.post("/api/convert", json={"regex": "(a|b)*a" + "(a|b)" * 9})
    assert response.status_code == 400
    data = response.get_json()
    assert data["too_large"] is True
    assert "300 DFA states" in data["error"]


def test_too_large_operation_gives_400(client):
    response = client.post("/api/operations", json={
        "regex1": "(a|b)*a" + "(a|b)" * 6, "regex2": "(b*ab*ab*a)*b*", "operation": "intersection",
    })
    assert response.status_code == 400
    assert "300 DFA states" in response.get_json()["error"]


@pytest.fixture
def fake_ai(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key-for-tests")
    monkeypatch.setattr(app_module, "ask_llm", lambda system, message, max_tokens=None: "OK")
    monkeypatch.setattr(app_module, "AI_REQUESTS_PER_MINUTE", 2)
    return client


def test_ai_requests_are_rate_limited_per_visitor(fake_ai):
    visitor = {"REMOTE_ADDR": "203.0.113.5"}
    codes = [fake_ai.post("/api/ai/test", environ_base=visitor).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    # Another visitor has their own allowance.
    assert fake_ai.post("/api/ai/test", environ_base={"REMOTE_ADDR": "203.0.113.6"}).status_code == 200


def test_requests_from_this_computer_are_not_rate_limited(fake_ai):
    codes = {fake_ai.post("/api/ai/test").status_code for _ in range(5)}
    assert codes == {200}


def test_builtin_explanations_are_not_rate_limited(client, monkeypatch):
    monkeypatch.setattr(app_module, "AI_REQUESTS_PER_MINUTE", 1)
    visitor = {"REMOTE_ADDR": "203.0.113.7"}
    for _ in range(3):
        response = client.post("/api/ai/explain", json={"stage": "dfa", "data": {}}, environ_base=visitor)
        assert response.status_code == 200


def test_simulate_reuses_the_built_automata(client, monkeypatch):
    calls = []
    real_pipeline = app_module.run_pipeline

    def counting_pipeline(regex):
        calls.append(regex)
        return real_pipeline(regex)

    monkeypatch.setattr(app_module, "run_pipeline", counting_pipeline)
    app_module.cached_pipeline.cache_clear()
    for text in ("abb", "aabb", "ab"):
        client.post("/api/simulate", json={"regex": "(a|b)*abb", "string": text})
    assert calls == ["(a|b)*abb"]
