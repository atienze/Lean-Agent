from pathlib import Path
import json

# Node defined by graphify schema
Node = {
    "id": str,      
    "type": str,        
    "name": str | None,
    "source_location": str | None,
}

# adjacency map to node id's to neighbor id's 
AdjacencyMap = dict[str, set[str]]

# node lookup id to node
NodeLookup = dict[str, Node]

# convert graphify node to internal representation
def _translate_node(raw_node: dict) -> Node:

    return {
        "id": raw_node["id"],
        "type": raw_node.get("file_type"),
        "name": raw_node.get("label"),
        "source_location": raw_node.get("source_location"),
    }

# extract source/target pair from graphify edge
def _translate_edge(raw_edge: dict) -> tuple[str, str]:

    return (raw_edge["source"], raw_edge["target"])

# load graph.json and return (node_lookup, adjacency_map)
def load_graph(graph_path: Path) -> tuple[NodeLookup, AdjacencyMap]:

    # check for graph_path existance
    if not graph_path.exists():
        raise FileNotFoundError(f"Graph missing... Try running 'lean init' first.")

    # read raw JSON
    with open(graph_path) as d:
        data = json.load(d)

    # grab nodes from json and put into map
    nodes: NodeLookup = {}
    for raw_node in data.get("nodes", []):
        node = _translate_node(raw_node)
        nodes[node["id"]] = node

    # build undirected adjacency map
    adj: AdjacencyMap = {node_id: set() for node_id in nodes}

    # grab edges from json and put into adj matrix
    for raw_edge in data.get("edges", []):
        source, target = _translate_edge(raw_edge)

        if source in adj and target in adj:
            adj[source].add(target)
            adj[target].add(source)

    return nodes, adj


    