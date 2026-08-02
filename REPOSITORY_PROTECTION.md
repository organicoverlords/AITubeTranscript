# Repository protection

This repository uses layered protection against accidental or unauthorized edits, destructive pull requests, branch loss, and repository deletion.

## Protections stored in the repository

- `.github/CODEOWNERS` assigns every path to `@organicoverlords`.
- `Repository protection / guard` rejects deletion or renaming of critical source, test, workflow, licensing, packaging, and recovery files.
- Destructive changes require both the repository owner and the `allow-destructive-change` pull-request label.
- Every guard run creates a SHA-256 manifest of all tracked files.
- `Repository backup` creates a complete Git bundle on every `main` push, weekly, and on demand.
- Backup artifacts include every fetched branch, tag, commit, tree, and blob and are retained for 90 days.
- When `BACKUP_PAT` is configured, every backup also pushes immutable commit-addressed recovery branches into the separate private repository selected by `BACKUP_REPOSITORY` (default: `organicoverlords/all`).

## Required GitHub ruleset for `main`

Repository files cannot activate GitHub branch rules by themselves. An administrator must create a branch ruleset in **Settings → Rules → Rulesets** with the following values:

- Target branch: `main`
- Restrict deletions: enabled
- Block force pushes: enabled
- Require a pull request before merging: enabled
- Required approvals: 1
- Require review from Code Owners: enabled
- Dismiss stale approvals: enabled
- Require conversation resolution: enabled
- Require status checks: enabled
- Required checks:
  - `test (3.10)`
  - `test (3.12)`
  - `guard`
- Require branches to be up to date before merging: enabled
- Do not allow bypassing the above settings: enabled, except an emergency owner role if desired

Apply an equivalent deletion and force-push restriction to the `results` branch. The results branch needs GitHub Actions write access, so do not require pull requests for that branch unless the publishing workflow is redesigned.

## Deletion-safe external mirror

GitHub's built-in workflow token cannot write to another private repository. To enable the external mirror:

1. Create a fine-grained personal access token with **Contents: read and write** access to `organicoverlords/all`.
2. Add it to this repository as the Actions secret `BACKUP_PAT`.
3. Optionally set the Actions variable `BACKUP_REPOSITORY`; the default is `organicoverlords/all`.
4. Run **Actions → Repository backup → Run workflow**.
5. Confirm the log contains `EXTERNAL_MIRROR=PROVEN`.

The mirror creates branches under:

```text
backups/AITubeTranscript/main-<commit-sha>
backups/AITubeTranscript/latest-<source-branch>
```

It never overwrites the backup repository's normal branches.

## Recovery

From a downloaded bundle:

```bash
git clone AITubeTranscript.bundle AITubeTranscript-recovered
git -C AITubeTranscript-recovered bundle verify ../AITubeTranscript.bundle
```

From the private mirror, create a new repository and push the desired recovery branch or commit into it.

## Truth classification

- In-repository guardrails: active after this change reaches `main`.
- 90-day Git-bundle artifacts: active after this change reaches `main` and the backup workflow completes.
- Cross-repository deletion-safe mirror: `NOT_PROVEN` until `BACKUP_PAT` is configured and a workflow log reports `EXTERNAL_MIRROR=PROVEN`.
- GitHub branch deletion/direct-push prevention: `NOT_PROVEN` until the ruleset described above is enabled in repository settings.
