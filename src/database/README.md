# Cơ sở dữ liệu

Thư mục này chứa schema, migration và seed cho PostgreSQL của demo UEBA.

- `init.sql`: tạo các bảng tối thiểu cần cho refactor gồm `users`, `logs`, `alerts`, `model_predictions`.
- `seed.sql`: nạp một ít dữ liệu demo ban đầu.
- `seed_mock_data.py` và `load_cert_data.py`: giữ lại utility nạp dữ liệu cũ trong `src/database/`.

Runtime helper để backend làm việc với database nằm tại `src/backend/app/db/session.py`.
