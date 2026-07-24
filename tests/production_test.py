import urllib.request
import urllib.parse
import json
import uuid

BASE_URL = "https://organic-marketing-ai1.onrender.com"

def test_health():
    print("Testing /health...")
    req = urllib.request.Request(f"{BASE_URL}/health")
    with urllib.request.urlopen(req) as response:
        print(f"Status: {response.status}")
        print(response.read().decode())
        assert response.status == 200

def test_public_stats():
    print("Testing /api/public/stats...")
    req = urllib.request.Request(f"{BASE_URL}/api/public/stats")
    with urllib.request.urlopen(req) as response:
        print(f"Status: {response.status}")
        print(response.read().decode())
        assert response.status == 200

def test_register_and_login():
    print("Testing registration and login...")
    test_email = f"test_{uuid.uuid4()}@example.com"
    test_password = "password123"

    # Register
    data = json.dumps({
        "email": test_email,
        "password": test_password,
        "name": "Test User"
    }).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/register", data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            print("Register response:", res)
            assert res.get("success") == True
    except urllib.error.HTTPError as e:
        print("Registration failed:", e.read().decode())
        return

    # Login
    login_data = json.dumps({
        "email": test_email,
        "password": test_password
    }).encode('utf-8')
    req_login = urllib.request.Request(f"{BASE_URL}/api/v1/auth/login", data=login_data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req_login) as response:
            res = json.loads(response.read().decode())
            print("Login response:", res)
            assert res.get("success") == True
            token = res.get("token")
            
            # Fetch /me
            req_me = urllib.request.Request(f"{BASE_URL}/api/v1/users/me", headers={'Authorization': f'Bearer {token}'})
            with urllib.request.urlopen(req_me) as response_me:
                res_me = json.loads(response_me.read().decode())
                assert "id" in res_me
            return token
    except urllib.error.HTTPError as e:
        print("Login/Me failed:", e.read().decode())
        return None

def test_marketing_automation(token: str):
    print("Testing manual marketing triggers...")
    
    # 1. Update business profile to trigger brand analysis
    print("Triggering brand analysis...")
    profile_data = json.dumps({
        "name": "Test Automation Business",
        "description": "We sell high quality automation software",
        "websiteUrl": "https://example.com"
    }).encode('utf-8')
    req_profile = urllib.request.Request(
        f"{BASE_URL}/api/v1/users/me/business-profile",
        data=profile_data,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req_profile) as response:
            res = json.loads(response.read().decode())
            print("Profile update response:", res)
    except urllib.error.HTTPError as e:
        print("Profile update failed:", e.read().decode())

    # Wait for background brand analysis to complete by polling
    import time
    print("Polling for AI brand analysis to complete...")
    max_retries = 15
    analysis_complete = False
    for i in range(max_retries):
        req_me = urllib.request.Request(
            f"{BASE_URL}/api/v1/users/me/onboarding-status",
            headers={'Authorization': f'Bearer {token}'}
        )
        try:
            with urllib.request.urlopen(req_me) as response:
                status_res = json.loads(response.read().decode())
                if status_res.get("brandAnalysisComplete") == True:
                    analysis_complete = True
                    print(f"Brand analysis completed after {i*5} seconds!")
                    print("Waiting 20 seconds for starter campaigns to be generated & saved...")
                    time.sleep(20)
                    break
        except Exception:
            pass
        print("Waiting...")
        time.sleep(5)
    
    if not analysis_complete:
        print("WARNING: Brand analysis did not complete within time limit (likely missing LLM keys on server). Marketing loop may skip this workspace.")

    # 2. Trigger social post
    print("Triggering social post...")
    req_trigger = urllib.request.Request(
        f"{BASE_URL}/api/v1/social/trigger",
        data=b"{}",
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req_trigger) as response:
            res = json.loads(response.read().decode())
            print("Social Trigger response:", res)
            assert res.get("success") == True
    except urllib.error.HTTPError as e:
        print("Social trigger failed:", e.read().decode())

    # Check recent posts
    req_recent = urllib.request.Request(
        f"{BASE_URL}/api/v1/social/recent-posts",
        headers={'Authorization': f'Bearer {token}'}
    )
    try:
        with urllib.request.urlopen(req_recent) as response:
            res = json.loads(response.read().decode())
            print("Recent posts:", res)
    except urllib.error.HTTPError as e:
        print("Recent posts failed:", e.read().decode())

def run_tests():
    test_health()
    test_public_stats()
    token = test_register_and_login()
    if token:
        test_marketing_automation(token)
    print("All basic tests completed.")

if __name__ == "__main__":
    run_tests()
