from ..graph.query import format_nodes, top_nodes
from ..graph.loader import NodeLookup, AdjacencyMap

def run(args: dict, nodes: NodeLookup, adj: AdjacencyMap) -> str:
    n = int(args.get("n", 5))
    selected_nodes = top_nodes(nodes, adj, n)
    formatted_result = format_nodes(selected_nodes, adj)
    return formatted_result