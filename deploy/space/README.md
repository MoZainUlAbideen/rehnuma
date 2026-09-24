---
title: Rehnuma API
emoji: ⚡
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
short_description: Pakistani electricity bills - audit, summary, cited NEPRA rules
---

# Rehnuma (رہنما) - API

The backend of **Rehnuma**, an AI copilot that audits Pakistani electricity bills,
explains them in Urdu or English, and answers questions about NEPRA rules with citations
to the official documents.

- Interactive API docs: `/docs`
- Health: `/api/health`
- Code, tests and evals: https://github.com/MoZainUlAbideen/rehnuma

This Space is deployed automatically from the GitHub repository on every push to `main`
(`.github/workflows/deploy-space.yml`). Uploaded bill photos are processed in memory and
never stored.
