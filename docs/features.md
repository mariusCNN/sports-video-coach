# Feature and command catalog

Open-source sports video analysis, basketball analytics, computer vision and AI coaching for athletes,
amateur teams, volunteer coaches and coding agents. This catalog describes implemented capabilities;
availability depends on the selected sport, installed dependencies, footage and reviewed evidence.

[English README](../README.md) · [中文 README](../README.zh.md) · [Agent contract](../AGENTS.md)

## Video to coaching, for any sport

| Feature | Benefit | Entry point / requirement |
|---|---|---|
| Resumable end-to-end run | Stops at the exact step needing agent judgment; preserves completed work | `sports-video-coach run`; exit 3 requests an agent artifact, 0 means done |
| Multiple source videos | One ordered session timeline with source attribution | `run <video...>`; simultaneous camera angles are separate units |
| Timestamped contact sheets and zooms | Review long footage and revisit fast or ambiguous moments | `frames`, plugin review guides |
| Structured film review | Machine-readable moments with evidence and uncertainty | Agent-written JSON, checked by the selected plugin |
| Coaching report and drills | Each fix can include an action, practice drill and next-session target | Report guides and Markdown |
| Mobile HTML report | Read, switch language, watch supporting clips and listen in one page | `html`; standard pages or optional embedded/offline HTML |
| Source clips and slow replay | Check the action behind a coaching claim | `clips`, report clip references |
| Narrated report | Listen while travelling to training | `narrate`; online TTS receives narration text |
| Explained MP4 | Narration over clips/charts, freezes, annotations and subtitles | `film`; script must be reviewed |
| Artifact selection | Request only the outputs you need; keep older artifacts | `run --artifacts html film`, or unit/profile configuration |
| Eight generic languages | English, Chinese, Japanese, Korean, Spanish, French, German, Portuguese | `--lang`; basketball currently Chinese + English |
| Incremental rebuilds | Update affected outputs after source/report changes | Stage input tracking, stale-step checks, per-language scripts |
| Concurrent-run protection | Avoid two writers corrupting one unit | OS run lock and checkout-version checks |
| Static page QA | Detect broken anchors, missing assets and script/text issues | `page-check --strict --write-qa`; layout/playback still need a browser |
| Optional unlisted publishing | Stable report links for deliberate sharing | `publish` / `--publish`, Cloudflare account; links are not access control |
| Synthetic demo | Inspect all deliverables without private footage or an agent | `sports-video-coach demo` |

## Basketball games and team analysis

| Feature | Benefit | Basketball command(s) |
|---|---|---|
| League import and game setup | Align video, rosters, official scores and game context | `fetch`, `new-game`, `official`; current importer is Glory League |
| Player, ball and court detection | Collect measurements for later tracking/review | `extract`, `recalib`; local model dependencies, normally CUDA |
| Team classification and court tracks | Separate jersey colours and follow court-space movement | `embed`, `tracks` |
| Jersey-number evidence and chain repair | Support identity review across track fragments | `jersey`, `stitch`; inferred identities require verification |
| Ball trajectory and shot proposals | Locate actions worth reviewing | `ball-track`, `rim-scan`, `shot-proposals` |
| Court calibration and shot locations | Map source pixels into a FIBA court coordinate system | `calibrate`, `shot-locate`; quality depends on visible geometry |
| Possession and lineup review | Build a coherent sequence from trips and on-court players | `review`, `coach-sheets`, `merge-reviews`, `coach-check` |
| Tactical features and supported insights | Connect transition, spacing and defensive evidence to advice | `analyze`, `coach-summary`, `coach-features`, `coach-insights`, `coach-eval` |
| Official + reviewed box score | Keep official points/fouls distinct from film-counted actions | `box`, `official`, `plusminus` |
| Four Factors and possession breakdowns | Explain efficiency, turnovers, rebounding and free-throw opportunities | Reviewed summaries, team report tables |
| Shot charts and score flow | Explore shot zones and scoring runs | `report`, `momentum`, reviewed shot locations |
| Running load and matchups | Inspect per-stint distance/speed and shot-defense proximity | `load`, `matchups`; tracking/calibration quality matters |
| Team and focus-player reports | Team game plan plus a private individual deep dive | `run`, bilingual report and narration guides |
| Tactics replay and telestration | Show court movement and annotate relevant players | `replay`, `posters` |
| Phone reels | Follow a focus player in a vertical clip | `reels`; needs usable tracks |
| Opponent dossier and season view | Reuse previous games for rematches and progress review | `scout`, `season` |

