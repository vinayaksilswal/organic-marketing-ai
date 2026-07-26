import urllib.request
import urllib.error
import json
import time
import random

base_url = "https://organic-marketing-ai1.onrender.com/api/v1"
rand_email = f"test_{random.randint(1000,9999)}@example.com"
password = "password123"

print(f"Registering {rand_email}...")
try:
    req = urllib.request.Request(
        f"{base_url}/auth/register",
        data=json.dumps({"email": rand_email, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as response:
        login_res = json.loads(response.read().decode())
        print("Register Success:", login_res)
        token = login_res.get("token")
        
        if token:
            print("Fetching /users/me...")
            req_me = urllib.request.Request(
                f"{base_url}/users/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            with urllib.request.urlopen(req_me) as response_me:
                me_res = json.loads(response_me.read().decode())
                print("Me Success:", me_res)
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code}")
    print(e.read().decode())
except Exception as e:
    print("Error:", e)
