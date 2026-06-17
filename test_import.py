import requests

def test_import():
    base_url = "http://127.0.0.1:8000/api"
    
    # 1. Login
    print("Logging in...")
    resp = requests.post(f"{base_url}/auth/login", json={"email": "admin@demo.com", "password": "password"})
    if not resp.ok:
        print(f"Login failed: {resp.status_code} {resp.text}")
        return
        
    token = resp.json().get("access_token")
    if not token:
        print("No token received")
        return
        
    # 2. Call import
    print("Calling import...")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{base_url}/datasets/cert-r42/import", headers=headers)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")

if __name__ == "__main__":
    test_import()
