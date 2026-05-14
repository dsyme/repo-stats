# DRAFT: The Impact of Automated Repository Maintenance Assistance

**Date:** May 14, 2026

**Authors:** Don Syme, Florian Verdonck, Krzysztof Cieślak, Tomas Grosup, Scott Hanselman, Peli de Halleux, Mara Kiefer, Russell Horton, Tamás Szabó, Landon Cox, Alex Gorischek, David Slater, Idan Gazit, Insop Song, Luke Edwards, Maggie Appleton, Nate Butler, Rahul Pandita, Terkel Gjervig Nielsen

## Executive Summary

We analyze the impact of Repo Assist, a proactive AI repository agent, across 15 open source repositories that adopted it between February and March 2026. The agent **reduced open issue counts in every repository** — 651 issues net. Across all repositories, some of which were previously largely dormant, **issue closure velocity increased by a median of 9×** and **PR merge velocity by a median of 9×** after adoption, transforming largely dormant projects into actively maintained ones.

Modeling repositories as **human-agent software factories** reveals that the single most important factor determining outcomes is the rate at which maintainers decide to act on the agent's output: the human is firmly in the loop, and the factory's throughput is gated by human decision-making. Maintainers pushed additional commits to **37% of Repo Assist PRs**, often using Copilot as a secondary agent to extend the work, while the issue reopen rate after agent-assisted closure is just 3.3%.

## Introduction

