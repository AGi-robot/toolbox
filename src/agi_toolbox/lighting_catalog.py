"""Editable Markdown catalogue, with one fenced JSON data block and atomic saves."""
import json
import os
import re
import tempfile
import threading
from pathlib import Path

from .lighting_effects import LightingEffect, _colour

_BLOCK = re.compile(r'```json\s*\n(.*?)\n```', re.DOTALL)
_LOCK = threading.RLock()
_DEFAULT = Path(__file__).with_name('lighting_catalog.md')


def _path():
    return Path(os.getenv('AGI_LIGHTING_CATALOG', '~/.agi/lighting.md')).expanduser()


def _document():
    path = _path()
    source = path if path.exists() else _DEFAULT
    if source.stat().st_size > 65536:
        raise ValueError('Lighting catalogue exceeds 64 KiB')
    return source.read_text(encoding='utf-8')


def _parse(document):
    blocks = list(_BLOCK.finditer(document))
    if len(blocks) != 1:
        raise ValueError('Lighting catalogue needs exactly one fenced json block')
    data = json.loads(blocks[0].group(1))
    if not isinstance(data, dict) or set(data) != {'colors', 'effects'}:
        raise ValueError('Catalogue must contain colors and effects objects')
    for category in ('colors', 'effects'):
        if not isinstance(data[category], dict) or len(data[category]) > 128:
            raise ValueError('Catalogue permits at most 128 colours and 128 effects')
        for name in data[category]:
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name):
                raise ValueError('Catalogue names use letters, digits, underscores and hyphens')
    for colour in data['colors'].values():
        _colour(colour)
    for effect in data['effects'].values():
        resolve_effect(effect, data)
    return data


def resolve_effect(payload, catalog=None):
    if not isinstance(payload, dict):
        raise ValueError('Expected an effect object')
    values = dict(payload)
    if catalog is None:
        catalog = read_catalog()
    name = values.pop('preset', None)
    if name == 'default' and name not in catalog['effects']:
        catalog = {**catalog, 'effects': {**catalog['effects'], 'default': {}}}
    if name is not None:
        if name not in catalog['effects']:
            raise ValueError('Unknown lighting preset')
        values = {**catalog['effects'][name], **values}
    if name == 'default':
        if set(values) - {'reason', 'meaning'}:
            raise ValueError('The default preset restores live activity lighting; overrides are not applicable')
        # Validate explanation fields through the regular effect validator.
        LightingEffect(**values)
        return None
    for key in ('start_color', 'end_color'):
        if isinstance(values.get(key), str):
            values[key] = catalog['colors'].get(values[key], values[key])
    if isinstance(values.get('transition_colors'), list):
        values['transition_colors'] = [catalog['colors'].get(c, c) if isinstance(c, str) else c for c in values['transition_colors']]
    return LightingEffect(**values)


def read_catalog():
    with _LOCK:
        data = _parse(_document())
        # New built-in effects appear in existing user catalogues without
        # overwriting the user's saved colors or effects.
        if _path().exists():
            seed = _parse(_DEFAULT.read_text(encoding='utf-8'))
            for category in ('colors', 'effects'):
                data[category] = {**seed[category], **data[category]}
        data['default_behavior'] = 'Release expressive control so Console can render its current activity state'
        data['effects']['default'] = {}
        return data


def save_preset(name: str, effect: dict, colors: dict | None = None, reason: str = '', meaning: str = ''):
    with _LOCK:
        if name == 'default':
            raise ValueError('default is reserved for the live activity lighting')
        document = _document()
        data = _parse(document)
        seed = _parse(_DEFAULT.read_text(encoding='utf-8'))
        for category in ('colors', 'effects'):
            data[category] = {**seed[category], **data[category]}
        if not isinstance(effect, dict) or 'preset' in effect:
            raise ValueError('Saved effects must be objects without nested preset references')
        if colors is not None and not isinstance(colors, dict):
            raise ValueError('colors must be an object')
        LightingEffect(reason=reason, meaning=meaning)
        if reason:
            effect = {**effect, 'reason': reason}
        if meaning:
            effect = {**effect, 'meaning': meaning}
        data['colors'].update(colors or {})
        data['effects'][name] = effect
        block = '```json\n' + json.dumps(data, indent=2, ensure_ascii=False) + '\n```'
        match = _BLOCK.search(document)
        updated = document[:match.start()] + block + document[match.end():]
        _parse(updated)
        if len(updated.encode('utf-8')) > 65536:
            raise ValueError('Lighting catalogue exceeds 64 KiB')
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as handle:
                temporary = handle.name
                handle.write(updated)
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        return {'saved': name, 'effect': effect, 'colors': colors or {}, 'reason': reason, 'meaning': meaning}
