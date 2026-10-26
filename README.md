# Shared agent skills

Install engineering, review, and writing skills for Codex, Claude Code, Hermes, Pi, and other agents from one collection.

## Choose skills and agents

With Node.js 22.20 or later and npm installed, run:

```sh
npx skills add jhs88/skills
```

Follow the prompts to choose skills and agents. By default, the CLI installs into your current project. You do not need to clone this repository or authenticate to GitHub.

If you already have skills with the same names, review those copies before replacing them.

## Install across projects

Add `-g` to install skills in your user directories instead of the current project:

```sh
npx skills add jhs88/skills -g
```

To install the whole collection for specific agents without prompts, run:

```sh
npx skills add jhs88/skills -g --skill '*' -a codex claude-code hermes-agent pi -y
```

Remove any agent names you do not use. Restart or reload your agent if the new skills do not appear.

## Select one skill

List the available skills without installing them:

```sh
npx skills add jhs88/skills --list
```

For example, install only `unslop` globally for Claude Code:

```sh
npx skills add jhs88/skills -g --skill unslop -a claude-code -y
```

The collection includes Matt Pocock's published engineering and productivity skills, adapted tstack PR workflows, and Pstack's `technical-writing` and `unslop`. Browse the [skill directories](skills) for their instructions.

## Refresh your installation

Rerun your `add` command to install the current selection from this repository. Choose newly added skills when prompted, or use `--skill '*'` to include all skills.

Repository updates do not change installed copies automatically. If a skill is removed from the collection, remove the installed copy explicitly:

```sh
npx skills remove <skill-name> -g
```

Omit `-g` for a project installation. Keep local customizations separate from installed copies so an update does not replace your work.

## Maintain the collection

See [verification](docs/verification.md) for contributor setup and tests, [Matt sync](docs/npm-skills-verification.md) for automated update PRs, and [adapted collections](docs/adapted-imports.md) for tstack and Pstack update checks.

Source repositories are listed in [sources](docs/provenance.md). Imported skill licenses and notices are in [LICENSES.md](LICENSES.md); original repository code and documentation do not yet have an assigned license.
