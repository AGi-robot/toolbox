import pytest
from agi_toolbox.lighting_catalog import read_catalog, save_preset, resolve_effect


def test_catalog_saves_markdown_and_resolves_names(tmp_path, monkeypatch):
    path = tmp_path / 'lighting.md'
    monkeypatch.setenv('AGI_LIGHTING_CATALOG', str(path))
    assert 'rainbow' in read_catalog()['effects']
    assert not path.exists()
    save_preset('my_pattern', {'start_color': 'ocean', 'rhythm': 'pattern',
                'rhythm_pattern': [0, .5, 1, .5], 'rhythm_seconds': 4}, {'ocean': '#0088CC'})
    assert path.exists()
    assert '```json' in path.read_text()
    effect = resolve_effect({'preset': 'my_pattern', 'brightness': 1})
    assert effect.color_at(0) == (0, 0, 0)
    assert effect.color_at(2) == (0, 136, 204)
    before = path.read_text()
    with pytest.raises(ValueError):
        save_preset('invalid', {'brightness': 5})
    assert path.read_text() == before
    path.write_text(before.replace("# Grace's lighting catalogue", '# My own notes'))
    save_preset('quiet', {'brightness': .1})
    assert path.read_text().startswith('# My own notes')


def test_invalid_manual_markdown_is_reported(tmp_path, monkeypatch):
    path = tmp_path / 'lighting.md'
    path.write_text('No machine readable block here')
    monkeypatch.setenv('AGI_LIGHTING_CATALOG', str(path))
    with pytest.raises(ValueError):
        read_catalog()


def test_default_releases_expressive_control(tmp_path, monkeypatch):
    monkeypatch.setenv('AGI_LIGHTING_CATALOG', str(tmp_path / 'lighting.md'))
    assert 'default' in read_catalog()['effects']
    assert resolve_effect({'preset': 'default', 'reason': 'Return to normal'}) is None
    with pytest.raises(ValueError):
        save_preset('default', {})


def test_personal_code_explanation_is_saved(tmp_path, monkeypatch):
    monkeypatch.setenv('AGI_LIGHTING_CATALOG', str(tmp_path / 'lighting.md'))
    save_preset('hello_oppa', {'start_color': '#FF88AA', 'rhythm': 'pattern',
                'rhythm_pattern': [1, 0, 1, 0], 'rhythm_seconds': 4},
                reason='I wanted a personal greeting', meaning='Two pink pulses mean hello')
    effect = resolve_effect({'preset': 'hello_oppa'})
    assert effect.meaning == 'Two pink pulses mean hello'
    assert effect.reason == 'I wanted a personal greeting'



def test_existing_catalog_gets_new_presets_and_can_save_their_colours(tmp_path, monkeypatch):
    path = tmp_path / 'lighting.md'
    path.write_text('# My catalogue\n\n```json\n{"colors":{"mint":"#123456"},"effects":{}}\n```\n')
    monkeypatch.setenv('AGI_LIGHTING_CATALOG', str(path))
    assert 'cyberpunk' in read_catalog()['effects']
    save_preset('my_cyan', {'start_color': 'cyan'})
    assert resolve_effect({'preset': 'my_cyan'}).start_color == '#00E5FF'
    assert read_catalog()['colors']['mint'] == '#123456'
    assert path.read_text().startswith('# My catalogue')
