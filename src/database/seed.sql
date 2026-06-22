INSERT INTO users (id, username, role, email, department, risk_score)
VALUES
    ('u-demo-001', 'demo.analyst', 'analyst', 'analyst@example.com', 'Security', 12),
    ('u-demo-002', 'demo.admin', 'admin', 'admin@example.com', 'Security', 5)
ON CONFLICT (id) DO NOTHING;

INSERT INTO logs (user_id, event_type, timestamp, source_ip, device, action, raw_payload)
VALUES
    ('u-demo-001', 'logon', now(), '10.0.0.10', 'workstation-01', 'login_success', '{"source":"seed"}'::jsonb)
ON CONFLICT DO NOTHING;
