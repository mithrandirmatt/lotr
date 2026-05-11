def test_app_importable():
    import server.server.app as appmod
    assert hasattr(appmod, "app")
