"""Evidence-bound teaching episodes shared by film, interactive pages and follow-up.

No sport, tracking model or private notebook is assumed. The agent observes and judges;
this module checks the contract, invalidates changed evidence and compiles approved text.
Passing structure/review checks is not evidence that a person learned or improved in a game.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

SOURCE_TYPES = {"film_observation", "official_stat", "player_report", "model_proposal",
                "coaching_principle", "training_experiment"}
TEXT_FIELDS = ("title", "look", "good", "change", "next", "exception", "question", "rationale")
DIMENSIONS = ("identity", "timing", "choice", "outcome")
GENERIC_ACTIONS = {"make better decisions", "improve decision making", "play harder", "move the ball",
                   "communicate better", "be more aggressive", "加强防守", "注意配合", "多传球", "更积极", "打得更好"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf8"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def digest(folder: Path, data: dict | None = None) -> str:
    """Bind ALL languages, episodes, reviewed frames and declared source documents together."""
    data = data if data is not None else read(folder / "lessons.json")
    paths = set(data.get("dependencies", []))
    for episode in data.get("episodes", []):
        paths.update(episode.get("frames", []))
    contents = {str(p): sha(folder / p) if (folder / p).is_file() else None for p in sorted(paths)}
    return hashlib.sha256(json.dumps({"data": data, "files": contents}, sort_keys=True,
                                    ensure_ascii=False).encode("utf8")).hexdigest()


def validate(data: dict, folder: Path | None = None) -> list[str]:
    """Structural/evidence-contract errors. Visibility and feasible actions still need review."""
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return ["lessons.json: schema_version must be 1"]
    errors = []
    langs = data.get("languages")
    if not isinstance(langs, list) or not langs or len(set(langs)) != len(langs) \
            or any(l not in ("en", "zh") for l in langs):
        errors.append("languages: give unique en/zh language codes")
        langs = []
    if not nonempty(data.get("game_id")):
        errors.append("game_id is required")
    eps, lessons = data.get("episodes"), data.get("lessons")
    if not isinstance(eps, list) or not eps or not isinstance(lessons, list) or not lessons:
        return errors + ["episodes and lessons must be non-empty lists"]
    by_id = {}
    for i, ep in enumerate(eps):
        if not isinstance(ep, dict):
            errors.append(f"episode {i}: must be an object")
            continue
        tag = f"episode {ep.get('id', i)}"
        if not nonempty(ep.get("id")) or ep["id"] in by_id:
            errors.append(f"{tag}: missing or duplicate id")
        by_id[ep.get("id")] = ep
        values = [ep.get(k) for k in ("start", "decision_t", "action_t", "outcome_t", "end")]
        if not all(number(v) for v in values) or not 0 <= values[0] < values[1] < values[2] <= values[3] <= values[4]:
            errors.append(f"{tag}: require 0 <= start <= decision_t < action_t <= outcome_t <= end")
        elif round(values[1] * 10) >= round(values[2] * 10):
            errors.append(f"{tag}: decision and action must remain separate at film precision (0.1 s)")
        for key in ("observation", "action", "decision_assessment", "execution_assessment", "outcome"):
            if not nonempty(ep.get(key)):
                errors.append(f"{tag}: {key} is required; unclear is valid when explained")
        cues = ep.get("cues")
        if not isinstance(cues, list) or not cues or any(not nonempty(c) for c in cues):
            errors.append(f"{tag}: cues must describe visible information before the action")
        alternatives = ep.get("alternatives")
        if not isinstance(alternatives, list) or not alternatives or any(not isinstance(a, dict) or
                any(not nonempty(a.get(k)) for k in ("when", "action", "limit")) for a in alternatives):
            errors.append(f"{tag}: alternatives need when, action and limit (allow several reasonable choices)")
        uncertainty = ep.get("uncertainty", {})
        if not isinstance(uncertainty, dict) or any(not nonempty(uncertainty.get(k)) for k in DIMENSIONS):
            errors.append(f"{tag}: uncertainty needs identity, timing, choice and outcome separately")
        sources = ep.get("sources")
        if not isinstance(sources, list) or not sources or any(not isinstance(s, dict) or
                s.get("type") not in SOURCE_TYPES or not nonempty(s.get("ref")) or not nonempty(s.get("supports"))
                for s in sources):
            errors.append(f"{tag}: sources need type, ref and supports; principles are not game observations")
        frames = ep.get("frames")
        if not isinstance(frames, list) or not frames or any(not nonempty(f) for f in frames):
            errors.append(f"{tag}: list the actual inspected frames")
        elif folder:
            errors += [f"{tag}: inspected frame missing: {f}" for f in frames if not (folder / f).is_file()]
        marks = ep.get("marks", [])
        if not isinstance(marks, list) or any(not isinstance(m, list) or len(m) != 2 or
                any(not number(v) or not 0 <= v <= 1 for v in m) for m in marks):
            errors.append(f"{tag}: marks must be normalized [x,y] coordinates")
    ids = set()
    for i, lesson in enumerate(lessons):
        if not isinstance(lesson, dict):
            errors.append(f"lesson {i}: must be an object")
            continue
        tag = f"lesson {lesson.get('id', i)}"
        if not nonempty(lesson.get("id")) or lesson["id"] in ids:
            errors.append(f"{tag}: missing or duplicate id")
        ids.add(lesson.get("id"))
        if lesson.get("episode_id") not in by_id:
            errors.append(f"{tag}: unknown episode_id")
        if lesson.get("kind") not in ("good", "change", "unclear"):
            errors.append(f"{tag}: kind must be good, change or unclear")
        if not nonempty(lesson.get("objective")):
            errors.append(f"{tag}: give one observable learning objective")
        contrasts = lesson.get("contrast_episode_ids", [])
        if not isinstance(contrasts, list) or any(e not in by_id or e == lesson.get("episode_id") for e in contrasts):
            errors.append(f"{tag}: contrasting episodes must exist and differ from the main episode")
        if not contrasts and not nonempty(lesson.get("contrast_limit")):
            errors.append(f"{tag}: provide a contrasting episode or explain why none is established")
        text = lesson.get("text", {})
        for lang in langs:
            words = text.get(lang, {}) if isinstance(text, dict) else {}
            if not isinstance(words, dict):
                errors.append(f"{tag}/{lang}: text must be an object")
                continue
            for key in TEXT_FIELDS:
                if not nonempty(words.get(key)):
                    errors.append(f"{tag}/{lang}: {key} must name the cue, action or explained uncertainty")
            if str(words.get('next', '')).lower().strip().rstrip('.。!') in GENERIC_ACTIONS:
                errors.append(f"{tag}/{lang}: next is generic; name a visible cue and a concrete action")
            if re.search(r'\d+(?:\.\d+)?\s*[%％]', str(words.get('next', ''))) and not lesson.get('practice', {}).get('basis'):
                errors.append(f"{tag}/{lang}: percentage target needs an explicit experimental basis")
            choices = words.get("choices")
            if not isinstance(choices, list) or not 2 <= len(choices) <= 4 or any(not isinstance(c, dict) or
                    not nonempty(c.get("id")) or not nonempty(c.get("text")) or type(c.get("acceptable")) is not bool
                    or not nonempty(c.get("why")) for c in choices):
                errors.append(f"{tag}/{lang}: give 2–4 choices with id, text, acceptable and why")
            elif len({c['id'] for c in choices}) != len(choices) or not any(c['acceptable'] for c in choices):
                errors.append(f"{tag}/{lang}: choice ids must be unique and allow a reasonable answer")
        if len(langs) > 1 and isinstance(text, dict) and all(isinstance(text.get(l), dict) for l in langs):
            branches = [[(c.get('id'), c.get('acceptable')) for c in text[l].get('choices', []) if isinstance(c, dict)]
                        for l in langs]
            if any(b != branches[0] for b in branches[1:]):
                errors.append(f"{tag}: language choices disagree; review translations together")
        practice = lesson.get("practice", {})
        if not isinstance(practice, dict) or practice.get("kind") not in ("training_experiment", "observation"):
            errors.append(f"{tag}: practice kind must be training_experiment or observation")
        else:
            for key in ("setup", "cue", "observe", "stop_or_change"):
                if not nonempty(practice.get(key)):
                    errors.append(f"{tag}: practice.{key} is required")
            if practice.get("target") is not None and (not nonempty(practice.get("basis")) or
                                                       practice['kind'] != 'training_experiment'):
                errors.append(f"{tag}: numeric practice target needs an explicit experimental basis")
    deps = data.get("dependencies")
    if not isinstance(deps, list) or not deps or any(not nonempty(p) for p in deps):
        errors.append("dependencies must list the evidence/source documents used in authoring")
    elif folder:
        errors += [f"dependency missing: {p}" for p in deps if not (folder / p).is_file()]
    for key in ("introduction", "closing"):
        if not isinstance(data.get(key), dict) or any(not nonempty(data[key].get(l)) for l in langs):
            errors.append(f"{key}: provide the same message in every language")
    for i, scene in enumerate(data.get('context_scenes', [])):
        for lang in langs:
            if not isinstance(scene, dict) or any(not nonempty(scene.get(k, {}).get(lang))
                                                  for k in ('visual', 'caption', 'narration')):
                errors.append(f'context scene {i}: visual, caption and narration required in each language')
            elif not scene['visual'][lang].startswith(('stats:', 'stat:')):
                errors.append(f'context scene {i}: use a sourced stat/stats board')
    return errors


def review_errors(folder: Path, data: dict, *, signing: bool = False) -> list[str]:
    path = folder / "lesson-review.json"
    if not path.is_file():
        return ["lesson-review.json missing: an independent reviewer must re-open the evidence"]
    review = read(path)
    if not isinstance(review, dict):
        return ["lesson-review.json must be an object"]
    errors = []
    if review.get("reviewer_kind") not in ("independent_agent", "human_coach") or not nonempty(review.get("reviewer")):
        errors.append("review needs reviewer and reviewer_kind; agent review is not human validation")
    verdicts = review.get("verdicts", [])
    if not isinstance(verdicts, list):
        return errors + ["review verdicts must be a list"]
    by_id = {v.get('id'): v for v in verdicts if isinstance(v, dict)}
    if len(by_id) != len(verdicts):
        errors.append("review verdicts need unique lesson ids")
    for lesson in data['lessons']:
        v = by_id.get(lesson['id'], {})
        if v.get('verdict') != 'keep':
            errors.append(f"{lesson['id']}: needs a keep verdict after revisions")
        for key in ('evidence_check', 'alternative_check', 'plain_language_check', 'translation_check'):
            if not nonempty(v.get(key)):
                errors.append(f"{lesson['id']}: reviewer must explain {key}")
        reopened = v.get('reopened', [])
        if not isinstance(reopened, list) or not reopened or any(not isinstance(p, str) or
                not (folder / p).is_file() for p in reopened):
            errors.append(f"{lesson['id']}: reviewer must list actual reopened evidence files")
    if not signing and review.get('source_digest') != digest(folder, data):
        errors.append("lesson evidence/text changed or review unsigned; independent re-review required")
    return errors


def check(folder: Path, *, reviewed: bool = True) -> list[str]:
    try:
        data = read(folder / 'lessons.json')
        errors = validate(data, folder)
        return errors or (review_errors(folder, data) if reviewed else [])
    except (OSError, ValueError, TypeError) as ex:
        return [f'lessons: {ex}']


def stamp_review(folder: Path) -> list[str]:
    errors = check(folder, reviewed=False)
    if errors:
        return errors
    data = read(folder / 'lessons.json')
    errors = review_errors(folder, data, signing=True)
    if not errors:
        path = folder / 'lesson-review.json'
        review = read(path)
        review['source_digest'] = digest(folder, data)
        review['learning_validation'] = 'not_measured'
        write(path, review)
    return errors


def clock(t: float) -> str:
    # The film grammar supports tenths. Carry rounding across minute boundaries.
    tenths = round(t * 10)
    minutes, remainder = divmod(tenths, 600)
    seconds, decimal = divmod(remainder, 10)
    return f'{minutes:02d}:{seconds:02d}' + (f'.{decimal}' if decimal else '')


def script(data: dict, lang: str) -> str:
    """One cue question before the choice; explanation after play resumes. No outcome-first lecture."""
    eps = {ep['id']: ep for ep in data['episodes']}
    lines = ['# Generated from reviewed lessons.json; edit the source and re-review.', '', data['introduction'][lang], '']
    for context in data.get('context_scenes', []):
        lines += [f"![{context['caption'][lang]}]({context['visual'][lang]})", '', context['narration'][lang], '']
    for lesson in data['lessons']:
        ep, words = eps[lesson['episode_id']], lesson['text'][lang]
        lines += [f"![{words['title']}](clip:{clock(ep['start'])}-{clock(ep['end'])})", '', words['look'], '']
        marks = ' '.join(f'{x:.3f},{y:.3f}' for x, y in ep.get('marks', []))
        label = words.get('freeze_label', words['title']).replace('"', '')
        lines += [f"> {clock(ep['decision_t'])} {marks} \"{label}\"", '', words['question'], '', '>', '']
        lines += [words['good'] if lesson['kind'] == 'good' else words['change'], '', words['rationale'], '']
        # Keep the next-game instruction on a clear card, not a long hold on an unrelated outcome frame.
        lines += ['## ' + ('下次 · ' if lang == 'zh' else 'Next time · ') + words['title'], '',
                  words['next'], '', words['exception'], '']
    lines += ['## ' + ('下次带走这几件事' if lang == 'zh' else 'Take this into the next game'), '', data['closing'][lang], '']
    return '\n'.join(lines)


def public_data(data: dict, version: str) -> dict:
    """Explicit allowlist: never serialize notebooks, filesystem paths or private source notes into a page."""
    eps = {ep['id']: ep for ep in data['episodes']}
    cards = []
    for lesson in data['lessons']:
        ep = eps[lesson['episode_id']]
        cards.append({'id': lesson['id'], 'kind': lesson['kind'], 'episode_id': ep['id'],
                      'start': ep['start'], 'end': ep['end'], 'decision_t': ep['decision_t'],
                      'text': {lang: {k: words[k] for k in (*TEXT_FIELDS, 'choices')} for lang, words in
                               lesson['text'].items() if lang in data['languages']}})
    return {'schema_version': 1, 'version': version, 'languages': data['languages'], 'lessons': cards}


def compile_lessons(folder: Path) -> list[str]:
    errors = check(folder)
    if errors:
        return errors
    data = read(folder / 'lessons.json')
    version = digest(folder, data)
    outputs = {}
    for lang in data['languages']:
        path = folder / f'film.{lang}.md'
        path.write_text(script(data, lang), encoding='utf8')
        outputs[path.name] = sha(path)
    path = folder / 'lesson.public.json'
    write(path, public_data(data, version))
    outputs[path.name] = sha(path)
    write(folder / 'lesson-build.json', {'source_digest': version, 'outputs': outputs,
                                       'learning_validation': 'not_measured'})
    return []


def derivative_errors(folder: Path) -> list[str]:
    """Both languages become stale together; manual downstream edits cannot bypass source review."""
    if not (folder / 'lessons.json').exists():
        return []
    errors = check(folder)
    if errors:
        return errors
    try:
        build = read(folder / 'lesson-build.json')
        if build.get('source_digest') != digest(folder):
            return ['lessons changed: re-review and compile all language derivatives']
        data = read(folder / 'lessons.json')
        required = {*(f'film.{lang}.md' for lang in data['languages']), 'lesson.public.json'}
        outputs = build.get('outputs', {})
        if set(outputs) != required:
            return ['lesson build manifest is incomplete; compile again']
        return [f'{name} differs from approved lessons: compile again' for name in required
                if not (folder / name).is_file() or sha(folder / name) != outputs[name]]
    except (OSError, ValueError, TypeError) as ex:
        return [f'lesson build missing or unreadable: {ex}']


def evaluation_summary(records: list[dict]) -> dict:
    """Separate human comprehension, retention, opportunity-based transfer and agent audits.

    Unknown opportunities stay unknown. Neither clicks, preferences nor made shots prove a good decision.
    """
    out = {'agent_audits': 0, 'human_comprehension': [], 'retention': [], 'game_transfer': [], 'errors': []}
    for i, record in enumerate(records):
        if not isinstance(record, dict) or not all(nonempty(record.get(k)) for k in
                ('lesson_id', 'lesson_version', 'rater_id', 'rater_kind', 'phase')):
            out['errors'].append(f'record {i}: missing identity/version/phase')
            continue
        if record['rater_kind'] == 'agent':
            out['agent_audits'] += 1
            continue
        if record['rater_kind'] != 'human':
            out['errors'].append(f'record {i}: rater_kind must be human or agent')
            continue
        phase = record['phase']
        if phase in ('comprehension', 'retention'):
            if any(type(record.get(k)) is not bool for k in ('cue_understood', 'action_understood', 'exception_understood')) \
                    or not nonempty(record.get('viewer_id')) or not nonempty(record.get('viewer_response')) \
                    or record['viewer_id'] == record['rater_id']:
                out['errors'].append(f'record {i}: actual viewer response and independent cue/action/exception judgements required')
                continue
            out['human_comprehension' if phase == 'comprehension' else phase].append(record)
        elif phase == 'game_transfer':
            counts = [record.get(k) for k in ('opportunities', 'appropriate_decisions', 'executed')]
            if any(c is not None and (type(c) is not int or c < 0) for c in counts) or (
                    counts[0] is not None and any(c is not None and c > counts[0] for c in counts[1:])):
                out['errors'].append(f'record {i}: invalid opportunity counts')
                continue
            out['game_transfer'].append({**record, 'decision_rate': counts[1] / counts[0]
                                        if counts[0] and counts[1] is not None else None})
        else:
            out['errors'].append(f'record {i}: unknown phase')
    out['learning_status'] = 'not_measured' if not out['human_comprehension'] else 'human_observations_only'
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=('check', 'sign', 'compile', 'evaluate'))
    parser.add_argument('folder', type=Path)
    parser.add_argument('--draft', action='store_true', help='check source structure without independent review')
    parser.add_argument('--records', type=Path, help='evaluation records; no fabricated human responses')
    args = parser.parse_args(argv)
    if args.command == 'evaluate':
        if not args.records:
            parser.error('evaluate requires --records')
        result = evaluation_summary(read(args.records))
        write(args.folder / 'lesson-evaluation.json', result)
        errors = result['errors']
    else:
        errors = check(args.folder, reviewed=not args.draft) if args.command == 'check' else \
            stamp_review(args.folder) if args.command == 'sign' else compile_lessons(args.folder)
    for error in errors:
        print(error)
    print(f'lessons {args.command}: ' + ('FAIL' if errors else 'PASS (learning effectiveness not inferred)'))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
