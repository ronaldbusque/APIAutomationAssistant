try:
    import sys
    print(f"Python version: {sys.version}")
    print(f"Sys path: {sys.path}")
except Exception as e:
    print(f"Error getting system info: {e}")

try:
    import agents
    print('Found module: agents')
    print(dir(agents))
except ImportError as e:
    print(f'Module not found: agents - {e}')

try:
    from agents import Agent, Runner
    print('Successfully imported Agent and Runner from agents')
except ImportError as e:
    print(f'Failed to import from agents: {e}')

try:
    import openai_agents
    print('Found module: openai_agents')
    print(dir(openai_agents))
except ImportError as e:
    print(f'Module not found: openai_agents - {e}')

try:
    import site
    print(f"Site packages: {site.getsitepackages()}")
    # List all the site packages
    for site_pkg in site.getsitepackages():
        import os
        if os.path.exists(site_pkg):
            print(f"Contents of {site_pkg}:")
            print(os.listdir(site_pkg))
except Exception as e:
    print(f"Error listing site packages: {e}") 