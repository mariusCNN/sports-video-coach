# First 100 stars: launch and first-run experiment

The goal is 100 stars. This document tracks work and observed results; it does not predict a date or a conversion rate.
Start with developers who already use a coding agent and have a short sports-training video.

## Public evidence to lead with

- [Real shooting walkthrough](https://mariusding.github.io/sports-video-coach/case-study/): the author's existing public GIF.
- [Interactive sample report](https://mariusding.github.io/sports-video-coach/demo/): synthetic footage and a pre-written review.
- [Count it yourself](https://mariusding.github.io/sports-video-coach/benchmark/#count): a separate synthetic counting challenge.

The walkthrough is an edited demonstration, not proof of improved athletic performance.
Do not claim a runtime, model cost, independent user result or coaching accuracy without a recorded run supporting it.
Only link the new case-study page after its deployment has been verified.

## English launch copy

**Title:** My coding agent reviews my shooting practice and builds a coaching page

I play basketball and wanted to get more from my phone recordings. I built sports-video-coach so my coding agent
can review timestamped frames, then turn its observations into a page with the relevant video clips and practice suggestions.

Here is a walkthrough from my own shooting drill:
https://mariusding.github.io/sports-video-coach/case-study/

The generic workflow needs no GPU. A quick first run builds the local page and clips; narration and an explained
video can be added later. It needs Python 3.11, ffmpeg and your own coding agent. Frames read by the agent go to its provider.

It is alpha. I am looking for people who already use a coding agent and can try a short training clip of their own.
Where did the setup stop, and which observations were actually useful? Please describe the result without uploading private footage.

Code and instructions: https://github.com/mariusDing/sports-video-coach

## 中文发布文案

**标题：** 我让编程 agent 看自己的投篮录像，生成了能回看片段的复盘网页

我自己打篮球，手机里存了不少训练录像。我做了 sports-video-coach，让编程 agent 看带时间戳的帧，
再把观察到的问题、对应片段和练习建议整理成一个手机网页。

这里是我自己投篮练习的一段真实演示：
https://mariusding.github.io/sports-video-coach/case-study/

通用模式不需要 GPU。第一次可以只生成本地网页和片段，之后再加语音或讲解视频。
需要 Python 3.11、ffmpeg 和你自己的编程 agent；agent 读取的画面会发给它的模型服务商。

项目还是 alpha。我想找已经使用编程 agent、也有自己训练视频的人试一段短片：安装卡在哪一步？
哪些观察有用，哪些不准确？反馈用文字描述即可，不用上传私人录像。

源码和使用说明：https://github.com/mariusDing/sports-video-coach

## Ten-person first-run check

Give each volunteer the README, not a guided installation. Start with a 15–40 second clip they choose to process.
Do not gather their footage, authentication information or identifying player details.

Record only:

| Trial | OS | Agent | Setup succeeded? | First page completed? | Minutes to page | First blocking step | One useful observation? |
|---|---|---|---|---|---|---|---|
| 1–10 | | | | | | | |

Target: at least 8 of 10 finish a short-clip page using the README. Fix repeated blockers before another broad launch.
Keep an inability to review the footage distinct from an installation failure: `insufficient_evidence` is a valid result.
For a public case study, use material the author chooses to publish; preserve the synthetic-only issue reproduction rule.

## Four-week sequence

1. Lead the README and website with the real walkthrough; verify links on desktop and a 390 px phone.
2. Run the ten-person check; publish the install fixes and report the actual success/failure counts.
3. Update the existing Codex and Agent Skills discussions with the new evidence. Ask for specific feedback.
4. Publish a follow-up with the observed setup failures, corrections and useful outputs.

Use each community's posting rules. Reuse an existing thread when providing an update. Send invitations and publish
posts personally; this plan does not authorize automated messages or star actions.

## Measurement log

GitHub Insights supplies repository visitors and clones. The site has optional GoatCounter support via the
`GOATCOUNTER_CODE` repository variable; leave it unset until the owner has configured their own site.
Campaign links may use `?ref=codex-update`, `?ref=agent-skills-update` and `?ref=shooting-walkthrough`.
These identify visits to the site, not which individual later starred the repository.

| Period | Repo unique visitors | Unique cloners | Net stars | Site referrals | Trial pages completed | Repeated blocker |
|---|---|---|---|---|---|---|
| Before launch | | | | | | |
| Week 1 | | | | | | |
| Week 2 | | | | | | |
| Week 3 | | | | | | |
| Week 4 | | | | | | |

Low relevant traffic calls for better distribution. Traffic with repeated setup failures calls for install fixes.
Successful trials with little interest call for a clearer use case and stronger examples.

## Benchmark follow-up

Keep the benchmark a secondary entry until there are independent reruns. A useful next comparison pairs models or
effort settings on the same newly generated seed set, records identical input images and tool access, and reports
accuracy, completion rate, wall time and spend separately. Record limits and timeouts distinctly.
Do not launch more paid runs merely to fill the leaderboard; first recruit three independent reproductions.
