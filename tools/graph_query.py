from ..graph.query import bfs_query, format_nodes
from ..graph.loader import AdjacencyMap, NodeLookup

def run(args: dict, nodes: NodeLookup, adj: AdjacencyMap) -> str:
    found = bfs_query(nodes, adj, args["keywords"])
    return query.format_nodes(found, adj)