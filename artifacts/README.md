# Artifacts

Output máy sinh ra từ preprocessing, training, scoring và evaluation.

```text
preprocessing/  Feature matrix, feature columns, source summary
models/         Model artifact, model metadata, anomaly scores
predictions/    Batch inference outputs
evaluation/     Evaluation tables, feature lift, metrics
```

Artifact lớn như `.csv`, `.joblib`, `.pkl`, `.parquet` được ignore theo mặc định.
