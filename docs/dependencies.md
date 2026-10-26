# Dependency updates (Dependabot)

[Dependabot](https://docs.github.com/en/code-security/dependabot) is GitHub's
built-in bot that keeps dependencies current. It is configured in two places:

| Concern | Configured in | What it does |
| --- | --- | --- |
| **Version updates** | [`.github/dependabot.yml`](../.github/dependabot.yml) | Opens PRs for outdated dependencies on a schedule. |
| **Security updates** | Repo **Settings → Code security** | Opens a PR when a dependency gets a published advisory. |
| **Auto-merge** | [`.github/workflows/dependabot-automerge.yml`](../.github/workflows/dependabot-automerge.yml) | Merges green *patch* updates automatically. |

## Version update config

```yaml
version: 2
updates:
  - package-ecosystem: uv            # reads pyproject.toml + uv.lock
    directory: /
    schedule: { interval: weekly }
    open-pull-requests-limit: 10
    groups:
      python-minor-patch:            # one PR for all minor+patch bumps
        patterns: ["*"]
        update-types: [minor, patch]

  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: weekly }

  - package-ecosystem: docker
    directory: /
    schedule: { interval: weekly }
```

- Three ecosystems are watched: Python (`uv`), GitHub Actions, and Docker images.
- **Grouping** bundles every minor/patch update into a single Python PR, which
  keeps the noise down. **Major** updates are deliberately *not* grouped — they
  arrive one per PR so breaking changes get individual review.
- Dependabot only runs against the **default branch** (`master`). The config is
  inert until it is merged there.

## Auto-merge workflow

`.github/workflows/dependabot-automerge.yml` enables
[GitHub auto-merge](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request)
for Dependabot PRs whose **highest** bump is a patch:

```yaml
on: pull_request_target
permissions:
  contents: write
  pull-requests: write
jobs:
  auto-merge:
    if: github.event.pull_request.user.login == 'dependabot[bot]'
    steps:
      - uses: dependabot/fetch-metadata@v3
        id: metadata
      - if: steps.metadata.outputs.update-type == 'version-update:semver-patch'
        run: gh pr merge --auto --squash "$PR_URL"
```

### Why `update-type == semver-patch`

`fetch-metadata` reports `update-type` as **the highest semver change in the
PR**. So:

- A single patch update → `semver-patch` → auto-merged.
- A grouped PR where every update is a patch → `semver-patch` → auto-merged.
- A grouped PR that includes any minor/major → `semver-minor`/`semver-major` →
  **not** auto-merged; it waits for a human.

That is exactly "auto-merge grouped patch updates", and it keeps minor releases
(which can add behaviour) under review.

### Prerequisites (required)

Auto-merge is only as safe as your branch protection. Enable **both**:

1. **Settings → General → Pull Requests → Allow auto-merge.**
2. A **branch protection rule on `master`** that requires the CI status checks
   (the `quality` job from [`ci.yml`](../.github/workflows/ci.yml)).

Auto-merge completes only once all *required* checks pass. If nothing is marked
required, GitHub may merge before CI finishes — so requirement #2 is what makes
"when CI is green" true. See [operations.md](operations.md#ci).

### Why `pull_request_target`

Workflows triggered by Dependabot on the `pull_request` event run with a
**read-only `GITHUB_TOKEN`**, which cannot enable auto-merge.
`pull_request_target` runs in the base-repo context with the write permissions
declared above.

> **Security:** `pull_request_target` has write access and can read secrets.
> This workflow is safe because it only reads PR metadata and calls `gh` — it
> **never checks out or runs code from the PR**. Do not add an
> `actions/checkout` of the head ref or execute PR-authored scripts here.

## Adjusting it

- **Different merge style:** use `--merge` or `--rebase` instead of `--squash`.
- **Exclude dev dependencies:** add
  `&& steps.metadata.outputs.dependency-type == 'direct:production'` to the step
  `if`.
- **Restrict to safe packages:** add `contains(steps.metadata.outputs.dependency-names, 'pkg')`.
- **Only this repo:** add `&& github.repository == 'owner/repo'` (the template
  omits it so forks behave identically).
- **Never auto-merge anything:** delete the workflow and rely on manual review.

## How it relates to `pip-audit`

They are complementary:

- **`pip-audit`** (in CI) is a point-in-time gate that fails the build if a
  *known vulnerability* is present in the tree.
- **Dependabot** is continuous: version updates move you forward proactively and
  security updates react to new advisories between scheduled runs.

## Verifying it works

- Merge the config to `master`; Dependabot starts opening PRs.
- **Insights → Dependency graph → Dependabot** lists what it tracks.
- **Settings → Code security** shows alerts and security-update status.
- The **Dependabot** tab has a "Check for updates" button to trigger a run.
- Auto-merged PRs appear as merged by `github-actions[bot]` once checks pass.
