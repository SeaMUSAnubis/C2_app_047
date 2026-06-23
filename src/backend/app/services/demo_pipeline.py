from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.exceptions import InconsistentVersionWarning

from src.backend.app.services.llm import explain_alert

warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

ROOT_DIR = Path(__file__).resolve().parents[4]  # services -> app -> backend -> src -> repo root
MODEL_PATH = os.getenv(
    "OCSVM_MODEL_PATH",
    os.getenv("MODEL_PATH", str(ROOT_DIR / "src" / "ml" / "weights" / "ocsvm_cert_r42_chunked.joblib")),
)
DATA_DIR = os.getenv("DATA_DIR", str(ROOT_DIR / "data" / "sample" / "cert-r4.2-small"))

class DemoPipeline:
    def __init__(self):
        self.model = None
        self.feature_columns = None
        self._load_model()

    def _load_model(self) -> None:
        if not os.path.exists(MODEL_PATH):
            print(f"DemoPipeline warning: Model not found at {MODEL_PATH}")
            return
        
        try:
            loaded = joblib.load(MODEL_PATH)
            if isinstance(loaded, dict):
                self.model = loaded.get("pipeline", loaded.get("model"))
                # The saved dict uses "feature_cols" (not "feature_columns")
                self.feature_columns = loaded.get(
                    "feature_cols",
                    loaded.get("feature_columns", getattr(self.model, "feature_names_in_", [])),
                )
            else:
                self.model = loaded
                self.feature_columns = getattr(self.model, "feature_names_in_", [])

            if hasattr(self.feature_columns, "tolist"):
                self.feature_columns = self.feature_columns.tolist()

            print(f"DemoPipeline: model loaded, {len(self.feature_columns)} features: {self.feature_columns}")

        except Exception as e:
            print(f"DemoPipeline error loading model: {e}")

    @staticmethod
    def _is_after_hours(ts_str: str | None) -> bool:
        """Check whether a timestamp falls outside 08:00–18:00."""
        if not ts_str:
            return False
        try:
            from datetime import datetime as dt
            ts = dt.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            return ts.hour < 8 or ts.hour >= 18
        except (ValueError, TypeError):
            try:
                ts = dt.strptime(str(ts_str), "%m/%d/%Y %H:%M:%S")
                return ts.hour < 8 or ts.hour >= 18
            except (ValueError, TypeError):
                return False

    def extract_features(self, events: list[dict[str, Any]]) -> pd.DataFrame:
        """Extract the 20 features the OCSVM model was actually trained on.

        Feature list (from ocsvm_cert_r42_chunked.joblib):
          logon_count, logon_after_hours_count,
          logon_activity_Logoff_count, logon_activity_Logon_count,
          device_count, device_after_hours_count,
          device_activity_Connect_count, device_activity_Disconnect_count,
          file_count, file_after_hours_count,
          email_count, email_after_hours_count,
          email_size_sum, email_size_mean, email_size_max,
          email_attachments_sum, email_attachments_mean, email_attachments_max,
          http_count, http_after_hours_count
        """
        if not events:
            return pd.DataFrame()

        df = pd.DataFrame(events)
        if df.empty:
            return pd.DataFrame()

        # Extract activity / timestamp from raw payload when available
        def _col_or_raw(col: str) -> pd.Series:
            if col in df.columns:
                return df[col].fillna("")
            return pd.Series([""] * len(df), index=df.index)

        activity = _col_or_raw("activity")
        action = _col_or_raw("action")
        ts_col = _col_or_raw("timestamp")

        # Effective activity: prefer raw.activity, fall back to action
        eff_activity = activity.where(activity != "", action)

        after_hours_mask = ts_col.apply(self._is_after_hours)

        # ── Logon ──
        logon_mask = df["event_type"] == "logon"
        logons = df[logon_mask]
        logon_activity = eff_activity[logon_mask].str.lower()
        logon_ah = after_hours_mask[logon_mask]

        logon_count = int(logon_mask.sum())
        logon_after_hours_count = int(logon_ah.sum())
        logon_activity_Logoff_count = int((logon_activity == "logoff").sum())
        logon_activity_Logon_count = int((~logon_activity.isin(["logoff"])).sum())

        # ── Device ──
        device_mask = df["event_type"] == "device"
        device_activity = eff_activity[device_mask].str.lower()
        device_ah = after_hours_mask[device_mask]

        device_count = int(device_mask.sum())
        device_after_hours_count = int(device_ah.sum())
        device_activity_Connect_count = int((device_activity == "connect").sum())
        device_activity_Disconnect_count = int((device_activity == "disconnect").sum())

        # ── File ──
        file_mask = df["event_type"] == "file"
        file_ah = after_hours_mask[file_mask]

        file_count = int(file_mask.sum())
        file_after_hours_count = int(file_ah.sum())

        # ── Email ──
        email_mask = df["event_type"] == "email"
        emails = df[email_mask]
        email_ah = after_hours_mask[email_mask]

        email_count = int(email_mask.sum())
        email_after_hours_count = int(email_ah.sum())

        sizes = pd.to_numeric(_col_or_raw("size")[email_mask], errors="coerce").fillna(0).astype(int)
        email_size_sum = int(sizes.sum())
        email_size_mean = float(sizes.mean()) if email_count > 0 else 0.0
        email_size_max = int(sizes.max()) if email_count > 0 else 0

        attach = pd.to_numeric(_col_or_raw("attachments")[email_mask], errors="coerce").fillna(0).astype(int)
        email_attachments_sum = int(attach.sum())
        email_attachments_mean = float(attach.mean()) if email_count > 0 else 0.0
        email_attachments_max = int(attach.max()) if email_count > 0 else 0

        # ── HTTP ──
        http_mask = df["event_type"] == "http"
        http_ah = after_hours_mask[http_mask]

        http_count = int(http_mask.sum())
        http_after_hours_count = int(http_ah.sum())

        features = {
            "logon_count": logon_count,
            "logon_after_hours_count": logon_after_hours_count,
            "logon_activity_Logoff_count": logon_activity_Logoff_count,
            "logon_activity_Logon_count": logon_activity_Logon_count,
            "device_count": device_count,
            "device_after_hours_count": device_after_hours_count,
            "device_activity_Connect_count": device_activity_Connect_count,
            "device_activity_Disconnect_count": device_activity_Disconnect_count,
            "file_count": file_count,
            "file_after_hours_count": file_after_hours_count,
            "email_count": email_count,
            "email_after_hours_count": email_after_hours_count,
            "email_size_sum": email_size_sum,
            "email_size_mean": email_size_mean,
            "email_size_max": email_size_max,
            "email_attachments_sum": email_attachments_sum,
            "email_attachments_mean": email_attachments_mean,
            "email_attachments_max": email_attachments_max,
            "http_count": http_count,
            "http_after_hours_count": http_after_hours_count,
        }

        row = pd.DataFrame([features])

        # Align to model's expected column order, fill missing with 0
        if self.feature_columns:
            for col in self.feature_columns:
                if col not in row.columns:
                    row[col] = 0.0
            row = row[self.feature_columns]

        return row

    def analyze(self, events: list[dict[str, Any]], user_id: str) -> dict[str, Any]:
        if not self.model:
            return {"error": "Model is not loaded on server."}

        # Flatten 'raw' into top-level for easier processing
        flattened_events = []
        for e in events:
            flat_e = dict(e)
            if "raw" in flat_e and isinstance(flat_e["raw"], dict):
                for k, v in flat_e["raw"].items():
                    if k not in flat_e:
                        flat_e[k] = v
            flattened_events.append(flat_e)

        events = flattened_events
        features_df = self.extract_features(events)
        if features_df.empty:
            return {"error": "No valid features could be extracted."}

        try:
            # Predict returns 1 for inliers, -1 for outliers/anomalies
            prediction = self.model.predict(features_df)[0]
            is_anomaly = bool(prediction == -1)
            
            score = 0.0
            if hasattr(self.model, "decision_function"):
                score = float(self.model.decision_function(features_df)[0])
                
            # For OCSVM, decision_function < 0 is anomaly. 
            risk_score = 85 if is_anomaly else 20
        except Exception as e:
            return {"error": f"Prediction failed: {e}"}

        # Identify top drivers based on the raw events directly to avoid KeyError
        top_factors = []
        if is_anomaly:
            has_exe = any(e.get("filename", "").endswith("exe") for e in events if e.get("event_type") == "file")
            has_device_connect = any(e.get("activity") == "Connect" for e in events if e.get("event_type") == "device")
            if has_exe:
                top_factors.append("n_file_exe")
            if has_device_connect:
                top_factors.append("n_device_afterhours")
            if not top_factors:
                top_factors.append("unusual_behavior_pattern")

        # Generate timeline string.
        # Cap the number of events sent to the LLM so the prompt stays within the
        # model's context window (the OCSVM prediction above still uses ALL events).
        MAX_TIMELINE_EVENTS = 50
        timeline_events = events[-MAX_TIMELINE_EVENTS:]
        timeline_parts = []
        for e in timeline_events:
            t = e.get("date", e.get("timestamp", ""))
            action = e.get("activity", e.get("event_type", ""))
            timeline_parts.append(f"{t}: {action}")
        if len(events) > MAX_TIMELINE_EVENTS:
            timeline_parts.insert(
                0, f"... ({len(events) - MAX_TIMELINE_EVENTS} earlier events omitted) ..."
            )
        timeline_str = "\n  ".join(timeline_parts) if timeline_parts else "No timeline available"

        context = {
            "alert_id": "DEMO-ALERT-001",
            "user_id": user_id,
            "device_id": "UNKNOWN",
            "severity": "critical" if is_anomaly else "low",
            "risk_score": risk_score,
            "anomaly_score": score,
            "top_features": top_factors,
            "timeline": f"  {timeline_str}"
        }

        explanation = explain_alert(context) if is_anomaly else "Behavior is within normal baseline. No threats detected."

        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": score,
            "risk_score": risk_score,
            "top_factors": top_factors,
            "explanation": explanation
        }

def load_user_events_from_demo_csv(user_id: str) -> list[dict[str, Any]]:
    import os

    import pandas as pd
    data_dir = DATA_DIR
    events = []
    
    csv_types = {
        "logon.csv": "logon",
        "device.csv": "device",
        "http.csv": "http",
        "email.csv": "email",
        "file.csv": "file"
    }
    
    for filename, event_type in csv_types.items():
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            continue
        try:
            df = pd.read_csv(filepath)
            # Filter by user
            if "user" in df.columns:
                user_df = df[df["user"] == user_id].copy()
                if not user_df.empty:
                    user_df["event_type"] = event_type
                    # Convert date to timestamp for timeline mapping
                    if "date" in user_df.columns:
                        user_df["timestamp"] = user_df["date"]
                    events.extend(user_df.to_dict("records"))
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            
    return events

demo_pipeline = DemoPipeline()
