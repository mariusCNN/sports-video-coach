"""Prepare leak-free pre-action reference prompts and summarize independent review ratings.

This is a file-based harness, not a new model client. Reference annotations may be provisional;
their provenance is retained. Never score a coach's prose using its own self-assessment.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import lessons


def validate_cases(cases: list[dict], folder: Path) -> list[str]:
    if not isinstance(cases, list) or not cases:
        return ['reference set must be a non-empty list']
    errors, ids, games = [], set(), {}
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f'case {i}: must be an object')
            continue
        tag = str(case.get('episode_id', i))
        for key in ('episode_id', 'game_id', 'recurrence_group', 'question'):
            if not lessons.nonempty(case.get(key)):
                errors.append(f'{tag}: {key} required')
        if case.get('episode_id') in ids:
            errors.append(f'{tag}: duplicate episode')
        ids.add(case.get('episode_id'))
        split = case.get('split')
        if split not in ('development', 'held_out'):
            errors.append(f'{tag}: split must be development or held_out')
        game = case.get('game_id')
        if game in games and games[game] != split:
            errors.append(f'{tag}: same game appears in both splits')
        games[game] = split
        decision = case.get('decision_t')
        if not lessons.number(decision) or decision < 0:
            errors.append(f'{tag}: numeric decision_t required')
            continue
        frames = case.get('pre_action_frames')
        if not isinstance(frames, list) or not frames:
            errors.append(f'{tag}: pre_action_frames required')
        else:
            for frame in frames:
                if not isinstance(frame, dict) or not lessons.number(frame.get('t')) or not 0 <= frame['t'] <= decision:
                    errors.append(f'{tag}: a pre-action frame leaks a later time')
                elif not isinstance(frame.get('path'), str) or not (folder / frame['path']).is_file():
                    errors.append(f'{tag}: pre-action frame missing')
        cues = case.get('pre_action_cues')
        if not isinstance(cues, list) or not cues or any(not isinstance(cue, dict) or not lessons.nonempty(cue.get('text'))
                or not lessons.number(cue.get('t')) or not 0 <= cue['t'] <= decision for cue in cues):
            errors.append(f'{tag}: cues need text and a time no later than decision_t')
        annotation = case.get('annotation', {})
        if not isinstance(annotation, dict) or annotation.get('kind') not in ('agent_provisional', 'human_adjudicated') \
                or any(not lessons.nonempty(annotation.get(k)) for k in ('author', 'reviewer', 'adjudication')):
            errors.append(f'{tag}: annotation provenance and adjudication required')
    return errors


def prepare(cases: list[dict], source_folder: Path, output: Path) -> list[str]:
    errors = validate_cases(cases, source_folder)
    if errors:
        return errors
    prompts = []
    for case in cases:
        # No outcome, reference answer, source narrative or future contact sheet crosses this boundary.
        prompts.append({k: case[k] for k in ('episode_id', 'game_id', 'split', 'decision_t', 'question',
                                            'pre_action_cues', 'pre_action_frames')})
        prompts[-1]['pre_action_frames'] = [dict(t=f['t'], path=str((source_folder / f['path']).resolve()))
                                            for f in case['pre_action_frames']]
        prompts[-1]['pre_action_cues'] = [dict(t=c['t'], text=c['text']) for c in case['pre_action_cues']]
    lessons.write(output / 'preaction-prompts.json', prompts)
    manifest = dict(episodes=len(cases), games=len({c['game_id'] for c in cases}),
                    recurrence_groups=len({(c['game_id'], c['recurrence_group']) for c in cases}),
                    per_split={s:sum(c['split']==s for c in cases) for s in ('development','held_out')},
                    annotation_kinds=sorted({c['annotation']['kind'] for c in cases}),
                    learning_effectiveness='not_measured', model_comparison='not_run',
                    frame_hashes={f['path']:lessons.sha(source_folder / f['path']) for c in cases for f in c['pre_action_frames']})
    lessons.write(output / 'reference-manifest.json', manifest)
    lessons.write(output / 'reference-key.private.json', cases)
    return []


def ratings_summary(cases: list[dict], ratings: list[dict]) -> dict:
    """Aggregate independent ratings without treating unreviewed/unclear cases as successes."""
    by_id = {c['episode_id']: c for c in cases}
    seen, groups, errors = set(), {}, []
    for i, rating in enumerate(ratings):
        if not isinstance(rating, dict) or rating.get('episode_id') not in by_id:
            errors.append(f'rating {i}: unknown episode')
            continue
        key = (rating['episode_id'], rating.get('variant'), rating.get('reviewer'))
        if key in seen:
            errors.append(f'rating {i}: duplicate episode/variant/reviewer')
            continue
        seen.add(key)
        if rating.get('reviewer_kind') not in ('independent_agent','human') \
                or any(not lessons.nonempty(rating.get(k)) for k in ('reviewer', 'author', 'variant')) \
                or rating.get('reviewer') == rating.get('author'):
            errors.append(f'rating {i}: independent reviewer required')
            continue
        required = ('fact_support', 'conditional_action', 'plain_language')
        if any(rating.get(k) not in ('pass','fail','unclear') for k in required):
            errors.append(f'rating {i}: pass/fail/unclear judgements required for each dimension')
            continue
        group = groups.setdefault(f"{rating.get('variant')}:{rating['reviewer_kind']}:{by_id[rating['episode_id']]['split']}",
                                  {k:dict.fromkeys(('pass','fail','unclear'),0) for k in required})
        for field in required:
            group[field][rating[field]] += 1
    return dict(groups=groups, errors=errors, learning_effectiveness='not_measured',
                note='Descriptive independent ratings on selected episodes; not whole-game accuracy or a causal efficacy estimate.')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=('prepare','score'))
    parser.add_argument('--cases', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--ratings', type=Path)
    args = parser.parse_args(argv)
    cases = lessons.read(args.cases)
    errors = validate_cases(cases, args.cases.parent)
    if not errors:
        if args.command == 'prepare':
            errors = prepare(cases, args.cases.parent, args.out)
        elif args.ratings:
            result = ratings_summary(cases, lessons.read(args.ratings))
            lessons.write(args.out / 'ratings-summary.json', result)
            errors = result['errors']
        else:
            parser.error('score requires --ratings')
    for error in errors:
        print(error)
    print(f'lesson-bench {args.command}: ' + ('FAIL' if errors else 'PASS'))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
