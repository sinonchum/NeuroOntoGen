# Benchmark skeleton

This directory contains the first deterministic benchmark scaffold for NeuroOntoGen.

The current benchmark is intentionally small. It evaluates the runnable company examples with the same schema compilation and SHACL validation path used by the SDK and CLI smoke tests.

## Quick benchmark

From the repository root:

```bash
python benchmarks/run_benchmark.py --dataset examples/company --quick
```

The command writes a JSON summary to stdout with:

- dataset path;
- mode;
- case count;
- SHACL conformance rate;
- placeholder repair success rate;
- placeholder prompt stability score;
- per-case SHACL reports.

## Markdown summary

```bash
python benchmarks/run_benchmark.py \
  --dataset examples/company \
  --quick \
  --output-markdown build/benchmark-summary.md
```

The benchmark skeleton is not a scientific benchmark yet. It is a reproducible smoke entrypoint for the future evaluation layer, where exact match, fuzzy token F1, SHACL conformance, repair success, and prompt stability metrics will be applied to larger datasets.