## Training and movement

| Feature | Benefit | Entry points |
|---|---|---|
| Personal basketball workout | Join clips, find repetitions, review technique, deliver a training report | `train`, `train-new`, `train-scan`, `train-sheets`, `train-summary` |
| Movement-session review | Examine pose/contact timing and gait-related measurements | `move`, `move-new`, `move-scan`, `move-sheets`, `move-summary` |
| Practice-plan app | Turn recommendations into a usable schedule and progress tracker | `program`; optional sync and cue/car audio |
| Coaching knowledge base | Trace suggested drills and cues to the sport's writing guides | `prompts/`, `guide`; still requires judgment about the actual footage |

## Optional perception and evaluation

| Integration | Implemented feature | Current boundary |
|---|---|---|
| [OpenHoopVision](perception.md) | External pinned backend; shot/pass/dribble/rebound/possession candidates, pose/OCR/identity evidence, source clips, review decisions, conflicts and bilingual validation cards | Candidate evidence, not official statistics or automatically confirmed identities |
| [WASB](perception-lab.md) | Official basketball three-frame network, exact affine preprocessing, heatmap centres and explicit no-observation state | Weak transfer in the first private diagnostic; opt-in |
| [SAHI](perception-lab.md) | Real SAHI sliced prediction with a local RF-DETR adapter, full-image pass, overlap/coordinate restoration and NMS | Better recall can introduce false positives and extra inference cost |
| [KaliCalib](perception-lab.md) | Official landmark model, floor-only correspondences, FIBA metre conversion, geometric rejection and independent landmark scoring | Untrusted proposals; no default-camera fallback and no automatic calibration replacement |
| Source provenance | Video, frame, checkpoint and executed-source hashes; pinned upstream revisions; cache invalidation | Provenance identifies inputs; it does not establish accuracy |
| Independent evaluation | Shot-window matching; top-1 ball precision/recall, false positives, pixel-radius sensitivity; court reprojection checks | Manual labels and complete coverage required; small samples are diagnostic |
| Visual comparison | Interactive frame/overlay viewer, raw JSON and a four-way annotated MP4 | Local/private artifacts; failed predictions remain visible |
| Tracking evaluation | Label-free track diagnostics and HOTA/IDF1 against labelled MOT data | `track-eval`; proxy metrics alone are not tracking accuracy |

## For agents, researchers and plugin authors

- **Discoverable CLI:** `sports-video-coach plugins --json` describes available plugins, capabilities, requirements
  and stages. `hoop-tape-miner --help` lists basketball commands; each command has `--help`.
- **Explicit agent contract:** [AGENTS.md](../AGENTS.md), guides, exit codes and structured artifacts work with
  Claude Code, Codex, Cursor and other coding agents. [llms.txt](../llms.txt) is a concise navigation index.
- **Sport plugins:** `new-plugin` scaffolds a working plugin; hooks keep the core independent of basketball.
  Examples include a swim stroke-rate plugin and a jump-rope counting plugin. [Plugin guide](plugins.md).
- **Exact-ground-truth benchmark:** `bench` prepares synthetic drills, runs agent/model adapters, scores and
  validates submissions, and builds a leaderboard. It measures the stated task, not general coaching quality.
- **Local vision / optional services:** detection runs locally; an agent's viewed frames go to its model provider,
  narration uses online TTS, and publishing is explicit. [Privacy](privacy.md).
- **MIT project code:** external models and separately maintained source retain their own licenses.
  No private footage, rosters, credentials or labels are required in public contributions.

## Limits to keep visible

Footage quality, occlusion, moving cameras, lens distortion, neighbouring courts and changing jerseys can break
automatic measurements. Model confidence is not accuracy. A court homography maps floor points; it does not
recover the 3D position of an airborne basketball. This project does not promise automatic official box scores,
universal identity recognition, live officiating or medical diagnosis from movement video.

See [setup and workflow](playbook.md), [architecture](architecture.md), [research attribution](research.md)
and [contributing](../CONTRIBUTING.md). Never attach real player data to public issues or PRs.
