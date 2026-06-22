# Mô hình ML

Thư mục này chứa phần ML đã được bảo toàn: code inference, service, model weight và script liên quan ML.

- `weights/`: lưu model weight đang dùng để inference.
- `services/ueba_ml/`: lưu wrapper inference và code service ML hiện tại.
- `scripts/`: lưu script preprocessing/training ML. Không chạy training trong quá trình refactor hoặc demo Docker.
- `legacy_review/`: chứa các utility project-specific cần review thủ công trước khi xóa hoặc chuyển vị trí.

Các thư mục root `artifacts/`, `data/`, `eval/` vẫn được giữ ngoài `src/` để lưu output model, dataset và report đánh giá.
