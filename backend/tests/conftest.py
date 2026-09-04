def pytest_collection_modifyitems(config, items):
    # Force sequential order in file for shared state
    items.sort(key=lambda i: i.location[1])
