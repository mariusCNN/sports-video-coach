# Sources for the fitness exercise library and knowledge base

Every `refs` key in `exercises.json` and every source tag in `../knowledge/*.md` resolves to an entry below.
Each entry was looked up during authoring (2026-11). Most were checked against the abstract or a repository
record, not the full text; where a figure came only from a secondary summary, that is said.

## How to read the data

- `muscles[].share` is **relative training emphasis** (sums to 100), not EMG %. Most shares are coach estimates;
  `muscles_basis` names the reference and says "estimate" where no study measured it.
- `(coach rule of thumb)` in the knowledge files marks practice that is common but not tested by a cited study.
- Nothing here was copied from ExRx or other non-free sites. Setup, cues and fault text are written for this repo.

## Data

### `fedb`

- yuhonas, *free-exercise-db: open public domain exercise dataset in JSON format* (800+ exercises; the copy used had 876).
- https://github.com/yuhonas/free-exercise-db
- License: **Unlicense** (public domain dedication), as shown on the repository page. The page states no separate license for images; this library does not ship its images.
- Used for: `fedb_id` links and as the starting point for each exercise's muscle list.

## Squat, hinge and single-leg mechanics

### `gullett2009`

- Gullett JC, Tillman MD, Gutierrez GM, Chow JW. A biomechanical comparison of back and front squats in healthy trained individuals. *J Strength Cond Res*. 2009;23(1):284-292.
- https://pubmed.ncbi.nlm.nih.gov/?term=A+biomechanical+comparison+of+back+and+front+squats+in+healthy+trained+individuals (DOI not verified)
- Supports: similar muscle activity front vs back squat; back squat had higher knee compressive force and extensor moment at the loads used; front squat as a knee-friendly main squat.

### `bryanton2012`

- Bryanton MA, Kennedy MD, Carey JP, Chiu LZF. Effect of squat depth and barbell load on relative muscular effort in squatting. *J Strength Cond Res*. 2012;26(10):2820-2828.
- https://era.library.ualberta.ca/items/8562bc34-0ecf-4d8c-92b0-6ace198be6b1
- Supports: knee-extensor effort rises with depth but not load; hip-extensor effort rises with depth and load; plantar flexors with load. Ten women, 50-90% 1RM.

### `schoenfeld2010`

- Schoenfeld BJ. Squatting kinematics and kinetics and their application to exercise performance. *J Strength Cond Res*. 2010;24(12):3497-3506. doi:10.1519/JSC.0b013e3181bac2d7
- https://pubmed.ncbi.nlm.nih.gov/20182386/
- Supports: general squat biomechanics review (ankle, knee, hip, spine) and technique recommendations.

### `contreras2015`

- Contreras B, Vigotsky AD, Schoenfeld BJ, Beardsley C, Cronin J. A comparison of gluteus maximus, biceps femoris, and vastus lateralis EMG activity in the back squat and barbell hip thrust exercises. *J Appl Biomech*. 2015;31(6):452-458.
- https://pubmed.ncbi.nlm.nih.gov/26214739/
- Supports: hip thrust had higher glute and biceps femoris EMG than the back squat; vastus lateralis similar. EMG only, 13 trained women.

### `plotkin2023`

- Plotkin DL, et al. Hip thrust and back squat training elicit similar gluteus muscle hypertrophy and transfer similarly to the deadlift. *Front Physiol*. 2023;14:1279170. doi:10.3389/fphys.2023.1279170
- https://pmc.ncbi.nlm.nih.gov/articles/PMC10593473/
- Supports: similar glute growth after 9 weeks; squats grew quads and adductors more; strength gains specific to the trained lift. Higher hip-thrust EMG did not predict more growth.

### `swinton2011`

- Swinton PA, Stewart A, Agouris I, Keogh JWL, Lloyd R. A biomechanical analysis of straight and hexagonal barbell deadlifts using submaximal loads. *J Strength Cond Res*. 2011;25(7):2000-2009. doi:10.1519/JSC.0b013e3181e73f87
- https://pubmed.ncbi.nlm.nih.gov/21659894/
- Supports: hex (trap) bar allowed higher 1RM and greater peak force/power. Lower lumbar and higher knee moments for the hex bar come from secondary summaries (not checked against full text).

