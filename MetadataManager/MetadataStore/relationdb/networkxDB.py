"""
Utility functions for handling graph relations and attributes using NetworkX.

This module provides functions to load, add relations, and retrieve relations from a NetworkX graph.
"""

import networkx as nx
import pickle
import os
from pyvis.network import Network
from itertools import combinations
from iteration_utilities import unique_everseen
from Utilities.base_utils import get_config_val


# --------------------------------------------------------------------------------------------

def getObj():
    """
    Load a NetworkX graph object from a pickle file if it exists, otherwise return an empty graph.

    Returns:
        nx.DiGraph: Loaded graph object if the file exists, otherwise an empty graph.

    Notes:
        - If the specified file exists, it is assumed to contain a NetworkX graph serialized using pickle.
        - The function returns the loaded graph object if the file exists.
        - If the file doesn't exist, an empty graph is returned.
    """

    Graphfilename = get_config_val("retrieval_config", ["relationdb","path"])

    if os.path.exists(Graphfilename):
        # If the file exists, load the graph from the pickle file
        with open(Graphfilename, "rb") as GObj:
            return pickle.load(GObj)
    else:
        # If the file doesn't exist, return an empty directed graph
        return nx.DiGraph()

# --------------------------------------------------------------------------------------------

def addRelations(GObj: nx.DiGraph, edges: dict):
    """
    Add nodes and edges with attributes to a NetworkX graph and save it to a pickle file.

    Args:
        GObj (nx.DiGraph): NetworkX graph object to which nodes and edges will be added.
        edges (dict): Dictionary containing edge tuples as keys (source, target) and edge attributes as values.

    Notes:
        - The function modifies the graph object GObj in place by adding edges with attributes.
        - Edges are added with the specified attributes.
        - The graph is then saved to a pickle file with the specified filename.
    """

    # Add edges in both directions — JOINs are semantically bidirectional,
    # and DiGraph requires explicit reverse edges for path traversal.
    for edge in edges:
        GObj.add_edge(edge[0].lower(), edge[1].lower(), JoinKeys=edge[2])
        GObj.add_edge(edge[1].lower(), edge[0].lower(), JoinKeys=edge[2])

    Graphfilename = get_config_val("retrieval_config", ["relationdb", "path"])

    # Save the graph to a pickle file
    with open(Graphfilename, 'wb') as f:
        pickle.dump(GObj, f)

# --------------------------------------------------------------------------------------------

def getRelations(GObj: nx.DiGraph, target_nodes: list):
    """
    Retrieve relations between target nodes in a graph.

    Args:
        GObj (nx.DiGraph): NetworkX graph object.
        target_nodes (list): List of target nodes.

    Returns:
        list: List of relations between target nodes along the shortest path.

    Notes:
        - This function finds the shortest path visiting all target nodes exactly once.
        - Relations are extracted along the shortest path, including edge attributes and node attributes.
    """
    # Initialize variables to store relations and shortest path
    relations = []
    shortest_path = dict()

    # Generate all possible paired combinations of target nodes
    combs = combinations(target_nodes, 2)

    # Find shortest path visiting all target nodes exactly once
    for comb in combs:

        # Check if there is an edge between consecutive target nodes
        if not nx.has_path(GObj, comb[0].lower(), comb[1].lower()):
            is_valid_path = False
            break

        # Compute the shortest path length between consecutive target nodes
        path = nx.shortest_path(GObj, source=comb[0].lower(), target=comb[1].lower())


        # Extract relations and attributes along the shortest path
        for i in range(len(path) - 1):
            relations.append({
                'source': path[i],
                'target': path[i + 1],
                'edge_attributes': GObj.get_edge_data(path[i], path[i + 1]),
                'node1_attributes': GObj.nodes[path[i]],
                'node2_attributes': GObj.nodes[path[i + 1]]
            })

        # Unique relations while maintaining their order
        relations = list(unique_everseen(relations))

    return relations
# --------------------------------------------------------------------------------------------

def visualizeRelations(GObj: nx.DiGraph):
    """
    Visualizes the relations in the graph and saves the graph as an HTML file.

    Args:
        GObj (nx.DiGraph): NetworkX graph object containing the relations.

    Returns:
        str: Message indicating that the HTML graph has been exported.
    """
    GraphViz = get_config_val("retrieval_config", ["relationdb", "viz"])
    # Initialize a Network object
    net = Network(height="1000px", width="100%")

    # Load the graph data into the Network object
    net.from_nx(GObj)

    # Save the graph as an HTML file
    net.save_graph(GraphViz)

    return "Html Graph : Exported"

