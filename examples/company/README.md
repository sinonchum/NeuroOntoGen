# Company example

This directory contains minimal Turtle data graphs for the built-in company-access ontology fixture.

## Compile the schema

From the repository root:

```bash
neuro-onto-gen compile-schema schemas/company_schema.yaml build/schema
```

This writes:

```text
build/schema/company_schema.schema.json
build/schema/company_schema.shacl.ttl
build/schema/company_schema.ttl
```

## Validate a conforming graph

```bash
neuro-onto-gen validate-turtle examples/company/valid_abox.ttl build/schema/company_schema.shacl.ttl
```

Expected output includes:

```text
conforms: true
```

The command exits with status `0`.

## Validate a non-conforming graph

```bash
neuro-onto-gen validate-turtle examples/company/invalid_abox.ttl build/schema/company_schema.shacl.ttl
```

Expected output includes:

```text
conforms: false
requiredClearance
```

The command exits with status `1` because `invalid_abox.ttl` intentionally omits `ex:requiredClearance` on a `ex:SecureAsset` individual.
