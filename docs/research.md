# Open-source options and how they were adapted

Checked 2026-10-15. This compares the relevant projects; it is not an exhaustive ranking of GitHub. Star counts are only a rough guide to community size.

| Project | Size shown on its page | Reusable parts | Still needed for amateur games |
|---|---:|---|---|
| [roboflow/sports](https://github.com/roboflow/sports) | ~5.4k stars | Sports video tools, team classification recipe; also a [basketball branch](https://github.com/roboflow/sports/tree/feat/basketball) | Court registration for each gym, player identity in amateur games, tactics and event review |
| [roboflow/supervision](https://github.com/roboflow/supervision) | ~51.2k stars | Generic detection data structures, annotation, tracking ecosystem | Does not produce possessions, tactics or advice for basketball |
| [roboflow/rf-detr](https://github.com/roboflow/rf-detr) | ~9.8k stars | Local object detection; this project uses RF-DETR-L | Teams, identities, court position, game semantics |
| [abdullahtarek/basketball_analysis](https://github.com/abdullahtarek/basketball_analysis) | ~192 stars | Reference implementation of basketball detection, ball/player tracking and team classification | Does not produce coach reports; needs adapting to each camera position and court |

All pages are the projects' own. The `basketball_analysis` README states MIT; it is used only as a reference and no code is copied from it. Models and weights follow the terms on their own release pages.

## What the pipeline uses

Detection and court mapping, SigLIP embeddings, ByteTrack tracking and 4-bit Qwen3-VL-4B jersey reading all run locally. Team labels are confirmed once from a cluster montage (which cluster is us, them, referees). The court is kept registered with hand-picked keyframes, painted lines, optical flow and SIFT relocalisation, instead of applying a model trained on professional broadcast cameras to an amateur gym.

Events come from vision-agent review of frame sheets sampled once per second. This works well for offensive actions, spacing and transition defence, but occlusion near the rim and the sampling interval often hide whether a shot went in. Unknown results therefore stay unknown: without a league feed the report does not claim a full score, official shooting percentages or official possession efficiency. Raw video and intermediate files stay on the local machine in the gitignored workspace.

## References for the tactical advice

Advice is based on what the film shows and on the [FIBA WABC coaching resources](https://about.fiba.basketball/en/wabc-documents). Most relevant: Level 1 on pass-and-cut and spacing, support after penetration, fast-break lanes, offensive rebounding versus getting back; Level 2 on attacking zone defences. Tactics boards show plans to run in the next game, not plays that already happened on film.