[Repo Assist](https://github.com/githubnext/agentics/blob/main/docs/repo-assist.md) is a proactive AI repository agent that performs maintenance tasks in an open source repository, effectively as a virtual assistant member of an open source repository's maintenance team. Unlike one-shot AI coding assistants that respond to individual prompts, Repo Assist runs autonomously on a schedule and in response to events — triaging issues, investigating bugs, creating draft pull requests, and responding to contributor questions. It represents an emerging model of **continuous AI-assisted repository automation**, where the AI agent is always on, always watching, and always ready to act.

This report analyzes the impact of Repo Assist across 15 open source repositories (11 F#, 1 C#, 1 Python, 1 Ruby, 1 multi-language) that adopted the workflow between February and March 2026. The results paint a nuanced picture: the AI agent produces dramatic results in some repositories, but **outcomes depend critically on human engagement**. The human is still firmly in the loop — Repo Assist creates draft PRs that require human review and merge, and its investigation comments require human judgment to act on. Maintainers remain the final authority on what gets merged, what gets closed, and what gets ignored. As we will see, **this human-in-the-loop dynamic is the single most important factor in determining whether a repository achieves higher development velocity**.

The analysis draws on an emerging view of repositories as **human-agent software factories** — systems where human maintainers and AI agents collaborate in a structured production pipeline. This framing, explored in a recent [SIGPLAN blog post on human-agent software factories](https://blog.sigplan.org/2026/04/21/repositories-are-human-agent-knowledge-factories/), allows us to apply classical production theory (Theory of Constraints, Little's Law, cycle time analysis) to understand where work flows and where it stalls.

Repo Assist is implemented as a [GitHub Agentic Workflow](https://gh.io/gh-aw/), but the findings here should apply to any repository-level AI automation that produces similar outputs (investigation comments, draft PRs) and relies on human review. The results should hold across different languages (here F#, C#, Python, Ruby) and project types (here compilers, libraries, tools), though outcomes will vary widely based on other factors such as maintainer engagement, codebase complexity, and social dynamics.

## Measuring the Impact on Quality: Backlog Reduction

Quality is measured as the proportion of the known backlog (number of open issues at the time of adoption) that has since been addressed. This captures how well the workflow tackles the accumulated debt of unresolved issues. For the purposes of this report, **human-approved AI PRs are assumed to be correct** — when a maintainer reviews and merges a Repo Assist draft PR, that constitutes a human quality judgment, just as it would for any human-authored contribution.

![Open Issue Trajectories](graphs/normalized-open-issues.png)

The normalized trajectory chart above shows each repository's open issue count as a percentage of its count at adoption (100% = adoption day), aligned on the x-axis at the adoption date. Repos that achieved near-complete backlog clearance (FSharp.Data, Deedle, AsyncSeq) show curves dropping to near zero. Repos with blocked pipelines (FSharp.Stats, dowhy) show only modest decline.

Full per-repository backlog clearance data is available in [Appendix B](#appendix-b-backlog-clearance-data).

![Backlog Addressed](graphs/comparative-backlog-addressed.png)

*Note: openclaw/openclaw-windows-node is excluded from the backlog charts above. It had only 3 open issues at adoption — too few for meaningful normalization — and its open issue count has since grown to 38 as rapid new issue creation (4.73/week) outpaced closure in this early-stage, actively growing project. Its adoption-era backlog was fully addressed (100%), but the net increase in open issues reflects growth, not a backlog problem. See the [per-repository detail](#openclawopenclaw-windows-node) for full analysis.*

## Measuring the Impact on Velocity: Dormant to Active

In software engineering, *velocity* measures the rate at which a team completes work — here, the number of issues closed per week and PRs merged per week. Velocity is a key indicator of a project's activity: a dormant project has near-zero velocity, while an active one shows sustained throughput.

All 15 repositories show an increase in both issue closure rate and PR merge rate after Repo Assist adoption. The chart below uses a dumbbell plot to visualize the before/after comparison — each arrow shows the magnitude of acceleration for a single repository, with the multiplier on the right. The "before" period is an equal-length window prior to adoption for fair comparison.

![Velocity Before and After](graphs/velocity-before-after.png)

The velocity increases are large across the board. The median issue closure velocity increased **9×** (from 0.13 to 3.61 issues/week), and the median PR merge velocity increased **9×** (from 0.34 to 5.63 PRs/week). These are not marginal improvements — they represent a qualitative shift from dormant or near-dormant repositories to actively-maintained ones. Even the weakest performer (FSharp.Stats, 2× on PRs) shows measurable improvement, though as we will see in the pipeline analysis, that repo's full potential is bottlenecked on human review.

The mean velocity increase is even larger, but the mean is pulled up by a few repositories (Deedle at 114×, FSharp.Formatting at 129× on PRs) that went from essentially zero prior activity to high throughput. The median is a more representative measure of the typical experience. Full per-repository velocity data is available in [Appendix A](#appendix-a-velocity-data).

## The Repository as Human-Agent Factory

Why do some repositories achieve near-complete backlog clearance while others barely move? To answer this, we model each repository as a **software factory** — a production system where issues are the raw input, human-agent collaboration is the process, and resolved issues are the output. This factory metaphor is not merely illustrative: it enables the application of well-established production theory to software maintenance.

The [Theory of Constraints](https://en.wikipedia.org/wiki/Theory_of_constraints) (Goldratt, 1984) tells us that the throughput of any production system is determined by its single most constrained resource — the bottleneck. [Little's Law](https://en.wikipedia.org/wiki/Little%27s_law) ($L = \lambda \times W$, where $L$ = work-in-progress, $\lambda$ = arrival rate, $W$ = cycle time) lets us quantify where work accumulates and how long it waits. Together, these tools reveal that the primary driver of low backlog clearance is **where the factory's pipeline is blocked**, not the inherent complexity of the issues.

### A Repository Process Flow Model

Each repository operates as a multi-stage "software factory" with **two distinct output paths**:

```mermaid
flowchart LR
    A[Issue Backlog] --> B["Investigation\n(automated)"]
    B -->|COMMENT PATH\ninvestigation, triage, Q&A| C["Human Review/Close"]
    C --> D1["Issue Resolution\n(no PR needed)"]
    B -->|PR PATH\ndraft PR created| E["PR Review Queue\n(WIP buffer)"]
    E --> F["PR Merge\n(human)"]
    F --> D2["Issue Resolution\n(code change)"]
```

Repo-assist automates the Investigation stage. For each issue it processes, it produces one of two outputs:

1. **Comment path**: Repo-assist investigates and determines that no code change is needed — the issue is already resolved, is a question that can be answered, or requires only triage. It leaves an investigation comment. A human may then close the issue.
2. **PR path**: Repo-assist determines a code change is needed and creates a draft PR. This enters the review queue where human maintainer action is required.

Both paths contribute to issue resolution. The comment path is a "fast lane" that resolves issues without requiring PR review overhead. Using Little's Law ($L = \lambda \times W$), we analyze where work accumulates in the PR path specifically — the comment path has no WIP buffer since it produces immediate output.

### Repository Throughput Analysis

| Repository | Comment Path (closed/total) | RA PRs | Merged | Rejected | Open (WIP) | PR Throughput | Status |
|---|---|---|---|---|---|---|---|
| FSharp.Stats | 2/28 | 18 | 2 | 0 | 16 | **11%** | **BLOCKED** |
| dowhy | 16/87 | 61 | 13 | 5 | 43 | **21%** | **BLOCKED** |
| fantomas | 28/75 | 64 | 22 | 41 | 1 | **34%** | **BLOCKED** |
| FsAutoComplete | 26/89 | 54 | 33 | 7 | 14 | **61%** | **BLOCKED** |
| TaskSeq | 11/17 | 83 | 66 | 17 | 0 | 80% | FLOWING |
| FSharp.Formatting | 51/65 | 118 | 94 | 22 | 2 | 80% | FLOWING |
| TypeProviders.SDK | 11/16 | 50 | 45 | 4 | 1 | 90% | FLOWING |
| licensee | 10/16 | 29 | 23 | 5 | 1 | 79% | FLOWING |
| openclaw | 18/38 | 102 | 74 | 27 | 1 | 73% | FLOWING |
| dotnet/fsharp | 54/87 | 0 | — | — | — | — | COMMENT-ONLY |
| AsyncSeq | 7/7 | 69 | 56 | 11 | 2 | 81% | IDLE |
| FSharp.Data | 104/110 | 102 | 86 | 15 | 1 | 84% | IDLE |
| Deedle | 67/70 | 100 | 91 | 8 | 1 | 91% | IDLE |
| SwaggerProvider | 26/28 | 69 | 63 | 6 | 0 | 91% | IDLE |
| GenPRES | 27/29 | 60 | 60 | 0 | 0 | **100%** | IDLE |

Status definitions: **BLOCKED** = pipeline stalled at a specific stage; **FLOWING** = pipeline operating normally with work still to do; **IDLE** = backlog effectively cleared, factory waiting for new input (≤5 open issues and ≤2 open PRs); **COMMENT-ONLY** = using only the investigation/triage path, no PR path.

The "Comment Path" column shows how many issues were resolved via investigation comments alone (closed/total investigated). In well-flowing repos like FSharp.Data (104/110) and Deedle (67/70), humans are closing issues after reading RA's investigation comments at very high rates. In blocked repos like FSharp.Stats (2/28) and dowhy (16/87), even the comment-path is stalled — maintainers are not acting on investigation results either.

The distinction between FLOWING and IDLE is important: repos classified as IDLE (FSharp.Data, Deedle, SwaggerProvider, AsyncSeq, GenPRES) have essentially completed their existing backlog. They are not constrained — they are **input-starved**. Their low residual WIP and issue counts reflect success, not a lack of capacity.

![Pipeline Flow](graphs/bottleneck-pipeline-flow.png)

![Throughput Ratio](graphs/bottleneck-throughput-ratio.png)

### Repository Flow Status Classification

The repositories fall into four distinct operational states:

**1. IDLE — Backlog cleared** (FSharp.Data, Deedle, SwaggerProvider, AsyncSeq, GenPRES): These factories have effectively completed their work. With ≤5 open issues and ≤2 open PRs, they are waiting for new input rather than being constrained. Their high throughput ratios (81–100%) and high comment-path closure rates (93–100%) reflect a well-functioning human-agent collaboration that has run out of backlog to process.

**2. FLOWING — Pipeline operating normally** (TaskSeq, FSharp.Formatting, TypeProviders.SDK, licensee, openclaw): These factories still have work to do and are processing it at a healthy rate. Throughput ratios of 73–90% indicate maintainers are keeping pace with the agent's output on both paths.

**3. BLOCKED — INACTION bottleneck** (FSharp.Stats, dowhy): Repo Assist is producing both investigation comments and PRs, but maintainers are not acting on either. The WIP queue grows without bound and comment-path closures are minimal.

- **FSharp.Stats**: 16 of 18 PRs (89%) sitting unreviewed, avg wait 32.8 days. On the comment path, only 2 of 28 investigated issues were closed — maintainers are ignoring RA's triage output too. Little's Law implies a cycle time of 43.6 days — the pipeline is effectively stalled. The low backlog clearance (7%) is **not** because the workflow is too new; it's because no one is acting on the work it produces.
- **dowhy**: 43 of 61 PRs (70%) in the review queue, avg wait 18.2 days. On the comment path, only 16 of 87 investigated issues were closed. Arrival rate is 1.15 PRs/day but departure rate is only 0.25/day — a 4.7:1 imbalance.

**4. BLOCKED — REJECTION bottleneck** (fantomas): Maintainers are actively reviewing PRs but rejecting 64% of them (41/64 closed without merge). The WIP queue is low (1 PR) because PRs are being processed — just not accepted. On the comment path, 28 of 75 investigated issues were closed, indicating moderate engagement with RA's triage comments even as PRs are rejected. The maintainer identifies three causes (see [Appendix E](#appendix-e-maintainer-notes--fantomas)): the domain requires holistic judgement that tests alone cannot capture, some open issues represent unresolved design discussions rather than actionable tasks, and the workflow's noise eventually exceeded available bandwidth — leading to a deliberate reduction to monthly cadence rather than full disablement.

**5. BLOCKED — MIXED bottleneck** (FsAutoComplete): Both accumulation (14 open PRs, avg wait 44.9 days) and rejection (7 rejected). On the comment path, only 26 of 89 investigated issues were closed. The 61% throughput rate is below the 79–91% seen in well-flowing repos. However, unlike the inaction cases above, this block reflects a **deliberate capacity constraint**: the maintainer reports high satisfaction with merged PR quality (33 RA PRs merged in 2 months = 62% of 2025's total output), but chose to pause the workflow to manage notification pressure during a period of reduced bandwidth (see [Appendix D](#appendix-d-maintainer-notes-fsautocomplete)). Some rejected PRs were intentionally experimental. This case illustrates that BLOCKED status can reflect legitimate human factors — burnout avoidance, life circumstances — rather than workflow failure.

### Cycle Time Analysis

[Cycle time](https://en.wikipedia.org/wiki/Cycle_time) is the elapsed time from when a work item enters a stage to when it exits. In manufacturing, cycle time directly determines throughput: a machine that takes 10 minutes per part can produce 6 parts per hour. In our software factory, we measure two cycle times: the **merge cycle time** (how long it takes a merged PR to go from creation to merge) and the **open wait time** (how long currently-open PRs have been waiting).

The ratio between these two measures is diagnostic. If open PRs have been waiting much longer than merged PRs took, the remaining open PRs are qualitatively different — they're stuck, not just slow. Full cycle time data is available in [Appendix C](#appendix-c-cycle-time-data).

![Cycle Times](graphs/bottleneck-cycle-times.png)

![WIP Accumulation](graphs/bottleneck-wip.png)

## Human Engagement and Maintainer Override

A key question for any AI-assisted workflow is: how much does a human need to intervene to correct or extend the agent's output? We measure this along several dimensions: directed invocations (human-initiated runs), code-level modifications (additional commits pushed to RA PR branches), use of secondary AI agents (Copilot assign-to-copilot), code review comments, draft-to-ready approvals, and issue reopen rates.

### Directed Invocations

Across all repositories, **30% of active workflow runs are human interventions** (687 of 2,318) — direct `/repo-assist` invocations where a maintainer explicitly asked the agent to work on a specific issue. A further **22% are additional dispatches** (506 runs) where maintainers manually triggered the workflow from the GitHub Actions UI, dialing up the rate of automation beyond the scheduled cadence. Together, **52% of active runs involved some form of human direction**, with the remaining 49% from scheduled automation.

The human intervention rate varies dramatically by repository. Repos with high human intervention rates (FSharp.Formatting: 52%, Deedle: 47%, fantomas: 41%) also tend to have the highest pipeline throughput — suggesting that active human direction of the agent correlates with better outcomes. GenPRES is a notable outlier with 0% human intervention — reflecting its pure work-queue pattern where the maintainer creates issues and lets the scheduled automation handle them.

### Code-Level Modification Rate

Maintainers pushed additional commits (possibly co-authored using local agents) to **328 of 877 RA PR branches (37.4%)**, contributing 650 human commits. Force pushes (which overwrite the agent's code entirely) occurred exactly **once** (0.1%), but regular pushes — adding commits on top of the agent's work — are common. The modification rate varies widely by repository: FSharp.Formatting (54%), licensee (52%), GenPRES (48%), TaskSeq (46%), and Deedle (44%) show the highest rates, while FsAutoComplete (6%), FSharp.Stats (6%), and TypeProviders.SDK (8%) are lowest.

This reveals a more nuanced review dynamic than simple accept-or-reject. In roughly **two-thirds** of RA PRs, maintainers merge the agent's code without modification. But in **over a third**, maintainers are actively building on the agent's work — pushing fixes, extending implementations, or adjusting details before merging. The agent's PRs serve as both finished proposals *and* useful starting points, depending on the issue complexity and maintainer engagement style.

### Copilot as Secondary Agent

Maintainers also used GitHub Copilot (via assign-to-copilot) to extend RA PR branches, with Copilot commits appearing on **60 of 877 RA PRs (6.8%)** — 115 Copilot commits total. Across all issues (not just RA PRs), **398 unique issues** received `copilot_work_started` events, with 124 of those on RA PRs specifically. This represents a **multi-agent workflow**: Repo Assist creates the initial PR, and maintainers then delegate additional work to Copilot rather than coding manually. SwaggerProvider is the most intensive user (57 RA PRs with Copilot assign, 70 Copilot commits), followed by dowhy (39 RA PRs, 17 commits) and licensee (17 RA PRs, 5 commits).

Copilot also participated as a **code reviewer**: 305 Copilot review comments were left on RA PRs across 7 repositories, compared to 92 human review comments on 54 PRs (6.2%). This suggests some maintainers are using Copilot not just to write additional code but also to review the agent's output — a form of AI-reviewing-AI with human oversight.

### Code Review Comments

Human code review comments (inline PR review comments, not issue comments) were left on **54 of 877 RA PRs (6.2%)** — 92 comments total. The most active reviewers were sergey-tihon (38 comments on SwaggerProvider), nojaf (12 on FSharp.Formatting, 1 on fantomas), dsyme (16 across several repos), and emrekiciman (9 on dowhy). The low rate of human review comments suggests that most RA PRs are evaluated at the whole-PR level (merge or reject) rather than through line-by-line code review — consistent with the draft-to-ready approval pattern.

### Draft-to-Ready Approval

Repo Assist creates PRs as drafts. Before a PR can be merged, a maintainer must explicitly mark it as "ready for review" — a deliberate approval step. Across all repos, **684 of 877 RA PRs (78%) were marked ready by a maintainer**. Of those reviewed (marked ready or explicitly closed), **654 of 795 were merged (82%)**. The remaining 82 open PRs are awaiting review.

### Issue Reopen Rate

Of 671 issues closed after Repo Assist investigation (via the comment path), **22 were subsequently reopened (3.3%)**. This low reopen rate suggests that when RA's investigation leads to issue closure — whether by identifying the issue as already fixed, answering a question, or triaging — the closure is almost always correct. The highest reopen rates were in licensee (25% of 12 closed, 3 reopened) and dotnet/fsharp (11% of 62 closed, 7 reopened), where compiler issue complexity may contribute to premature closures.

### Repo-Specific Norms

Repo Assist does not currently learn or encode repository-specific norms, coding conventions, or maintainer preferences. Its behavior is driven by the repository's code, documentation, and issue context at invocation time, not by accumulated memory of past interactions. This means each invocation starts fresh — the agent does not "learn" from rejected PRs or maintainer feedback. Adding persistent memory of repository norms could potentially reduce the rejection rate (currently 18% of reviewed PRs), particularly in repos like fantomas where domain-specific formatting rules cause high rejection (64%). However, there is also a risk that encoding maintainer preferences creates hidden policy that is difficult to audit or override.

A related limitation is **issue readiness**: the agent treats every open issue as potentially actionable, but some issues — particularly in fantomas — represent unresolved design discussions, behavioural trade-offs, or differing opinions between maintainer and reporter. As the fantomas maintainer notes (see [Appendix E](#appendix-e-maintainer-notes--fantomas)), "an open issue is not necessarily a green light for implementation." A mechanism for maintainers to signal issue readiness (e.g. labels, issue types, or explicit opt-in) could reduce wasted work on issues that are unlikely to produce mergeable PRs.

## Social Factors in the Software Factory

It is highly likely that, like all automation technologies, successful use of agentic repository automation will be driven by human-social factors and incentives.

For example, the creator of Repo Assist (@dsyme) was a maintainer and community leader in the software community which adopted Repo Assist here, and was the maintainer of some (but not all) of the repositories analyzed here. This clearly will influence adoption and usage rates.

Repositories with more active maintainers, or more knowledgable maintainers (e.g. original code authors), or where maintainers feel empowered to install and act, or where maintainers see each other succceeding, or where maintainers are actively seeking forward velocity for their project - these are surely more likely to see better outcomes. Those with less active maintainers, or with high levels of risk aversion, or where quality constraints make action impossible - these may struggle to unlock the forward velocity that automated repository assistance can evidently provide.

Two maintainers explicitly cited **automation fatigue** as a factor. The FsAutoComplete maintainer (see [Appendix D](#appendix-d-maintainer-notes-fsautocomplete)) cited **notification anxiety** and chose to disable the workflow entirely during a period of reduced bandwidth. The fantomas maintainer (see [Appendix E](#appendix-e-maintainer-notes--fantomas)) described the workflow's value wearing off as it became "too noisy relative to the amount of attention I want to give that project right now" — responding by reducing the cadence to monthly rather than disabling it. Both cases illustrate the same dynamic from different angles: continuous AI automation can amplify the pressure of open source maintenance, even when the output is high quality. The ability to **control the rate of automation** is crucial to maintainer happiness: there is nothing wrong with wanting your factory to operate at a rate suitable to your lifestyle! It lets maintainers control the production rate to match their available bandwidth, rather than being pressured by a stream of AI-generated work.

The adoption of AI automation can also have an impact on the repository as a place of human-to-human collaboration. Most the repositories in this analysis were "dormant" - that is, they had very low human-to-human interaction at point of adoption. This means **there was no significant human-to-human collaboration to impact** and so the impact on human-to-human processes is neither explored nor measurable in this report. However the general impression is that automated AI can be highly corrosive on social platforms and this should be taken into account before adopting any AI automation in a non-dormant repository. Future research should explore the social impact of AI automation in open source communities.

## Per-Repository Detail

### fsprojects/FSharp.Data
*Adopted 2026-02-21 · Factory IDLE (backlog cleared)*

Went from 153 open issues to just 1 — a complete backlog clearance. Issue closure rate went from 0.00/week to 14.26/week. This suggests a large proportion of FSharp.Data's backlog was well-specified, fixable bugs and features that were simply waiting for someone to address them.

![FSharp.Data Open Issues](graphs/fsprojects-FSharp.Data/open-issues-over-time.png)
![FSharp.Data Merge Rate](graphs/fsprojects-FSharp.Data/merge-rate.png)

### fslaborg/Deedle
*Adopted 2026-03-08 · Factory IDLE (backlog cleared)*

108 open issues reduced to 3. Adoption was slightly later but the rate of closure was the highest of all repos at 12/week. Nearly all legacy backlog addressed.

![Deedle Open Issues](graphs/fslaborg-Deedle/open-issues-over-time.png)
![Deedle Merge Rate](graphs/fslaborg-Deedle/merge-rate.png)

### fsprojects/SwaggerProvider
*Adopted 2026-03-08 · Factory IDLE (backlog cleared)*

32 → 1 open issues (96.9% backlog clearance). Particularly notable for high PR merge velocity — 9.86 PRs/week after adoption, the highest of any non-GenPRES repo. This repo had low prior activity (1.06 PRs merged/week before adoption).

![SwaggerProvider Open Issues](graphs/fsprojects-SwaggerProvider/open-issues-over-time.png)
![SwaggerProvider Merge Rate](graphs/fsprojects-SwaggerProvider/merge-rate.png)

### fsprojects/FSharp.Formatting
*Adopted 2026-02-22 · Factory FLOWING*

85 → 11 open issues. Both issue closure and PR merge rates exceeded 8/week after adoption. Zero pre-adoption activity in the comparison period makes the contrast especially stark.

![FSharp.Formatting Open Issues](graphs/fsprojects-FSharp.Formatting/open-issues-over-time.png)
![FSharp.Formatting Merge Rate](graphs/fsprojects-FSharp.Formatting/merge-rate.png)

### fsprojects/fantomas
*Adopted 2026-02-23 · Pipeline BLOCKED (rejection)*

120 → 74 open issues. Pipeline analysis reveals a **rejection bottleneck** on the PR path: maintainers are actively reviewing Repo Assist PRs but rejecting 64% of them (41 of 64 closed without merge). The WIP queue is low (1 PR), meaning PRs are being processed promptly (0.6d avg merge cycle) — they just don't meet the codebase's exacting standards. On the comment path, 28 of 75 investigated issues were closed, showing moderate engagement with the agent's triage function. The 34% PR throughput ratio reflects the domain complexity of formatting behaviour, but the comment path provides additional value — the dual-path model shows the agent contributing to issue resolution even when its code changes are rejected.

The maintainer's perspective (see [Appendix E](#appendix-e-maintainer-notes--fantomas)) adds important nuance. First, the workflow **did rekindle engagement** — the maintainer reports a "renewed spark" with the project. But the high rejection rate reflects three structural challenges: (1) **formatting requires holistic judgement** — a fix can pass all tests while moving the implementation in an undesirable direction, and it is often easier to close the PR and redo the work manually than to steer corrections; (2) **issue ambiguity** — some open issues represent unresolved design discussions or differing opinions, not actionable engineering tasks, and the agent cannot distinguish between them; (3) **bandwidth mismatch** — as the project is not the maintainer's primary focus, the automation's output eventually exceeded available attention. The maintainer responded by reducing the workflow to a monthly cadence rather than disabling it entirely — a **rate-limiting** strategy rather than rejection of the tool.

![fantomas Open Issues](graphs/fsprojects-fantomas/open-issues-over-time.png)
![fantomas Merge Rate](graphs/fsprojects-fantomas/merge-rate.png)

### py-why/dowhy
*Adopted 2026-03-18 · Pipeline BLOCKED (inaction)*

142 → 108 open issues. Despite issue closure jumping from 0.62 to 4.25/week, the pipeline is severely constrained on both paths: on the PR path, 43 of 61 PRs (70%) remain in the review queue with an average wait of 18.2 days; on the comment path, only 16 of 87 investigated issues were closed. The arrival rate of 1.15 PRs/day exceeds the departure rate of 0.25 PRs/day by 4.7:1. As a Python causal inference library with 8,100+ stars, it validates that Repo Assist works across ecosystems — but its full potential is bottlenecked on maintainer engagement with both the agent's PRs and investigation comments.

![dowhy Open Issues](graphs/py-why-dowhy/open-issues-over-time.png)
![dowhy Merge Rate](graphs/py-why-dowhy/merge-rate.png)

### ionide/FsAutoComplete
*Adopted 2026-02-22 · Pipeline BLOCKED (mixed) · Workflow paused by maintainer*

86 → 67 open issues. In raw throughput terms, the pipeline shows a **mixed bottleneck**: 14 PRs in the review queue (avg wait 44.9 days, the longest of any repo), 7 rejected, and only 26 of 89 investigated issues closed on the comment path. The 61% PR throughput ratio is below the 79–91% seen in well-flowing repos.

However, the maintainer's perspective (see [Appendix D](#appendix-d-maintainer-notes-fsautocomplete)) reveals important nuance. The merged PRs are **high quality** — in just two months, Repo Assist produced 33 merged PRs, equivalent to 62% of the repository's entire 2025 output of 53 PRs, and the maintainer reports that many were more impactful than typical contributions, following repository best practices including comprehensive integration tests. The codebase's complexity (FsAutoComplete is the core language server for F#, with broad ecosystem impact) means PRs require careful review — a legitimate quality constraint, not disengagement.

Some of the rejected PRs were **intentionally experimental** — prompted to investigate whether old bugs still existed or to explore specific approaches, rather than expected to merge directly. The maintainer ultimately **chose to disable the workflow** — not due to dissatisfaction with its output, but to manage notification pressure and protect against burnout during a period of reduced personal bandwidth. This represents a deliberate production-rate decision: the factory's human operator temporarily shut down the line rather than let unreviewed work accumulate. The maintainer intends to re-enable the workflow when capacity returns.

![FsAutoComplete Open Issues](graphs/ionide-FsAutoComplete/open-issues-over-time.png)
![FsAutoComplete Merge Rate](graphs/ionide-FsAutoComplete/merge-rate.png)

### fsprojects/FSharp.Control.TaskSeq
*Adopted 2026-03-07 · Factory FLOWING*

18 → 4 open issues, with one of the highest PR merge rates at 8.04/week. The workflow found many opportunities for contribution in this actively-developed library.

![TaskSeq Open Issues](graphs/fsprojects-FSharp.Control.TaskSeq/open-issues-over-time.png)

### fsprojects/FSharp.Control.AsyncSeq
*Adopted 2026-02-20 · Factory IDLE (backlog cleared)*

12 → 0 open issues. 100% of the pre-adoption backlog addressed. Small repo where the workflow was able to comprehensively address all outstanding issues.

![AsyncSeq Open Issues](graphs/fsprojects-FSharp.Control.AsyncSeq/open-issues-over-time.png)

### fsprojects/FSharp.TypeProviders.SDK
*Adopted 2026-02-24 · Factory FLOWING*

31 → 4 open issues (87.1% backlog clearance). Good result for a project that had seen no issue closures in the comparison period before adoption.

![TypeProviders.SDK Open Issues](graphs/fsprojects-FSharp.TypeProviders.SDK/open-issues-over-time.png)

### fslaborg/FSharp.Stats
*Adopted 2026-03-23 · Pipeline BLOCKED (inaction)*

60 → 57 open issues. While this is the most recently adopted repo, the low clearance (5%) is **not primarily due to recency** — it is due to an inaction bottleneck on **both** output paths. On the PR path, Repo Assist has created 18 PRs, but only 2 have been merged; the remaining 16 sit in the review queue with an average wait of 32.8 days. On the comment path, Repo Assist investigated 28 issues, but only 2 were closed — maintainers are not acting on the agent's triage output either. The pipeline throughput ratio is just 11% — the lowest of all repositories.

![FSharp.Stats Open Issues](graphs/fslaborg-FSharp.Stats/open-issues-over-time.png)

### licensee/licensee
*Adopted 2026-03-02 · Factory FLOWING*

16 → 5 open issues (69% backlog clearance). A Ruby gem for open source license detection with 881 stars — validating that Repo Assist works across language ecosystems. On the PR path, 23 of 29 PRs merged (79% throughput) with a fast 1.0d average merge cycle. On the comment path, 10 of 16 investigated issues were closed. Maintainers are actively reviewing and merging — the pipeline is flowing well with low WIP (1 open PR).

![licensee Open Issues](graphs/licensee-licensee/open-issues-over-time.png)
![licensee Merge Rate](graphs/licensee-licensee/merge-rate.png)

### openclaw/openclaw-windows-node
*Adopted 2026-03-17 · Factory FLOWING*

A C# application with 518 stars — the first C# repo in the analysis, further validating cross-ecosystem applicability. openclaw had only 3 open issues at adoption, but rapidly grew its backlog as the project scaled: 123 new issues were filed in just 8 weeks, with 85 closed (4.73 new/week, 3.27 closed/week). Repo Assist created 102 PRs, of which 74 were merged (73% throughput) and 27 rejected — a healthy rejection rate suggesting active maintainer engagement. The merge cycle time averages 2.8 days. On the comment path, 18 of 38 investigated issues were closed (47%).

The velocity increase is striking: issue closure went from 1.45/week to 8.81/week (6×), and PR merges from 1.21/week to 22.45/week (19×). With 121 active workflow runs — nearly all scheduled (118) with only 3 manual dispatches and 0 human interventions — this repo follows a primarily automated pattern similar to GenPRES, where the workflow runs on schedule with minimal human direction.

![openclaw Open Issues](graphs/openclaw-openclaw-windows-node/open-issues-over-time.png)
![openclaw Merge Rate](graphs/openclaw-openclaw-windows-node/merge-rate.png)

### dotnet/fsharp
*Adopted 2026-03-16 · Comment-path only*

dotnet/fsharp is a qualitatively different case from the other repositories in this analysis. It is the F# compiler and core tooling repository — a large, actively maintained project with over 6,700 issues, 12,700 PRs, and a pre-existing issue closure rate of 8.69/week. Unlike the other repositories, which were largely dormant at adoption, dotnet/fsharp was already a functioning software factory with regular human contributions.

Repo Assist was deployed here in a **limited, comment-path-only configuration**, focused exclusively on investigating and triaging old issues. No `[repo-assist]` PRs were created. This makes it a pure test of the agent's investigation and triage function at scale.

**Results:** 1,225 → 1,157 open issues (−68 net, 7% backlog clearance). Repo Assist investigated 87 old issues via comment-path, and 54 of those were subsequently closed by maintainers (62% comment-path closure rate). Issue closure velocity increased from 8.69/week to 13.64/week — a **1.6× increase**. While modest compared to the dramatic multipliers seen in dormant repositories, this represents roughly 68 additional issue closures over the period, on a codebase where each issue closure may involve nuanced compiler or tooling behavior.

The 62% comment-path closure rate is notable: it sits between the well-flowing repos (93–100% closure on investigated issues) and the blocked repos (7–20%). This likely reflects the higher complexity of compiler issues — some investigations correctly identify issues as resolved or answerable, while others surface problems that require deeper human judgment.

PR merge velocity also increased slightly (17.62 → 24.74 PRs/week, 1.4×), though this is not attributable to Repo Assist since no RA PRs were created — it may reflect independent maintainer activity or a knock-on effect of backlog reduction freeing up maintainer attention.

With 391 active workflow runs (283 scheduled, 12 additional dispatches, and 96 human interventions), the workflow saw substantial use. The high ratio of scheduled runs reflects the large backlog providing continuous work for the agent to investigate.

This case demonstrates that Repo Assist's comment-path (investigation/triage) function can provide value even in large, actively maintained repositories, and even without the PR path. The agent serves as a **backlog triage assistant**, systematically working through old issues that human maintainers may never get to, identifying which are already resolved, which can be answered, and which still require attention.

![dotnet/fsharp Open Issues](graphs/dotnet-fsharp/open-issues-over-time.png)

### informedica/GenPRES
*Adopted 2026-02-28 · Factory IDLE (backlog cleared) · Work queue pattern*

GenPRES is a qualitatively different case from the other repositories. It is an F# medical software project where the maintainer used Repo Assist as a **continuous asynchronous work queue processor**: rather than having an accumulated backlog of externally-reported issues, the maintainer created issues representing desired work items and let Repo Assist process them into PRs. This represents a distinct usage pattern — the agent as a **production assistant** rather than a backlog reducer.

**Results:** 19 → 2 open issues (100% backlog clearance). All 60 Repo Assist PRs were merged — a 100% throughput ratio, the highest of any repository. The merge cycle time averaged just 0.9 days. On the comment path, 27 of 29 investigated issues were closed (93%). PR merge velocity went from 2.71/week before to 17.17/week after adoption — a 6× increase — the highest absolute PR velocity of any repository.

The incoming rate data confirms the work queue pattern: all incoming issues after adoption are from the maintainer (2.61/week intra-factory, 0/week external), and the incoming rate increased dramatically after adoption as the maintainer fed more work items to the agent. With 78 active workflow runs (77 scheduled, 1 additional, 0 human interventions), the workflow was almost entirely automated — the maintainer created issues and let the scheduled runs pick them up.

![GenPRES Open Issues](graphs/informedica-GenPRES/open-issues-over-time.png)
![GenPRES Merge Rate](graphs/informedica-GenPRES/merge-rate.png)

## Workflow Invocation Analysis

Repo Assist workflow runs fall into three categories:

- **Automated (scheduled)**: Periodic runs on a cron schedule — the factory's own clock.
- **Automated (additional)**: Manual dispatch from the GitHub Actions UI — where a maintainer explicitly dialed up the rate of automation beyond the scheduled cadence.
- **Human intervention (/repo-assist)**: Event-triggered runs that actually executed — issue comments, PR review comments, issue events, and PR events that passed the workflow's pre-activation check. These represent actual `/repo-assist` invocations where a human triggered the agent to investigate a specific issue.

| Repository | Active Runs | Runs/wk | Automated (scheduled) | Automated (additional) | Human intervention |
|---|---|---|---|---|---|
| dotnet/fsharp | 391 | 47.2 | 283 | 12 | 96 |
| FSharp.Formatting | 338 | 30.3 | 73 | 90 | 175 |
| TypeProviders.SDK | 209 | 20.3 | 39 | 151 | 19 |
| FsAutoComplete | 142 | 19.5 | 52 | 50 | 40 |
| FSharp.Data | 216 | 19.4 | 71 | 95 | 50 |
| Deedle | 151 | 17.1 | 36 | 44 | 71 |
| fantomas | 143 | 13.2 | 83 | 2 | 58 |
| SwaggerProvider | 112 | 12.7 | 63 | 9 | 40 |
| TaskSeq | 103 | 11.6 | 69 | 16 | 18 |
| dowhy | 91 | 11.2 | 80 | 5 | 6 |
| licensee | 106 | 10.8 | 70 | 1 | 35 |
| AsyncSeq | 95 | 8.8 | 43 | 24 | 28 |
| GenPRES | 78 | 7.2 | 77 | 1 | 0 |
| FSharp.Stats | 46 | 6.6 | 31 | 4 | 11 |
| openclaw | 121 | 14.6 | 118 | 3 | 0 |

![Invocation Rate by Type](graphs/invocation-rate-by-type.png)

### Human Intervention Rates

The breakdown of human vs. automated runs is discussed in detail in [Human Engagement and Maintainer Override](#human-engagement-and-maintainer-override) above. The key finding: 30% of active runs are human-directed `/repo-assist` invocations and 22% are additional manual dispatches, with the remaining 49% from scheduled automation.

![Activity Over Time](graphs/invocation-over-time.png)

## Methodology

- **Velocity** is measured as issues closed per week and PRs merged per week. The "before" period is an equal-length window before the adoption date; "after" is from adoption to now.
- **Quality (backlog clearance)** is the proportion of issues that were open at the time of Repo Assist adoption that have since been closed. This measures how well accumulated technical and feature debt is being addressed.
- **Repo-assist detection**: A repository is classified as using repo-assist based on PRs with `[repo-assist]` in the title or issues/PRs with the `repo-assist` label. The adoption date is the earliest such item.
- **Inclusion criteria**: Repos were included only if (a) repo-assist workflow runs have succeeded in the last week, and (b) adoption was more than 3 weeks ago.
- **Bot issue exclusion**: Issues created by `github-actions[bot]` are excluded from all counting and analysis (backlog metrics, velocity, incoming rates). These include monthly activity reports, failure notifications, and other automated outputs that would inflate issue counts. Bot issues are *not* excluded from adoption date detection, since they signal when Repo Assist was deployed.
- **Limitations**: This analysis measures correlation, not strict causation. The adoption of Repo Assist may have coincided with increased human maintainer activity. However, the consistency of the pattern across all 15 repositories — and the near-zero baseline activity in many repos before adoption — strongly suggests Repo Assist is the primary driver. The non-F# repos (dowhy, licensee, openclaw) provide cross-ecosystem validation.
- **Issue quality caveat**: Some closed issues may have been closed as "won't fix" or triaged rather than fixed. The current analysis counts all closures equally. A more nuanced analysis could distinguish closure reasons.
- **Pipeline bottleneck analysis**: Models the repository as a multi-stage human-agent software factory. Uses Little's Law ($L = \lambda W$) to compute implied cycle times and identify WIP accumulation. Throughput ratio (PRs merged / PRs created) is the primary bottleneck metric. Bottleneck types are classified as: INACTION (high WIP, low review activity), REJECTION (high rejection rate, low WIP), or MIXED (both). Status levels: BLOCKED (score ≥5), FLOWING (0), IDLE (≤5 open issues and ≤2 open PRs with no bottleneck).
- **Workflow invocation analysis**: Uses the GitHub Actions API to retrieve all runs of the "Repo Assist" workflow. The workflow's trigger configuration includes `issue_comment`, `pull_request_review_comment`, and `pull_request` events primarily so it can detect `/repo-assist` slash commands in comments. Most of these triggered runs are **immediately skipped** by the workflow's pre-activation check when no `/repo-assist` command is found. Additionally, some runs conclude with `cancelled` or `action_required` status and never actually execute. Across all repos, **60% of all workflow runs (3,429 of 5,747) never executed** and are excluded — only *active* runs that actually proceeded to execute the agent are counted. Active runs are classified into three categories: *Automated (scheduled)* (cron-triggered), *Automated (additional)* (manual dispatch from the Actions UI), and *Human intervention (/repo-assist)* (event-triggered runs that passed pre-activation — issue comments, PR comments, issue events, PR events). The human intervention ratio measures direct maintainer engagement with the workflow.
- **Dual-path model**: Repo Assist produces two types of output per issue: investigation comments (comment path) and draft PRs (PR path). Bot comments are detected via `github-actions[bot]` comments containing "automated response from Repo Assist". PR-path issues are identified by comments mentioning "Pull request created". Issues resolved via the comment path are those with investigation comments where the issue was subsequently closed without a PR being created.
- **Maintainer override analysis**: Code-level modifications are measured by fetching commit lists for all 877 RA PRs via the GitHub API (`/repos/{owner}/{repo}/pulls/{number}/commits`). Commits authored by `github-actions[bot]`, `web-flow`, or `actions-user` are classified as bot/system commits. Commits by `Copilot` are classified as Copilot agent commits (from assign-to-copilot). All other commits are classified as human pushes. Force pushes are detected via `head_ref_force_pushed` events on RA PR branches by non-bot actors. Copilot assign usage is measured via `copilot_work_started` events. Code review comments are downloaded via the pull review comments API (`/repos/{owner}/{repo}/pulls/comments`); comments by `github-actions[bot]`, `github-advanced-security[bot]`, and `greptile-apps[bot]` are classified as bot comments, `Copilot` as Copilot review comments, and all others as human review comments. Draft-to-ready transitions are measured via `ready_for_review` events by non-bot actors. Issue reopen rate is measured by `reopened` events on RA-investigated issues (post-adoption only, excluding RA PRs from the denominator).

## Data & Scripts

All data and scripts used in this analysis are available in this repository:

- `scripts/download-github-data.sh` — Generic script to download issues, PRs, and events for any GitHub repo
- `scripts/download-all.sh` — Batch download for all analyzed repos
- `scripts/graph-repo-stats.py` — Per-repo graph generation (open issues over time, merge rate, PR time-to-merge, issue activity)
- `scripts/generate-all-graphs.sh` — Batch graph generation
- `scripts/analyze-repo-assist.py` — Cross-repo analysis, comparative graphs, and report generation
- `scripts/bottleneck-analysis.py` — Pipeline flow analysis using Theory of Constraints and Little's Law; bottleneck identification and classification
- `scripts/normalized-graph.py` — Normalized open-issue trajectory graph aligned to adoption date
- `scripts/invocation-analysis.py` — Workflow invocation rate analysis by trigger type (filters out skipped runs)
- `scripts/velocity-graph.py` — Velocity dumbbell chart (before/after comparison)
- `scripts/download-workflow-runs.sh` — Download GitHub Actions workflow run data
- `data/` — Raw JSON data for all repositories (including `workflow-runs.json` per repo)
- `graphs/` — All generated PNG graphs

---

## Appendices

### Appendix A: Velocity Data

| Repository | Adopted | Period | Issues Closed/wk Before | After | Δ | PRs Merged/wk Before | After | Δ |
|---|---|---|---|---|---|---|---|---|
| fsprojects/FSharp.Data | 2026-02-21 | 82d | 0.00 | 14.26 | **+14.26** | 0.26 | 8.71 | **+8.45** |
| fslaborg/Deedle | 2026-03-08 | 66d | 0.11 | 12.09 | **+11.98** | 0.11 | 10.71 | **+10.61** |
| fsprojects/FSharp.Formatting | 2026-02-22 | 81d | 0.00 | 8.12 | **+8.12** | 0.09 | 11.15 | **+11.06** |
| fsprojects/fantomas | 2026-02-23 | 80d | 0.35 | 5.08 | **+4.73** | 0.61 | 5.60 | **+4.99** |
| informedica/GenPRES | 2026-02-28 | 75d | 0.00 | 4.20 | **+4.20** | 2.71 | 17.17 | **+14.47** |
| py-why/dowhy | 2026-03-18 | 56d | 0.62 | 4.25 | **+3.63** | 1.75 | 4.88 | +3.12 |
| fsprojects/SwaggerProvider | 2026-03-08 | 66d | 0.42 | 3.61 | **+3.19** | 1.06 | 9.86 | **+8.80** |
| fsprojects/FSharp.TypeProviders.SDK | 2026-02-24 | 78d | 0.00 | 3.14 | **+3.14** | 0.09 | 4.22 | **+4.13** |
| ionide/FsAutoComplete | 2026-02-22 | 80d | 0.17 | 2.71 | +2.54 | 0.79 | 3.24 | +2.45 |
| fsprojects/FSharp.Control.TaskSeq | 2026-03-07 | 67d | 0.10 | 2.19 | **+2.09** | 0.10 | 8.04 | **+7.94** |
| fsprojects/FSharp.Control.AsyncSeq | 2026-02-20 | 82d | 0.26 | 1.71 | +1.45 | 0.34 | 5.63 | **+5.29** |
| licensee/licensee | 2026-03-02 | 73d | 0.67 | 1.34 | +0.67 | 1.73 | 4.32 | +2.59 |
| fslaborg/FSharp.Stats | 2026-03-23 | 52d | 0.13 | 0.40 | +0.27 | 0.13 | 0.27 | +0.13 |
| openclaw/openclaw-windows-node | 2026-03-17 | 58d | 1.45 | 8.81 | **+7.36** | 1.21 | 22.45 | **+21.24** |
| dotnet/fsharp † | 2026-03-16 | 58d | 8.69 | 13.64 | +4.95 | 17.62 | 24.74 | +7.12 |
| **Average (excl. dotnet/fsharp)** | | | **0.22** | **4.85** | **+4.63** | **0.75** | **7.22** | **+6.47** |
| **Median (excl. dotnet/fsharp)** | | | **0.13** | **3.61** | | **0.34** | **5.63** | |

† dotnet/fsharp is excluded from the Average and Median rows. Unlike the other repositories, it was already actively maintained before adoption (8.69 issues/wk, 17.62 PRs/wk). It used Repo Assist in a comment-path-only configuration with no RA PRs; the PR velocity change is not attributable to Repo Assist.

### Appendix B: Backlog Clearance Data

| Repository | Open at Adoption | Addressed Since | Backlog Clearance | Open Now | Net Change |
|---|---|---|---|---|---|
| fsprojects/FSharp.Data | 153 | 153 | **100.0%** | 1 | −152 |
| fsprojects/FSharp.Control.AsyncSeq | 12 | 12 | **100.0%** | 0 | −12 |
| informedica/GenPRES | 19 | 19 | **100.0%** | 2 | −17 |
| fslaborg/Deedle | 108 | 106 | **98.1%** | 3 | −105 |
| fsprojects/SwaggerProvider | 32 | 31 | **96.9%** | 1 | −31 |
| fsprojects/FSharp.Formatting | 85 | 76 | **89.4%** | 11 | −74 |
| fsprojects/FSharp.TypeProviders.SDK | 31 | 27 | **87.1%** | 4 | −27 |
| fsprojects/FSharp.Control.TaskSeq | 18 | 14 | **77.8%** | 4 | −14 |
| licensee/licensee | 16 | 11 | **68.8%** | 5 | −11 |
| fsprojects/fantomas | 120 | 48 | 40.0% | 74 | −46 |
| ionide/FsAutoComplete | 87 | 27 | 31.0% | 67 | −20 |
| py-why/dowhy | 142 | 34 | 23.9% | 108 | −34 |
| dotnet/fsharp † | 1225 | 90 | 7.3% | 1157 | −68 |
| fslaborg/FSharp.Stats | 60 | 3 | 5.0% | 57 | −3 |
| openclaw/openclaw-windows-node | 3 | 3 | **100.0%** | 38 | +35 |
| **Total (excl. dotnet/fsharp)** | **886** | **564** | **63.7%** | **375** | **−511** |
| **Total (all 15 repos)** | **2111** | **654** | **31.0%** | **1532** | **−579** |

† dotnet/fsharp's large issue count (1,225 at adoption) significantly shifts the aggregate backlog clearance percentage. The separate totals show the impact with and without this outlier. openclaw shows a net increase in open issues despite 100% adoption-backlog clearance, because rapid issue creation (123 new issues in 8 weeks) outpaced closure.

### Appendix C: Cycle Time Data

| Repository | Avg Merge Cycle | Avg Open Wait | Wait/Merge Ratio | Status |
|---|---|---|---|---|
| FSharp.Stats | 4.3d | 32.8d | **7.6×** | BLOCKED (inaction) |
| dowhy | 4.7d | 18.3d | **3.9×** | BLOCKED (inaction) |
| FsAutoComplete | 2.3d | 44.9d | **19.5×** | BLOCKED (mixed) |
| fantomas | 0.6d | 10.5d | **17.5×** | BLOCKED (rejection) |
| FSharp.Formatting | 3.9d | 21.1d | 5.4× | FLOWING |
| FSharp.Data | 2.0d | 40.4d | 20.2× | IDLE |
| Deedle | 1.0d | 2.0d | 2.0× | IDLE |
| SwaggerProvider | 0.8d | 0.0d | — | IDLE |
| TypeProviders.SDK | 1.8d | 3.0d | 1.7× | FLOWING |
| AsyncSeq | 1.7d | 13.6d | 8.0× | IDLE |
| TaskSeq | 2.0d | 0.0d | — | FLOWING |
| licensee | 1.0d | 0.7d | 0.7× | FLOWING |
| openclaw | 2.8d | 0.3d | 0.1× | FLOWING |
| GenPRES | 0.9d | 0.0d | — | IDLE |

### Appendix D: Maintainer Notes — FsAutoComplete

The following are lightly edited notes from the FsAutoComplete maintainer (Krzysztof Cieślak), providing qualitative context for the quantitative analysis above.

> FSAC is an interesting case. Couple of notes related to it:
>
> * The repository is not really actively maintained at all [there's new release every few months, and development is not really active]
> * Enabling Repo Assist definitely created a surge in activity - in ~2 months it was active we merged almost as much (probably could get exact numbers here easily) PRs as in whole 2025 year (and I'd say that many of Repo Assist PRs were more impactful)
> * Due to the type of software it is, there's certain level of code complexity + potential huge impact on the ecosystem if something goes wrong. Which means it requires rather careful reviews
> * In general I'm very happy with most PRs I merged - there are high quality, useful, meaningful, follows best practices of the repository [like adding a lot of integration tests for new features]
> * Some of the open PRs, at glance, looks good, but as I've mentioned they need more review...
> * Some of the non-merged PRs were very specifically prompted to be an experiments / "check if this old bug is still happening" type of things. They would require more follow-up, and maybe some of them should be just closed.
> * But I just don't have a time (nor I'm in the right mindset at the moment) to review stuff - this has nothing to do with Repo Assist on its own, but with me. Maintaining OSS has not been the highest priority for a while, due to various reasons related to both professional and personal life. 
> * Which resulted in me disabling the workflow (= reducing its production rate to zero) - but when I'll have more spare time / better mindset for FSAC work, I'll 100% enable again.
> * Keeping it enabled while I didn't had time created a bit of "notification anxiety" thing, that probably many of maintainers know well - you know, you wake up, open GH and see whole bunch of notifications, and you're like "oh no my life sucks"

*Editorial note: The exact numbers confirm the maintainer's observation — 33 Repo Assist PRs were merged in the ~2 month active period (Feb 22 – Apr 15, 2026), compared to 53 total PRs merged across all of 2025. This represents 62% of a full year's output in roughly one-sixth of the time.*

### Appendix E: Maintainer Notes — fantomas

The following are lightly edited notes from the fantomas maintainer (Florian Verdonck / @nojaf), providing qualitative context for the high rejection rate observed in that repository.

> A few observations from using repo-assist on Fantomas:
>
> 1. **It did rekindle some engagement.** Repo-assist genuinely gave me a renewed spark with Fantomas for a while. That part was real. But over time it became a bit too noisy relative to the amount of attention I want to give that project right now. Fantomas is not my main focus these days, so I reduced the frequency of repo-assist interactions to monthly. Eventually the value wore off more because of that mismatch than because of any one specific failure mode.
>
> 2. **Fantomas is a difficult target because many fixes need broader judgement.** For a formatter, a change can fix one reported case while moving the implementation in a direction that is not actually desirable overall, or by breaking other cases. Sometimes tests catch that, sometimes they do not, and sometimes you can simply tell the fix is too specific or not in the right spirit even if the tests pass. In those cases, it was often easier to close the PR and redo it myself than to try to steer multiple rounds of correction.
>
> 3. **Not every open issue is really implementation-ready.** Some Fantomas issues are not straightforward engineering tasks. They are closer to unresolved discussions about behaviour, trade-offs, or differing opinions between me and the reporter. As maintainer, I do not always want to close those immediately, so they can remain open for a while. But that means an open issue is not necessarily a green light for implementation. Repo-assist sometimes treated those limbo issues as actionable, which led to PRs that were unlikely to land from the start.
>
> I think those three things explain a fair bit of why there were so many closed PRs in that repo.

*Editorial note: The maintainer's feedback highlights three distinct causes of rejection: (1) automation fatigue — the workflow's value diminished as it exceeded the maintainer's available bandwidth, leading to a deliberate rate reduction; (2) domain complexity — formatting correctness requires holistic judgement that cannot be captured by test coverage alone, making it cheaper to redo than to steer; and (3) issue ambiguity — some open issues represent unresolved design discussions rather than actionable tasks, and the agent cannot distinguish between them. The maintainer ultimately reduced the workflow to a monthly cadence rather than disabling it entirely.*
