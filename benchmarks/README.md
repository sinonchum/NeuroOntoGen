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
- prompt stability score plus graph-level diagnostics for deterministic Turtle prompt variants;
- schema discovery term/cluster counts plus a human-reviewable LinkML draft generated from smoke domain terms;
- per-case SHACL reports.

## Markdown summary

```bash
python benchmarks/run_benchmark.py \
  --dataset examples/company \
  --quick \
  --output-markdown build/benchmark-summary.md
```

The benchmark skeleton is not a scientific benchmark yet. It is a reproducible smoke entrypoint for the future evaluation layer, where exact match, fuzzy token F1, SHACL conformance, repair success, RDF graph stability metrics, and human-reviewed clustering discovery diagnostics can be applied to larger datasets.