### `mackey2021`

- Mackey, Riemann. Biomechanical differences between the Bulgarian split-squat and back squat. *Int J Exerc Sci*. 2021;14(1).
- https://pmc.ncbi.nlm.nih.gov/articles/PMC8136570
- Supports: in the BSS (35% 1RM) vs back squat (70% 1RM), hip moment and work exceeded knee and ankle; knee range was smaller in the BSS.

## Weightlifting derivatives

### `suchomel2015`

- Suchomel TJ, Comfort P, Stone MH. Weightlifting pulling derivatives: rationale for implementation and application. *Sports Med*. 2015;45(6):823-839. doi:10.1007/s40279-015-0314-y
- https://dc.etsu.edu/etsu-works/4629
- Supports: clean pull, hang high pull, jump shrug, mid-thigh pull as catch-free derivatives; can be loaded above the catch 1RM; useful year-round.

### `comfort2011`

- Comfort P, Allen M, Graham-Smith P. Kinetic comparisons during variations of the power clean. *J Strength Cond Res*. 2011;25(12):3269-3274.
- https://salford-repository.worktribe.com/output/1440834/kinetic-comparisons-during-variations-of-the-power-clean
- Supports: at 60% power-clean 1RM, mid-thigh power clean and mid-thigh clean pull produced the highest peak force and RFD (16 rugby league players).

## Strength and athletic performance

### `suchomel2016`

- Suchomel TJ, Nimphius S, Stone MH. The importance of muscular strength in athletic performance. *Sports Med*. 2016;46(10):1419-1449. doi:10.1007/s40279-016-0486-0
- https://dc.etsu.edu/etsu-works/4641
- Supports: greater strength is associated with better jumping, sprinting and change of direction, and with lower injury risk.

### `suchomel2018`

- Suchomel TJ, Nimphius S, Bellon CR, Stone MH. The importance of muscular strength: training considerations. *Sports Med*. 2018;48(4):765-785. doi:10.1007/s40279-018-0862-z
- https://dc.etsu.edu/etsu-works/4659
- Supports: 2-5 min rest for strength-power; weaker athletes build strength before emphasising power; eccentric and bilateral training.

### `seitz2014`

- Seitz LB, et al. Increases in lower-body strength transfer positively to sprint performance: a systematic review with meta-analysis. *Sports Med*. 2014;44(12):1693-1702. doi:10.1007/s40279-014-0227-1
- https://pubmed.ncbi.nlm.nih.gov/25059334/
- Supports: squat strength gains correlated with sprint gains (r = -0.77; 15 studies, 510 subjects); mean sprint improvement about 3%.

### `lake2012`

- Lake JP, Lauder MA. Kettlebell swing training improves maximal and explosive strength. *J Strength Cond Res*. 2012;26(8):2228-2233.
- https://eprints.chi.ac.uk/id/eprint/266/
- Supports: 6 weeks of twice-weekly swings raised half-squat 1RM and jump height, not different from jump-squat training (21 men).

### `harper2022`

- Harper DJ, McBurnie AJ, Dos Santos T, et al. Biomechanical and neuromuscular performance requirements of horizontal deceleration: a review with implications for random intermittent multi-directional sports. *Sports Med*. 2022;52(10):2321-2354. doi:10.1007/s40279-022-01693-0
- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9474351/
- Supports: deceleration has high early-stance impact forces and loading rates; braking force control and attenuation; eccentric, concentric, isometric and reactive strength all matter.

### `dorn2012`

- Dorn TW, Schache AG, Pandy MG. Muscular strategy shift in human running: dependence of running speed on hip and ankle muscle performance. *J Exp Biol*. 2012;215:1944-1956. doi:10.1242/jeb.064527
- https://pubmed.ncbi.nlm.nih.gov/22573774/
- Supports: soleus and gastrocnemius contribute most to vertical support up to ~7 m/s; hip muscles drive stride frequency at higher speeds. Modelling study, 9 subjects.

