# Agent

Endpoint agent hoặc mock agent gửi event log về backend.

## Trách nhiệm

- Thu thập hoặc mô phỏng endpoint events.
- Sinh normal/anomaly behavior để demo.
- Gửi events qua REST API backend.
- Tuân thủ event schema trong `docs/DATA_CONTRACT.md`.

## Cấu trúc dự kiến

```text
ueba_agent/
  collectors/
  transport/
simulators/
tests/
```
