from .loader import AdjacencyMap, Node, NodeLookup

MAX_NEIGHBORS_SHOWN = 10

# 
def _matches(node: Node, wanted: list[str]) -> bool:
    parts = (node["id"], node["name"], node["source_location"])
    text = " ".join(part for part in parts if part).lower()
    return any(keyword in text for keyword in wanted)

def bfs_query(
        nodes: NodeLookup,
        adj: AdjacencyMap,
        keywords: list[str],
        depth: int = 1,
) -> list[Node]:
    # validate if model only sent one keyword
    if isinstance(keywords, str):
        keyword_list = [keywords]
    else:
        keyword_list = keywords

     # validate that there is no full whitespace items
     # strips and lowercases all other items
    wanted = []

    for keyword in keyword_list:
        text = str(keyword)
        if text.strip():
            wanted.append(text.strip().lower())

    # grab start ids for all nodes in wanted
    start_ids = []

    for node_id, node in nodes.items():
        if _matches(node, wanted):
            start_ids.append(node_id)

    # BFS
    visited = set(start_ids)
    frontier = list(start_ids)

    """
    add nodes to next_frontier and visited that are present
    in the neighbors of the node_id's in frontier
    """
    for _ in range(depth):
        next_frontier = []
        for node_id in frontier:
            for neighbor_id in adj[node_id]:
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    next_frontier.append(neighbor_id)
        frontier = next_frontier

    # result_nodes = all matching and reachable nodes that are in visited
    result_nodes = []
    for node_id in sorted(visited):
        node = nodes[node_id]
        result_nodes.append(node)
    
    return result_nodes 


def top_nodes(
        nodes: NodeLookup, 
        adj: AdjacencyMap, 
        n: int = 5,
) -> list[Node]:
    #define a helper to grab items adjacent and sort them (-degree)
    def node_sort_key(node: Node) -> tuple[int, str]:
        degree = len(adj[node["id"]])
        return (-degree, node["id"])

    # return sorted node values based on the helper
    ranked = sorted(nodes.values(), key=node_sort_key)

    # return first n items from ranked
    return ranked[:n]


def _describe(node: Node) -> str:
    # make a description of nodes from the node variables
    head = f"{node['id']} [{node['type'] or 'unknown'}]"
    if node["name"]:
        head += f" {node['name']}"
    if node["source_location"]:
        head += f" @ {node['source_location']}"
    return head

def format_nodes(nodes: list[Node], adj: AdjacencyMap) -> str:
    # check if nodes is falsy
    if not nodes:
        return "(no matching nodes)"

    # format to readable by me or LLM
    lines = []
    for node in nodes:
        neighbors = sorted(adj[node["id"]])
        if neighbors:
            shown = neighbors[:MAX_NEIGHBORS_SHOWN]
            hidden = len(neighbors) - len(shown)
            tail = ", ".join(shown) + (f" (+{hidden} more)" if hidden else "")
        else:
            tail = "(none)"
        lines.append(f"{_describe(node)} - neighbors: {tail}")
    # return each nodes description (neighbors & hidden neighbors)
    return "\n".join(lines)