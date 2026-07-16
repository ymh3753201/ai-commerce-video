# Security Policy

## Secrets

Do not place API keys, authorization headers, private env files, customer assets, request records, or generated media in this repository.

Use:

```text
~/.codex/ai-commerce-video.env
```

The setup script creates this file with owner-only permissions.

## Provider Trust

The bundled `119337` route is a third-party gateway, not an xAI-operated service. Review a provider's privacy, billing, retention, moderation, and account-security terms before uploading product images or credentials.

Do not reuse a credential issued for one provider on another provider's host.

The bundled `119337` model entries accept only `AI_COMMERCE_VIDEO_API_KEY` or `YUNWU_API_KEY`. They deliberately exclude `XAI_API_KEY` to prevent accidental credential forwarding.

## Reporting a Vulnerability

When reporting a security problem, include:

- the affected script and command;
- whether a paid request can be triggered;
- whether credentials or local files can be exposed;
- a minimal reproduction without real API keys or customer materials.

Do not publish live credentials, private request IDs, or customer assets in a public issue.
