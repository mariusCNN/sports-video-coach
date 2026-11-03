# Technique on 2D video: what a good rep looks like and what we can measure

Source keys resolve in `../library/SOURCES.md`. `(coach rule of thumb)` = common practice, not tested by a cited study.

## Camera rules (read first)

- A 2D joint angle is only valid when the camera is **perpendicular to the plane of motion**. (coach rule of thumb)
- **Side view** (camera at hip height, 90 deg to the lifter): sagittal-plane metrics.
  - `depth`, `trunk_lean`, `tempo`, `bar_path`, `knee_travel`, `hip_extension`, `pause`, `rep_count`, `velocity_loss`, `ground_contact`
- **Front view** (camera at knee-hip height, facing the lifter): frontal-plane metrics.
  - `knee_valgus`, `pelvis_drop`, `symmetry`, `rep_count`
- An angle more than about 15-20 deg off-axis distorts both views. Ask for a re-film rather than guess. (coach rule of thumb)
- `ground_contact` needs at least 100 fps; at 30 fps one frame is 33 ms, too coarse for contacts near 200 ms. (coach rule of thumb)
- Each exercise lists its valid metrics per view in `exercises.json` (`views`).

## Evidence for 2D measures

- Frontal-plane knee valgus (2D projection angle) from a front camera is reliable within a day for single-leg squat, single-leg landing and drop jump (ICC 0.59-0.88). [munro2012]
- Agreement with 3D motion capture depends on the task. Report 2D valgus as a screen, not a diagnosis. [munro2012]
- All other angle thresholds below are (coach rule of thumb) unless tagged.

## Squat (back, front, goblet, box, safety bar)

**Good rep**

- Whole foot on the floor; knees track over the toes.
- Hips and chest rise together.
- Depth: hip crease at or below the top of the knee (`depth`), if the back stays neutral.

**Why depth matters**

- Deeper squats raise knee-extensor effort without more load; hip extensors need depth and load. [bryanton2012]
- Front squat: similar muscle activity to back squat with lower knee compressive force at the loads tested. [gullett2009]

**Flags** (coach rule of thumb)

- `trunk_lean` rising sharply at the start of the ascent = hips shooting up.
- `knee_valgus` visible on the way up, especially late in a set.
- `bar_path` drifting more than a few cm forward of mid-foot.

## Hinge (deadlift, trap bar, RDL, swing, hip thrust)

**Good rep**

- Neutral back; bar close to the legs (`bar_path`).
- Full hip lockout without leaning back (`hip_extension`).
- RDL: knee angle nearly fixed; hips move back (`knee_travel` stays small).

**Notes**

- Trap bar allowed higher loads and peak power than a straight bar. [swinton2011]
- Hip thrust: higher glute EMG than squat, but similar glute growth in training. [contreras2015] [plotkin2023]
- Swing: power comes from the hips; the bell floats to chest height. (coach rule of thumb)

## Olympic pull derivatives

**Good rep**

- Bar stays close; arms stay long until the hips have extended.
- Full triple extension (`hip_extension`), then shrug.
- Mid-thigh starts give the highest force and RFD among clean variations at 60% 1RM. [comfort2011]
- Pulls skip the catch and can be loaded above the clean 1RM. [suchomel2015]

**Flags** (coach rule of thumb)

- Early elbow bend before the bar passes mid-thigh.
- Bar looping away from the thighs (`bar_path`).

## Single leg and lunge

**Good rep**

- Knee over the second toe (`knee_valgus`, front view).
- Pelvis level (`pelvis_drop`, front view).
- Trunk steady; front foot flat.

**Notes**

- Bulgarian split squat: hip moment exceeded knee and ankle; knee range smaller than the back squat. [mackey2021]
- Film both sides with the same camera position to compare `symmetry`. (coach rule of thumb)
- A left-right difference over about 10-15% in reps or depth is worth a note, not a diagnosis. (coach rule of thumb)

## Isometrics

- Measure hold time (`pause`) and joint angle (`depth`).
- Hold steady for the prescribed time; no bouncing.
- Patellar-tendon isometrics: 30-45 s holds reduced pain in a very small study. [rio2015]

## Plyometrics

**Good rep**

- Quiet, soft landing; knees bend and track over the toes.
- Same depth on landing as on take-off for box jumps.
- Pogo: short contacts, knees nearly straight.

**Measures**

- Ground contact time and reactive strength index guide fast stretch-shortening training. [flanagan2008]
- Fast SSC is often defined as contact under about 250 ms. (coach rule of thumb)
- Stop the set when contacts get longer or landings get loud. (coach rule of thumb)

## Upper body

- Bench and push-up: elbows about 45 deg from the torso; body straight (`trunk_lean`).
- Pull-up: full hang to chin over bar; no kip (`rep_count` counts only full reps).
- Row: torso does not rotate.
- All thresholds here are (coach rule of thumb).

## Thresholds: evidence vs rule of thumb

| Check | Threshold | Status |
| --- | --- | --- |
| 2D knee valgus is reliable from the front | ICC 0.59-0.88 | evidence [munro2012] |
| Velocity loss cap for power | about 20% | evidence-informed [pareja2017] |
| Squat depth: hip at or below knee | visual | rule of thumb |
| Off-axis camera limit | about 15-20 deg | rule of thumb |
| Fast SSC contact | under about 250 ms | rule of thumb |
| Left-right difference worth noting | about 10-15% | rule of thumb |
