"""Teaching contracts: temporal leakage, source drift, privacy and separate learning evidence."""
import copy
import json

import pytest

from sports_video_coach import clips, lesson_page, lessons


def example():
    words = dict(title='Use the free teammate', look='Watch the receiver near the line.', good='The pass reaches a ready teammate.',
                 change='No specific error is established here.', next='When the lane is clear, pass to the ready receiver.',
                 exception='Keep the ball if a defender closes that lane.', question='Who can receive safely?',
                 rationale='The receiver has room before the pass, regardless of the eventual shot.',
                 choices=[dict(id='pass', text='Pass along the open lane', acceptable=True, why='The receiver is ready.'),
                          dict(id='force', text='Pass through the defender', acceptable=False, why='That lane is blocked.')])
    return dict(schema_version=1, game_id='synthetic-game', languages=['en', 'zh'],
                dependencies=['source.json'], introduction=dict(en='Watch our choices.', zh='看选择。'),
                closing=dict(en='Read the receiver before you pass.', zh='传球前看接球人。'), episodes=[dict(
                    id='ep1', start=10, decision_t=12, action_t=13, outcome_t=16, end=18,
                    observation='Receiver has space.', cues=['Receiver is outside the crowd.'], action='Pass to receiver.',
                    decision_assessment='Reasonable with the visible lane.', execution_assessment='Receiver controls the pass.',
                    outcome='Shot misses.', alternatives=[dict(when='Lane closes', action='Keep a live dribble', limit='Only if still legal')],
                    uncertainty=dict(identity='Role visible, number unclear', timing='Frames bracket release',
                                     choice='Several reasonable actions', outcome='Miss visible'),
                    sources=[dict(type='film_observation', ref='frame.jpg', supports='Receiver space before release')],
                    frames=['frame.jpg'], marks=[[.3,.5]])], lessons=[dict(
                    id='pass-room', episode_id='ep1', kind='good', objective='Check receiver and passing lane before passing.',
                    contrast_limit='No independent contrasting episode yet.', text=dict(en=words, zh=copy.deepcopy(words)),
                    practice=dict(kind='observation', setup='Review the catch.', cue='Receiver and defender position.',
                                  observe='Describe the lane before deciding.', stop_or_change='Say unclear if the lane is hidden.'))])


def prepare(folder):
    data = example()
    lessons.write(folder / 'source.json', {'private': 'DO NOT EXPORT NOTE'})
    (folder / 'frame.jpg').write_bytes(b'synthetic frame')
    lessons.write(folder / 'lessons.json', data)
    lessons.write(folder / 'lesson-review.json', dict(reviewer='separate reviewer', reviewer_kind='independent_agent',
        verdicts=[dict(id='pass-room', verdict='keep', evidence_check='Reopened the receiver before release.',
                      alternative_check='Keeping the ball also works if the lane closes.',
                      plain_language_check='Cue and next action are stated without jargon.',
                      translation_check='Choice ids, conditions and uncertainty match.', reopened=['frame.jpg'])]))
    assert lessons.stamp_review(folder) == []
    return data


def test_requires_pre_action_evidence_not_result_frame():
    data = example()
    assert not lessons.validate(data)
    data['episodes'][0]['decision_t'] = 14
    assert any('decision_t < action_t' in e for e in lessons.validate(data))
    data['episodes'][0]['decision_t'] = float('nan')
    assert lessons.validate(data)


@pytest.mark.parametrize('key', ['cues', 'alternatives', 'sources', 'frames', 'uncertainty'])
def test_empty_contract_fields_do_not_count_as_evidence(key):
    data = example()
    data['episodes'][0][key] = []
    assert lessons.validate(data)


def test_unsupported_practice_quota_and_disagreeing_languages_fail():
    data = example()
    data['lessons'][0]['practice']['target'] = .95
    assert any('experimental basis' in e for e in lessons.validate(data))
    data = example()
    data['lessons'][0]['text']['zh']['choices'][1]['acceptable'] = True
    assert any('language choices disagree' in e for e in lessons.validate(data))


def test_changed_evidence_invalidates_all_languages_and_exports_no_private_data(tmp_path):
    prepare(tmp_path)
    assert lessons.compile_lessons(tmp_path) == []
    assert lessons.derivative_errors(tmp_path) == []
    public = (tmp_path / 'lesson.public.json').read_text(encoding='utf8')
    assert 'DO NOT EXPORT' not in public and 'source.json' not in public and 'frames' not in public
    (tmp_path / 'frame.jpg').write_bytes(b'corrected frame')
    assert any('changed' in e for e in lessons.derivative_errors(tmp_path))
    assert lessons.compile_lessons(tmp_path)


def test_manual_translation_edit_cannot_bypass_reviewed_source(tmp_path):
    prepare(tmp_path)
    lessons.compile_lessons(tmp_path)
    (tmp_path / 'film.zh.md').write_text('Changed advice', encoding='utf8')
    assert any('film.zh.md' in e for e in lessons.derivative_errors(tmp_path))


