"""Saving a layout into a level file, and taking it out again."""
import json
import os
import re

CREATED_MARKER = 'created_by_editor'


def level_path(level):
    from utils.resource_path import resource_path
    return resource_path(f'levels/{level}.json')


def _write(path, data):
    text = json.dumps(data, indent=2)
    text = re.sub(r'\[\s*(-?\d+),\s*(-?\d+)\s*\]', r'[\1, \2]', text)     # a cell on one line
    # Write beside the file, then swap it in: a failed write never leaves the level file half-written
    temporary = f'{path}.saving'
    try:
        with open(temporary, 'w') as handle:
            handle.write(text + '\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def _read(path):
    with open(path) as handle:
        return json.load(handle)


def save_layout(path, layout, defaults, extra=None):
    """Write `layout` (and `extra`'s keys beside it) into the level file, keeping every other key. A level with
    no file gets one made from `defaults` (its seed and maze), marked as the editor's own so that reverting can
    delete it again."""
    if os.path.exists(path):
        data = _read(path)
    else:
        data = {**defaults, CREATED_MARKER: True}
    data['layout'] = layout.to_json()
    data.update(extra or {})
    _write(path, data)


def revert_layout(path):
    """Take the layout out of the level file. True if there was one. A file the editor made is deleted."""
    if not os.path.exists(path):
        return False
    data = _read(path)
    if 'layout' not in data:
        return False
    del data['layout']
    if data.get(CREATED_MARKER):
        os.remove(path)
    else:
        _write(path, data)
    return True
