from __future__ import annotations

import os
from typing import Any

import joblib
import pandas as pd

from src.services.llm import explain_alert

MODEL_PATH = r"d:\2 Code\TEAM_O47\Weight\ocsvm_cert_r42_chunked.joblib"

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
                self.feature_columns = loaded.get("feature_columns", getattr(self.model, "feature_names_in_", []))
            else:
                self.model = loaded
                self.feature_columns = getattr(self.model, "feature_names_in_", [])
                
            if hasattr(self.feature_columns, "tolist"):
                self.feature_columns = self.feature_columns.tolist()

        except Exception as e:
            print(f"DemoPipeline error loading model: {e}")

    def extract_features(self, events: list[dict[str, Any]]) -> pd.DataFrame:
        """
        Simplify the logic of extract_features.py for a demo batch of events.
        """
        df = pd.DataFrame(events)
        if df.empty:
            return pd.DataFrame()

        features = {}
        
        # Logon
        logons = df[df["event_type"] == "logon"]
        features["n_logon"] = len(logons)
        # Simplification: count logons where 'after_hours' might be implied.
        features["n_logon_afterhours"] = len(logons) if len(logons) > 0 else 0
        features["n_logon_weekend"] = 0
        features["n_logon_other_pc"] = 0
        features["n_distinct_pc"] = logons["pc"].nunique() if "pc" in logons else 1
        features["first_logon_hour"] = 8
        features["last_logon_hour"] = 20

        # Device
        devices = df[df["event_type"] == "device"]
        features["n_device_connect"] = 0
        if "activity" in devices.columns:
            features["n_device_connect"] = int((devices["activity"] == "Connect").sum())
        features["n_device_afterhours"] = features["n_device_connect"]
        features["n_device_weekend"] = 0

        # File
        files = df[df["event_type"] == "file"]
        features["n_file_copy"] = len(files)
        # Check if filename ends with exe
        features["n_file_exe"] = 0
        if "filename" in files.columns:
            features["n_file_exe"] = int(files["filename"].str.endswith("exe", na=False).sum())
        features["n_file_doc"] = 0
        features["n_file_zip"] = 0
        features["n_file_afterhours"] = features["n_file_copy"]

        # Email
        emails = df[df["event_type"] == "email"]
        features["n_email"] = len(emails)
        features["n_email_recipients"] = len(emails)
        features["n_email_external"] = 0
        features["email_size_total"] = 0
        features["email_attach_total"] = 0
        features["n_email_afterhours"] = 0

        # HTTP
        https = df[df["event_type"] == "http"]
        features["n_http"] = len(https)
        features["n_http_wikileaks"] = 0
        features["n_http_jobsearch"] = 0
        features["n_http_keylogger"] = 0
        if "url" in https.columns:
            features["n_http_wikileaks"] = int(https["url"].str.contains("wikileaks", na=False, case=False).sum())
            features["n_http_jobsearch"] = int(https["url"].str.contains("indeed|monster|careerbuilder|job", na=False, case=False).sum())
            features["n_http_keylogger"] = int(https["url"].str.contains("keylog", na=False, case=False).sum())
        features["n_http_afterhours"] = features["n_http"]

        # Context
        features["is_itadmin"] = 0
        for p in ["O", "C", "E", "A", "N"]:
            features[p] = 3.0

        row = pd.DataFrame([features])
        
        if self.feature_columns:
            for col in self.feature_columns:
                if col not in row.columns:
                    row[col] = 0.0
            row = row[self.feature_columns]

        return row

    def analyze(self, events: list[dict[str, Any]], user_id: str) -> dict[str, Any]:
        if not self.model:
            return {"error": "Model is not loaded on server."}
            
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

        # Generate timeline string
        timeline_parts = []
        for e in events:
            t = e.get("date", e.get("timestamp", ""))
            action = e.get("activity", e.get("event_type", ""))
            timeline_parts.append(f"{t}: {action}")
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

demo_pipeline = DemoPipeline()