def test_same_source_generates_prechoice_clip_and_escaped_interaction(tmp_path):
    data = prepare(tmp_path)
    data['lessons'][0]['text']['en']['title'] = '<img src=x onerror=alert(1)>'
    lessons.write(tmp_path / 'lessons.json', data)
    lessons.stamp_review(tmp_path)
    lessons.compile_lessons(tmp_path)
    assert ('00:10', '00:12') in clips.find_clips(tmp_path, film=False)
    assert ('00:10', '00:18') in clips.find_clips(tmp_path, film=False)
    page = lesson_page.panel(tmp_path, 'en')
    assert '&lt;img src=x onerror=alert(1)&gt;' in page
    assert 'class="lesson-answer" hidden' in page and '0010-0012.mp4' in page
    assert 'source.json' not in page and str(tmp_path) not in page


def test_agent_scores_and_unknown_denominators_do_not_become_human_learning():
    base = dict(lesson_id='a', lesson_version='v1', rater_id='anon', phase='game_transfer', rater_kind='human')
    result = lessons.evaluation_summary([{**base, 'opportunities': None, 'appropriate_decisions': 3, 'executed': 2},
                                         {**base, 'rater_kind': 'agent'}])
    assert result['learning_status'] == 'not_measured' and result['agent_audits'] == 1
    assert result['game_transfer'][0]['decision_rate'] is None
    result = lessons.evaluation_summary([{**base, 'opportunities': 2, 'appropriate_decisions': 3, 'executed': 1}])
    assert result['errors'] and not result['game_transfer']


def test_single_correct_answer_is_not_comprehension_validation():
    result = lessons.evaluation_summary([dict(lesson_id='a', lesson_version='v1', rater_id='anon',
        phase='comprehension', rater_kind='human', choice='a')])
    assert result['errors'] and result['learning_status'] == 'not_measured'


def test_clock_carries_tenths_across_minute_boundary():
    assert lessons.clock(59.99) == '01:00'


def test_next_action_gets_a_card_and_learning_needs_an_actual_response():
    data = example()
    script = lessons.script(data, 'en')
    assert '## Next time ·' in script
    base = dict(lesson_id='a', lesson_version='v1', rater_id='reviewer', viewer_id='viewer',
        phase='comprehension', rater_kind='human', cue_understood=True,
        action_understood=True, exception_understood=True)
    assert lessons.evaluation_summary([base])['errors']
    response = dict(base, viewer_response='Look at the receiver and pass if the lane stays clear.')
    assert not lessons.evaluation_summary([response])['errors']
    assert lessons.evaluation_summary([dict(response, rater_id='viewer')])['errors']


def test_bilingual_cards_share_saved_recall_without_reload(tmp_path):
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is not available for the interaction regression')
    setup = r'''
const records=new Map(), listeners={};
globalThis.localStorage={getItem:k=>records.get(k)||null,setItem:(k,v)=>records.set(k,v)};
globalThis.CustomEvent=class{constructor(type,o){this.type=type;this.detail=o.detail}};
function element(){return {value:'',textContent:'',hidden:true,handlers:{},addEventListener(t,f){this.handlers[t]=f},setAttribute(){},pause(){}}}
function card(lang){const nodes={};for(const name of ['lesson-recall','lesson-before','lesson-answer','lesson-feedback','lesson-save','lesson-saved'])nodes['.'+name]=element();
 const choice=element();choice.dataset={choice:'a',why:lang+' explanation'};
 return {dataset:{key:'shared',lesson:'pass',version:'v1',language:lang},nodes,choice,
 querySelector:s=>nodes[s],querySelectorAll:s=>s==='.lesson-choice'?[choice]:[]};}
const cardsForTest=[card('en'),card('zh')];
globalThis.document={querySelectorAll:s=>s==='.lesson-card'?cardsForTest:[],
 addEventListener:(t,f)=>(listeners[t]??=[]).push(f),dispatchEvent:e=>(listeners[e.type]||[]).forEach(f=>f(e))};
'''
    assertions = r'''
const [en,zh]=cardsForTest;
en.choice.handlers.click();en.nodes['.lesson-recall'].value='Look at the receiver first.';
en.nodes['.lesson-save'].handlers.click();
if(zh.nodes['.lesson-answer'].hidden || zh.nodes['.lesson-recall'].value!=='Look at the receiver first.')throw Error('translated card stale');
if(zh.nodes['.lesson-feedback'].textContent!=='zh explanation')throw Error('wrong feedback language');
zh.nodes['.lesson-save'].handlers.click();
if(JSON.parse(records.get('shared')).recall!=='Look at the receiver first.')throw Error('recall was erased');
'''
    js = lesson_page.ASSETS.split('<script>', 1)[1].split('</script>', 1)[0]
    file = tmp_path / 'cards.js'
    file.write_text(setup + js + assertions, encoding='utf8')
    subprocess.run([node, str(file)], check=True, capture_output=True)
