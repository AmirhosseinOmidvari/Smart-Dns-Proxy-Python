# Team plan

## Member 1: repository owner

Owns the domain pipeline and deterministic decision engine: configuration validation, domain normalization, boundary aware list matching, FIFO TTL cache, result models, and the resolver orchestration.

## Mahdis: network transport

Owns the network boundary: raw UDP text transport, the local upstream simulator, real DNS packet transport for the optional feature, and transport failure handling.

## Matin: user interface and verification

Owns the console protocol, optional commands, structured logging, acceptance tests, sample files, and the final README. This member also runs the complete T1-T13 checklist after the first two patches are merged.

## Integration rule

Work on separate branches from `main`. Each member applies only the patch assigned to them after the previous patch has been applied. The final branch is validated with `python -m pytest` and the manual two-process UDP run described in the README.
