import json 
from pathlib import Path

import pytest

from graph.loader import load_graph
from graph.query import bfs_query, format_nodes, top_nodes

FIXTURE = Path(__file__).parent / "fixtures" / "graph.json"

def write_graph(tmp_path, data) -> Path:
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path

# loader tests
def test_load_graph_translates_graphify_fields():
    nodes, _ = load_graph(FIXTURE)
    assert len(nodes) == 10
    assert nodes["auth/session.py:create_session"] == {
        "id": "auth/session.py:create_session",
        "type": "code",                       # graphify's file_type
        "name": "create_session()",           # graphify's label
        "source_location": "auth/session.py:12",
    }


def test_load_graph_builds_undirected_adjacency():
    nodes, adj = load_graph(FIXTURE)
    assert set(adj) == set(nodes)
    # mint_token is never a `source` in the fixture, yet it knows both nodes that point at it
    assert adj["auth/token.py:mint_token"] == {"auth/session.py:create_session", "auth/token.py"}


def test_load_graph_drops_edges_to_unknown_nodes(tmp_path):
    path = write_graph(tmp_path, {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"source": "a", "target": "b"}, {"source": "a", "target": "ghost"}],
    })
    _, adj = load_graph(path)
    assert adj == {"a": {"b"}, "b": {"a"}}


def test_load_graph_missing_optional_fields_become_none(tmp_path):
    nodes, _ = load_graph(write_graph(tmp_path, {"nodes": [{"id": "a"}]}))
    assert nodes["a"] == {"id": "a", "type": None, "name": None, "source_location": None}


def test_load_graph_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_graph(tmp_path / "nope.json")


# query tests
def test_bfs_query_session_depth_1():
    nodes, adj = load_graph(FIXTURE)
    result = bfs_query(nodes, adj, ["session"], depth=1)
    assert [n["id"] for n in result] == [
        "api/routes.py:login",
        "api/routes.py:logout",
        "auth/session.py",
        "auth/session.py:create_session",
        "auth/session.py:invalidate",
        "auth/token.py:mint_token",
    ]


def test_bfs_query_depth_0_returns_only_keyword_matches():
    nodes, adj = load_graph(FIXTURE)
    result = bfs_query(nodes, adj, ["session"], depth=0)
    assert [n["id"] for n in result] == [
        "auth/session.py",
        "auth/session.py:create_session",
        "auth/session.py:invalidate",
    ]


def test_bfs_query_is_case_insensitive():
    nodes, adj = load_graph(FIXTURE)
    assert bfs_query(nodes, adj, ["SESSION"]) == bfs_query(nodes, adj, ["session"])


def test_bfs_query_no_match():
    nodes, adj = load_graph(FIXTURE)
    assert bfs_query(nodes, adj, ["nonexistent"]) == []
    assert format_nodes([], adj) == "(no matching nodes)"


def test_bfs_query_ignores_blank_keywords_and_accepts_a_bare_string():
    nodes, adj = load_graph(FIXTURE)
    assert bfs_query(nodes, adj, [""]) == []                # blank must not match the whole graph
    assert bfs_query(nodes, adj, ["  ", "user"]) == bfs_query(nodes, adj, ["user"])
    assert bfs_query(nodes, adj, "session") == bfs_query(nodes, adj, ["session"])


def test_format_nodes_exact_output():
    nodes, adj = load_graph(FIXTURE)
    result = bfs_query(nodes, adj, ["user"], depth=1)
    assert format_nodes(result, adj) == (
        "db/models.py [code] models.py @ db/models.py:1 — neighbors: db/models.py:User\n"
        "db/models.py:User [code] User @ db/models.py:5 — neighbors: db/models.py"
    )


def test_format_nodes_caps_neighbor_list():
    hub = {"id": "hub", "type": "code", "name": None, "source_location": None}
    adj = {"hub": {f"leaf{i:02d}" for i in range(12)}}
    out = format_nodes([hub], adj)
    assert out.startswith("hub [code] — neighbors: leaf00")
    assert out.endswith("leaf09 (+2 more)")


def test_top_nodes_ranks_by_degree():
    nodes, adj = load_graph(FIXTURE)
    result = top_nodes(nodes, adj, n=5)
    assert [n["id"] for n in result] == [
        "auth/session.py:create_session",   # degree 3, the only hub
        "api/routes.py",                    # degree 2 from here down, id-ordered
        "api/routes.py:login",
        "api/routes.py:logout",
        "auth/session.py",
    ]
