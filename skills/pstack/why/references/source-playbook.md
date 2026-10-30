# Source playbooks

Provider names, schemas, and commands below are examples. Discover available tools and verify their current schemas before use. Use only authorized read operations; report unavailable sources without inventing results.

The why skill spawns one investigator per available evidence category, each reading a single source-specific playbook below. The playbooks are concrete examples for common MCPs. Adapt them for a different MCP in the same category.

| Category | Playbook | Example MCP it documents |
|---|---|---|
| Source control history | [`sources/code-archaeology.md`](./sources/code-archaeology.md) | git, `gh` |
| Issue / ticket tracker | [`sources/linear.md`](./sources/linear.md) | Linear (adapt for Jira, GitHub Issues, Plane, Shortcut) |
| Long-form documents | [`sources/notion.md`](./sources/notion.md) | Notion (adapt for Confluence, Google Docs, Coda) |
| Real-time team chat | [`sources/slack.md`](./sources/slack.md) | Slack (adapt for Discord, Microsoft Teams, Mattermost) |
| Infrastructure observability | [`sources/datadog.md`](./sources/datadog.md) | Datadog (adapt for New Relic, Honeycomb, Grafana, Splunk) |
| Error / exception tracking | [`sources/sentry.md`](./sources/sentry.md) | Sentry (adapt for Rollbar, Bugsnag, Airbrake) |
| Product analytics warehouse | [`sources/databricks.md`](./sources/databricks.md) | Databricks SQL (adapt for Snowflake, BigQuery, ClickHouse, dbt) |

Cross-cutting:

- [`sources/incident-postmortem.md`](./sources/incident-postmortem.md). Add this if the target code looks defensive (null checks, retry, timeout, rate limit, feature flag, egress guard, OOM handler).