### `flanagan2008`

- Flanagan EP, Comyns TM. The use of contact time and the reactive strength index to optimize fast stretch-shortening cycle training. *Strength Cond J*. 2008;30(5):32-38. doi:10.1519/SSC.0b013e318187e25b
- https://pure.ul.ie/en/publications/the-use-of-contact-time-and-the-reactive-strength-index-to-optimi/
- Supports: using ground contact time and RSI to target fast SSC plyometrics and monitor them.

## Tendon, groin and hamstring

### `rio2015`

- Rio E, et al. Isometric exercise induces analgesia and reduces inhibition in patellar tendinopathy. *Br J Sports Med*. 2015;49(19):1277-1283.
- https://pubmed.ncbi.nlm.nih.gov/25979840/
- Supports: in 6 volleyball players, isometric contractions reduced pain on the single-leg decline squat for at least 45 min, more than isotonic. Very small sample; treat as an option, not a guarantee.

### `breda2021`

- Breda SJ, et al. Effectiveness of progressive tendon-loading exercise therapy in patients with patellar tendinopathy: a randomised clinical trial. *Br J Sports Med*. 2021;55(9):501-509.
- https://bjsm.bmj.com/content/55/9/501
- Supports: progressive loading (isometric to isotonic to energy-storage to sport) beat eccentric therapy on VISA-P at 24 weeks (28 vs 18 points; n = 76).

### `beyer2015`

- Beyer R, et al. Heavy slow resistance versus eccentric training as treatment for Achilles tendinopathy: a randomized controlled trial. *Am J Sports Med*. 2015;43(7):1704-1711.
- https://clinicaltrials.gov/study/NCT00952042
- Supports: heavy slow calf training and eccentric training gave similar, lasting improvements in midportion Achilles tendinopathy (n = 58); HSR had higher satisfaction at 12 weeks.

### `vanderhorst2015`

- van der Horst N, Smits DW, Petersen J, Goedhart EA, Backx FJG. The preventive effect of the Nordic hamstring exercise on hamstring injuries in amateur soccer players: a randomized controlled trial. *Am J Sports Med*. 2015;43(6):1316-1323.
- https://pubmed.ncbi.nlm.nih.gov/25794868/
- Supports: 25 Nordic sessions over 13 weeks reduced hamstring injury incidence (OR 0.282), not severity.

### `haroy2019`

- Harøy J, et al. The Adductor Strengthening Programme prevents groin problems among male football players: a cluster-randomised controlled trial. *Br J Sports Med*. 2019;53(3):150-157. doi:10.1136/bjsports-2017-098937
- https://bjsm.bmj.com/content/53/3/150
- Supports: one Copenhagen-adduction exercise, 3x/week preseason and 1x/week in season, cut groin-problem prevalence (13.5% vs 21.3%; OR 0.59).

## Programming and load monitoring

### `acsm2009`

