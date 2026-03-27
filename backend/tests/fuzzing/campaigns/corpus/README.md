# Fuzzing Corpus Directory

This directory contains interesting inputs discovered during fuzzing campaigns.

## Purpose

Atheris automatically saves "interesting inputs" to this directory during fuzzing runs. These inputs can be used to re-seed future campaigns for faster coverage.

## Structure

```
corpus/
├── auth/          # Interesting inputs for auth endpoints
├── agent/         # Interesting inputs for agent endpoints
├── workflow/      # Interesting inputs for workflow endpoints
└── ...            # Other endpoint categories
```

## Re-seeding Campaigns

When starting a fuzzing campaign, Atheris will automatically use existing corpus files as seed inputs:

```python
# Atheris automatically reads from corpus directory
atheris.Fuzz(
    lambda data: test_api_endpoint(data),
    [f"corpus/auth/*"]  # Seed with existing corpus
)
```

## Corpus Management

- **Automatic**: Atheris automatically saves interesting inputs to corpus
- **Manual**: You can manually add known edge cases to corpus
- **Cleanup**: Remove redundant corpus files periodically (Atheris will deduplicate)

## Corpus Quality

Good corpus files include:
- Edge cases (empty strings, null bytes, special characters)
- Boundary conditions (max lengths, overflow values)
- Interesting structures (malformed JSON, invalid UTF-8)
- Security-relevant inputs (SQL injection, XSS patterns)

## File Format

Corpus files are binary files containing raw input data that triggered interesting code paths during fuzzing.
