from copy import deepcopy
import json

from sports_video_coach import lesson_eval as E


def case(tmp_path):
    (tmp_path / 'before.jpg').write_bytes(b'frame')
    return dict(episode_id='a', game_id='g1', split='development', recurrence_group='p1',
                decision_t=4.5, question='Where is the defender?',
                pre_action_frames=[dict(t=4, path='before.jpg', outcome='must not leak')],
                pre_action_cues=[dict(t=4, text='The defender is beside the receiver.')],
                outcome='made', answer='pass', future_frames=['after.jpg'],
                annotation=dict(kind='agent_provisional', author='writer', reviewer='critic', adjudication='unclear'))


def test_preparation_has_no_outcome_or_future_frames(tmp_path):
    c = case(tmp_path)
    out = tmp_path / 'out'
    assert E.prepare([c], tmp_path, out) == []
    prompt = json.loads((out / 'preaction-prompts.json').read_text())[0]
    assert not {'outcome', 'answer', 'future_frames', 'annotation'} & prompt.keys()
    assert set(prompt['pre_action_frames'][0]) == {'t', 'path'}
    assert prompt['pre_action_frames'][0]['path'] == str((tmp_path / 'before.jpg').resolve())
    assert json.loads((out / 'reference-key.private.json').read_text())[0]['outcome'] == 'made'


def test_rejects_late_frame_cue_and_game_split_leak(tmp_path):
    c = case(tmp_path)
    other = deepcopy(c)
    other.update(episode_id='b', split='held_out')
    other['pre_action_frames'][0]['t'] = 5
    other['pre_action_cues'][0]['t'] = 6
    errors = E.validate_cases([c, other], tmp_path)
    assert any('both splits' in x for x in errors)
    assert any('later time' in x for x in errors)
    assert any('no later' in x for x in errors)


def test_recurrence_and_uncertainty_are_not_success(tmp_path):
    c = case(tmp_path)
    rating = dict(episode_id='a', variant='new', author='writer', reviewer='critic',
                  reviewer_kind='independent_agent', fact_support='pass', conditional_action='unclear', plain_language='pass')
    result = E.ratings_summary([c], [rating])
    assert not result['errors']
    counts = result['groups']['new:independent_agent:development']['conditional_action']
    assert counts == {'pass': 0, 'fail': 0, 'unclear': 1}
    assert result['learning_effectiveness'] == 'not_measured'
    assert E.ratings_summary([c], [dict(rating, reviewer='writer')])['errors']
    assert E.ratings_summary([c], [dict(rating, author='')])['errors']
    assert E.ratings_summary([c], [rating, rating])['errors']
    assert E.ratings_summary([c], [])['groups'] == {}
