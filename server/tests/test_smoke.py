def test_app_importable():
    try:
        import server.server.app as appmod
    except ModuleNotFoundError:
        import server.app as appmod
    assert hasattr(appmod, "app")
