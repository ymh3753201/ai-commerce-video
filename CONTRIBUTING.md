# Contributing

Contributions are welcome when they preserve the Skill's paid-generation, asset-consistency, subtitle, and delivery gates.

## Before Opening a Pull Request

1. Do not include API keys, customer assets, generated videos, request IDs, or private env files.
2. Run:

   ```bash
   python3 scripts/audit_release.py
   PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
   ```

3. Explain the user-facing behavior change.
4. Add a regression test for every behavior or safety change.

## Model Adapter Contributions

A model adapter is not complete when only a model ID or base URL changes. Include:

- provider and authentication contract;
- dedicated environment-variable names;
- create, poll, and result endpoints;
- exact request and response fields;
- duration, resolution, aspect-ratio, and reference-image limits;
- text/image/reference/edit/extend capabilities;
- audio, speech, and lip-sync behavior;
- prompt limits;
- mocked submit/poll tests and no-key preflight coverage;
- updated model-capability documentation.

Do not silently change the behavior of an existing validated model key. Add a new model key when the provider schema or capability contract differs.

## Pull Request Scope

Keep commerce-ad production separate from general creator talking-head workflows. Do not remove the two-confirmation flow, clean-provider-frame rule, one-paid-submit rule, or final delivery manifest gate.
