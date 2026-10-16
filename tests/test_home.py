def test_landing_page_is_served_at_the_root(client):
    """Visitors and the admin's "View site" link open / - it must not 404."""
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res["Content-Type"]
    body = res.content.decode()
    assert "ShopAPI" in body
    assert "/api/docs/" in body
