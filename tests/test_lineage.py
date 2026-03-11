import networkx as nx
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.app import app


def _build_graph():
    g = nx.DiGraph()
    for node in ('orders', 'customers', 'inventory', 'payments'):
        g.add_node(node)
    g.add_edge('orders', 'customers', JoinKeys='orders.customer_id = customers.customer_id')
    g.add_edge('customers', 'orders', JoinKeys='orders.customer_id = customers.customer_id')
    g.add_edge('orders', 'inventory', JoinKeys='orders.inventory_id = inventory.inventory_id')
    g.add_edge('inventory', 'orders', JoinKeys='orders.inventory_id = inventory.inventory_id')
    g.add_edge('payments', 'orders', JoinKeys='payments.order_id = orders.order_id')
    g.add_edge('orders', 'payments', JoinKeys='payments.order_id = orders.order_id')
    return g


def test_lineage_returns_connected_component():
    client = TestClient(app)
    graph = _build_graph()

    with patch('MetadataManager.MetadataStore.relationdb.kuzuDB.getObj', return_value=graph):
        response = client.get('/api/lineage/orders')

    assert response.status_code == 200
    payload = response.json()
    assert payload['center'] == 'orders'
    assert len(payload['nodes']) == 4  # orders + customers + inventory + payments -> center + 3 others sorted
    assert payload['nodes'][0]['id'] == 'orders'
    assert set(n['id'] for n in payload['nodes']) == {'orders', 'customers', 'inventory', 'payments'}

    # edges should include at least the join keys we inserted (deduplicated)
    join_keys = {edge['joinKeys'] for edge in payload['edges']}
    assert 'orders.customer_id = customers.customer_id' in join_keys
    assert 'orders.inventory_id = inventory.inventory_id' in join_keys


def test_lineage_missing_table_returns_404():
    client = TestClient(app)
    graph = _build_graph()

    with patch('MetadataManager.MetadataStore.relationdb.kuzuDB.getObj', return_value=graph):
        response = client.get('/api/lineage/nonexistent')

    assert response.status_code == 404