- American College of Sports Medicine. Position stand: Progression models in resistance training for healthy adults. *Med Sci Sports Exerc*. 2009 (volume/pages not verified against the journal).
- https://www.sportgeneeskunde.com/wp-content/uploads/ACSM-Position-Stand-Progression-Models-in-Resistance-Training-for-Healthy-Adults.pdf
- Supports: progressive overload, specificity and variation as core principles. ACSM published an updated resistance-training statement in 2026 (https://acsm.org/science-spotlight-acsm-releases-new-position-stand-on-resistance-training/); its summary says training to failure and complex periodisation did not consistently change outcomes for healthy adults.

### `nsca_ltad2016`

- Lloyd R, Cronin J, Faigenbaum A, et al. National Strength and Conditioning Association position statement on long-term athletic development. *J Strength Cond Res*. 2016;30(6):1491-1509. doi:10.1519/JSC.0000000000001387
- https://dxpprod.nsca.com/globalassets/education/nsca_position_statement_on_ltad.pdf
- Supports: long-term development of strength and movement competence for health, performance and lower injury risk (10 pillars).

### `helms2016`

- Helms ER, Cronin J, Storey A, Zourdos MC. Application of the repetitions in reserve-based rating of perceived exertion scale for resistance training. *Strength Cond J*. 2016;38(4):42-49. doi:10.1519/SSC.0000000000000218
- https://openrepository.aut.ac.nz/items/92cefeac-7c32-44f1-bfbc-f48f4a5dd8cf/full
- Supports: RIR-based RPE scale (RPE 10 = 0 RIR) and set-by-set load adjustment.

### `weakley2021`

- Weakley J, Mann B, Banyard H, McLaren S, Scott T, Garcia-Ramos A. Velocity-based training: from theory to application. *Strength Cond J*. 2021;43(2):31-49. doi:10.1519/SSC.0000000000000560
- https://acuresearchbank.acu.edu.au/item/8x23v/velocity-based-training-from-theory-to-application
- Supports: velocity feedback, load-velocity profiles, velocity-loss thresholds and how VBT fits a microcycle.

### `pareja2017`

- Pareja-Blanco F, et al. Effects of velocity loss during resistance training on athletic performance, strength gains and muscle adaptations. *Scand J Med Sci Sports*. 2017.
- https://www.uloyola.es/en/research-transfer/publications/effects-of-velocity-loss-during-resistance-training-on-athletic-performance-strength-gains-and-muscle-adaptations-article
- Supports: 20% vs 40% velocity loss in the squat (22 men, 8 weeks): similar strength with ~40% fewer reps, larger jump gain with 20%; 40% gave more hypertrophy but a shift away from type IIX fibres.

### `cuthbert2024`

- Cuthbert M, Haff GG, McMahon JJ, Evans M, Comfort P. Microdosing: a conceptual framework for use as programming strategy for resistance training in team sports. *Strength Cond J*. 2024;46(2):180-201. doi:10.1519/SSC.0000000000000786
- https://salford-repository.worktribe.com/output/1891510/microdosing-a-conceptual-framework-for-use-as-programming-strategy-for-resistance-training-in-team-sports
- Supports: microdosing = splitting weekly volume into frequent short bouts; direct empirical research is limited; often confused with minimum effective dose.

### `wilson2012`

- Wilson JM, et al. Concurrent training: a meta-analysis examining interference of aerobic and resistance exercises. *J Strength Cond Res*. 2012;26(8):2293-2307.
- https://search.pedro.org.au/search-results/record-detail/34457
- Supports: concurrent training reduced strength and hypertrophy gains vs strength alone; running interfered, cycling did not; endurance frequency and duration related to interference.

### `bell2023`

- Bell L, et al. Integrating deloading into strength and physique sports training programmes: an international Delphi consensus approach. *Sports Med Open*. 2023;9:87.
- https://pmc.ncbi.nlm.nih.gov/articles/PMC10511399/
- Supports: consensus definition of a deload (reduced training stress to manage fatigue and restore readiness); no objective prevalence data.

### `schoenfeld2015tempo`

- Schoenfeld BJ, Ogborn DI, Krieger JW. Effect of repetition duration during resistance training on muscle hypertrophy: a systematic review and meta-analysis. *Sports Med*. 2015;45(4):577-585.
- https://pubmed.ncbi.nlm.nih.gov/25601394/
- Supports: similar hypertrophy for rep durations of 0.5-8 s when sets go to failure; very slow reps (>10 s) may be worse.

## Video measurement

### `munro2012`

- Munro A, Herrington L, Carolan M. Reliability of 2-dimensional video assessment of frontal-plane dynamic knee valgus during common athletic screening tasks. *J Sport Rehabil*. 2012;21(1):7-11.
- https://salford-repository.worktribe.com/output/1437145/reliability-of-two-dimensional-video-assessment-of-frontal-plane-dynamic-knee-valgus-during-common-athletic-screening-tasks
- Supports: 2D frontal-plane projection angle from a front camera is reliable within-day (ICC 0.59-0.88) for single-leg squat, single-leg landing and drop jump. Later reviews report validity vs 3D is task-dependent.
