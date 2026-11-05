"""Pre-outcome questions. Only the public export is rendered; answers stay in the browser."""
from __future__ import annotations

import html
from pathlib import Path

from . import clips, lessons


def panel(folder: Path, lang: str, embed: bool = False) -> str:
    path = folder / 'lesson.public.json'
    if not path.is_file():
        return ''
    data = lessons.read(path)
    zh, esc = lang == 'zh', html.escape
    from .render_html import data_uri

    def src(start, end):
        clip = clips.clip_path(folder, lessons.clock(start), lessons.clock(end))
        return esc(data_uri(clip) if embed and clip.exists() else clip.relative_to(folder).as_posix(), quote=True)

    def poster(start, end):
        frame = clips.clip_path(folder, lessons.clock(start), lessons.clock(end)).with_suffix('.jpg')
        if not frame.exists():
            return ''
        return ' poster="' + esc(data_uri(frame) if embed else frame.relative_to(folder).as_posix(), quote=True) + '"'

    rows = []
    for item in data['lessons']:
        w = item['text'].get(lang)
        if not w:
            continue
        key = esc(f"svc-lesson:{data['version']}:{item['id']}", quote=True)
        choices = ''.join(f'<button type="button" class="lesson-choice" data-choice="{esc(c["id"], quote=True)}" '
                          f'data-why="{esc(c["why"], quote=True)}">{esc(c["text"])}</button>' for c in w['choices'])
        labels = (('good', '做得好' if zh else 'What worked'), ('change', '要改什么' if zh else 'What to change'),
                  ('next', '下次怎么做' if zh else 'Next time'), ('exception', '什么时候换个办法' if zh else 'When to change'))
        explanation = ''.join(f'<p><b>{label}</b><br>{esc(w[field])}</p>' for field, label in labels)
        rows.append(f'''<section class="lesson-card" id="{lang}-lesson-{esc(item['id'], quote=True)}" data-lesson="{esc(item['id'], quote=True)}" data-key="{key}"
            data-version="{esc(data['version'], quote=True)}" data-language="{lang}">
          <h3>{esc(w['title'])}</h3><p>{esc(w['look'])}</p>
          <video class="lesson-before" controls playsinline preload="none" src="{src(item['start'], item['decision_t'])}"{poster(item['start'], item['decision_t'])}
            aria-label="{'先看动作之前' if zh else 'Watch before the choice'}"></video>
          <p><b>{esc(w['question'])}</b></p><div class="lesson-options">{choices}</div>
          <div class="lesson-answer" hidden><p class="lesson-feedback" role="status"></p>
            <video class="lesson-after" controls playsinline preload="none" src="{src(item['start'], item['end'])}"{poster(item['start'], item['end'])}
              aria-label="{'看完整回合' if zh else 'Watch the full play'}"></video>
            <p>{esc(w['rationale'])}</p>{explanation}
            <label>{'用自己的话：你先看哪里？接着怎么做？' if zh else 'In your words: what do you look for, then do?'}
              <textarea class="lesson-recall" rows="2" maxlength="600"></textarea></label>
            <button type="button" class="lesson-save">{'保存这句提醒' if zh else 'Save my reminder'}</button>
            <span class="lesson-saved" role="status"></span>
          </div></section>''')
    return (f'<div class="lesson-room"><h2>{"先选一下，再看结果" if zh else "Make a choice, then watch"}</h2>'
            f'<p>{"选一个你会用的办法，再看这个回合。你的回答只保存在这台设备。" if zh else "Choose what you would do, then watch the play. Answers stay on this device."}</p>'
            + ''.join(rows) + f'<button type="button" class="lesson-export">{"导出我的回答" if zh else "Export my answers"}</button></div>')


ASSETS = r'''<style>
.lesson-room{margin:1.5rem 0;padding:1rem;border:1px solid var(--line,#444);border-radius:16px}
.lesson-card{padding:1rem 0;border-bottom:1px solid var(--line,#444);max-width:75ch}
.lesson-card p{max-width:40em;line-height:1.65}.lesson-card video{width:100%;height:auto;display:block;border-radius:10px}
.lesson-options{display:grid;gap:.6rem;margin:.8rem 0}.lesson-room button{font:inherit;text-align:left;padding:.8rem 1rem;
border:1px solid var(--line,#777);border-radius:10px;color:inherit;background:transparent;cursor:pointer;min-height:44px;white-space:normal}
.lesson-room button:focus-visible{outline:3px solid #ad9fff}.lesson-choice[aria-pressed=true]{border-color:#ad9fff;background:#6250d633}
.lesson-card textarea{box-sizing:border-box;display:block;width:100%;font:inherit;padding:.7rem;color:inherit;background:transparent;
border:1px solid #777;border-radius:8px;margin:.5rem 0}.lesson-answer[hidden]{display:none}.lesson-saved{font-size:.85rem;margin-left:.5rem}
</style><script>
(()=>{
const cards=[...document.querySelectorAll('.lesson-card')];
const read=key=>{try{return JSON.parse(localStorage.getItem(key)||'null')}catch{return null}};
const put=(key,v)=>{try{localStorage.setItem(key,JSON.stringify(v));return true}catch{return false}};
for(const card of cards){
 const key=card.dataset.key, recall=card.querySelector('.lesson-recall');
 const reveal=(id)=>{const b=[...card.querySelectorAll('.lesson-choice')].find(x=>x.dataset.choice===id);if(!b)return;
  card.querySelector('.lesson-before').pause();card.querySelector('.lesson-answer').hidden=false;
  card.querySelector('.lesson-feedback').textContent=b.dataset.why;
  card.querySelectorAll('.lesson-choice').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));};
 const hydrate=()=>{const prior=read(key);if(prior){reveal(prior.choice);recall.value=prior.recall||'';}};
 hydrate();
 // Translations share one response. Keep both cards current before a language switch can expose either.
 document.addEventListener('lesson-record',event=>{if(event.detail===key)hydrate();});
 card.querySelectorAll('.lesson-choice').forEach(b=>b.addEventListener('click',()=>{
  const before=read(key), now=new Date().toISOString();
  const record={lesson_id:card.dataset.lesson,lesson_version:card.dataset.version,language:card.dataset.language,
    first_choice:before?.first_choice||b.dataset.choice,choice:b.dataset.choice,first_at:before?.first_at||now,
    updated_at:now,recall:before?.recall||'',measurement:'self_response_not_comprehension_score'};
  const ok=put(key,record);reveal(b.dataset.choice);
  if(ok)document.dispatchEvent(new CustomEvent('lesson-record',{detail:key}));
 }));
 card.querySelector('.lesson-save').addEventListener('click',()=>{
  const old=read(key);if(!old)return;
  const ok=put(key,{...old,recall:recall.value,updated_at:new Date().toISOString()});
  if(ok)document.dispatchEvent(new CustomEvent('lesson-record',{detail:key}));
  card.querySelector('.lesson-saved').textContent=card.dataset.language==='zh'?(ok?'已保存':'浏览器未能保存'):(ok?'Saved':'Browser could not save');
 });
}
document.querySelectorAll('.lesson-export').forEach(button=>button.addEventListener('click',()=>{
 const unique=new Map(cards.map(c=>[c.dataset.key,read(c.dataset.key)]));
 const blob=new Blob([JSON.stringify([...unique.values()].filter(Boolean),null,2)],{type:'application/json'});
 const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='lesson-answers.json';link.click();
 setTimeout(()=>URL.revokeObjectURL(link.href),1000);
}));
})();</script>'''
