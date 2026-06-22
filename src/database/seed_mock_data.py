from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

MODEL_VERSION = "ocsvm-v1.0-cert"



def load_csv_data(conn):
    import json
    import os

    import pandas as pd

    from src.backend.app.db.session import utc_now

    data_dir = os.getenv("DATA_DIR", str(ROOT_DIR / "data" / "sample" / "cert-r4.2-small"))
    if not os.path.exists(data_dir):
        raise Exception(f"Data directory {data_dir} does not exist.")

    now = utc_now()
    total_loaded = 0
    event_type_counts = {}
    total_users = set()
    total_devices = set()

    def optional_text(value):
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None
        return text

    for filename in os.listdir(data_dir):
        if not filename.endswith(".csv"):
            continue

        file_path = os.path.join(data_dir, filename)
        event_type = filename.split('.')[0]

        try:
            df = pd.read_csv(file_path)
            if df.empty:
                continue

            col_map = {
                "id": "source_id",
                "date": "timestamp",
                "user": "user_id",
                "pc": "device_id",
                "activity": "action"
            }
            df.rename(columns=col_map, inplace=True)

            if "url" in df.columns:
                df["resource"] = df["url"]
            elif "filename" in df.columns:
                df["resource"] = df["filename"]
            elif "to" in df.columns:
                df["resource"] = df["to"]
            else:
                if "resource" not in df.columns:
                    df["resource"] = ""

            if "action" not in df.columns:
                df["action"] = event_type.upper()

            if "user_id" in df.columns:
                unique_users = df["user_id"].dropna().unique()
                for u in unique_users:
                    total_users.add(u)
                user_records = [(u, u, u, f"{u.lower()}@dtaa.com", "Unknown", "Employee", "active", 0, now, now) for u in unique_users if u]
                if user_records:
                    with conn.cursor() as cur:
                        cur.executemany(
                            """
                            INSERT INTO users (id, username, full_name, email, department, job_role, status, risk_score, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT(id) DO NOTHING
                            """,
                            user_records
                        )

            if "device_id" in df.columns:
                unique_devices = df["device_id"].dropna().unique()
                for d in unique_devices:
                    total_devices.add(d)
                device_records = [(d, d, "Unknown", "0.0.0.0", None, "online", 0, now, now, now) for d in unique_devices if d]
                if device_records:
                    with conn.cursor() as cur:
                        cur.executemany(
                            """
                            INSERT INTO devices
                            (id, hostname, os, ip_address, assigned_user_id, status, risk_score, last_seen, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT(id) DO NOTHING
                            """,
                            device_records
                        )

            records = []
            for _, row in df.iterrows():
                row_dict = row.dropna().to_dict()
                source_id = optional_text(row_dict.get("source_id"))
                timestamp = optional_text(row_dict.get("timestamp"))
                if not source_id or not timestamp:
                    continue

                user_id = optional_text(row_dict.get("user_id"))
                device_id = optional_text(row_dict.get("device_id"))
                action = optional_text(row_dict.get("action")) or event_type.upper()
                resource = optional_text(row_dict.get("resource")) or ""

                raw_json = json.dumps(row_dict)
                records.append((
                    source_id, filename, timestamp, user_id, device_id, event_type,
                    action, resource, "{}", raw_json, now
                ))

            # chunk the records to avoid memory issues with executemany
            chunk_size = 5000
            for i in range(0, len(records), chunk_size):
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO event_logs (
                            source_id, source_file, timestamp, user_id, device_id, event_type,
                            action, resource, metadata_json, raw_json, created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(source_id) DO NOTHING
                        """,
                        records[i:i+chunk_size]
                    )
            
            total_loaded += len(records)
            event_type_counts[event_type.lower()] = len(records)
            print(f"Loaded {len(records)} from {filename}")
        except Exception as e:
            print(f"Failed to load {filename}: {e}")

    print(f"Total CSV events loaded: {total_loaded}")
    return {
        "rows_imported": total_loaded,
        "users_found": len(total_users),
        "devices_found": len(total_devices),
        "event_types": event_type_counts
    }


def main() -> dict:
    import os

    from src.backend.app.db.session import get_connection, initialize_database, utc_now

    initialize_database()
    now = utc_now()

    model_path = os.getenv("MODEL_PATH", str(ROOT_DIR / "weights" / "ocsvm_cert_r42_chunked.joblib"))
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO model_artifacts (
                model_version, artifact_path, training_config_json, metrics_json, created_at
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT(model_version) DO UPDATE SET
                artifact_path = excluded.artifact_path,
                training_config_json = excluded.training_config_json,
                metrics_json = excluded.metrics_json
            """,
            (
                MODEL_VERSION,
                model_path,
                json.dumps({"source": "CERT r4.2 chunked", "detector": "OneClassSVM"}),
                json.dumps({"precision_at_k": 0.86, "roc_auc": 0.93}),
                now,
            ),
        )

        stats = load_csv_data(conn)

    print(
        f"Seeded real data: {stats.get('rows_imported', 0)} event logs, model {MODEL_VERSION}"
    )
    
    if not stats:
        stats = {
            "rows_imported": 0,
            "users_found": 0,
            "devices_found": 0,
            "event_types": {}
        }
    return stats

if __name__ == "__main__":
    main()
