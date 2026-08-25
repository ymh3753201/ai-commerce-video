# Security Policy

## Secrets

Do not place API keys, authorization headers, private env files, customer assets, request records, or generated media in this repository.

Use:

```text
~/.codex/ai-commerce-video.env
```

On macOS, the default setup stores the MikuAPI key in Keychain service
`ai-commerce-video-mikuapi-video` and creates this owner-only file for the
non-secret MikuAPI base URL and model settings. CI systems should inject
`AI_COMMERCE_VIDEO_MIKUAPI_KEY` through their secret manager. Use
`setup_private_env.py --route xai-reference` only when intentionally configuring
the optional official route; it uses the separate `ai-commerce-video-xai-video`
Keychain service and `XAI_API_KEY`.

## Provider Trust

The default route calls MikuAPI, a third-party relay rather than an xAI-operated
service. The optional `119337` route is also a third-party gateway. Review a
provider's privacy, billing, retention, moderation, and account-security terms
before uploading product images or credentials.

Do not reuse a credential issued for one provider on another provider's host.

The default and single-image MikuAPI entries accept only
`AI_COMMERCE_VIDEO_MIKUAPI_KEY` or their MikuAPI Keychain service. The optional
official xAI entry accepts only `XAI_API_KEY` or its dedicated Keychain service. The optional `119337`
entry accepts only `AI_COMMERCE_VIDEO_119337_KEY` or Keychain service
`ai-commerce-video-119337-video`. All third-party routes
deliberately exclude `XAI_API_KEY` to prevent accidental credential forwarding.

## Reporting a Vulnerability

When reporting a security problem, include:

- the affected script and command;
- whether a paid request can be triggered;
- whether credentials or local files can be exposed;
- a minimal reproduction without real API keys or customer materials.

Do not publish live credentials, private request IDs, or customer assets in a public issue.
