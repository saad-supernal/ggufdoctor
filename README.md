# ggufdoctor

A command-line linter for the chat template embedded in a GGUF model file.

`tokenizer.chat_template` is arbitrary Jinja2 that most GGUF tooling never
validates before shipping. `ggufdoctor` renders it against a small corpus of
realistic conversations and checks it against the file's own vocab and
special-token metadata, catching the failure modes that otherwise only show
up at inference time: templates that don't compile, that raise on an
ordinary conversation, that emit tokens absent from the vocab, that never
emit the declared EOS, that duplicate BOS, or that silently ignore
`add_generation_prompt`.

## Install

```
pip install ggufdoctor
```

## Usage

Lint a local file or a Hugging Face repo id directly:

```
ggufdoctor path/to/model.gguf
ggufdoctor some-org/some-model-GGUF
ggufdoctor path/to/model.gguf --compare-upstream some-org/some-model --json report.json
```

Survey chat-template divergence from upstream across the GGUF ecosystem on
Hugging Face:

```
ggufdoctor survey --top 200 --per-org 2 --markdown survey.md
```

Run `ggufdoctor --help` or `ggufdoctor survey --help` for the full flag
reference.

## License

Not yet chosen. No license is granted until one is added here.
