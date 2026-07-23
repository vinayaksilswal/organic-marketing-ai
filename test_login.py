import urllib.request
import urllib.error
import json

base_url = "https://organic-marketing-ai1.onrender.com/api/v1"

# Try login
try:
    req = urllib.request.Request(
        f"{base_url}/auth/login",
        data=json.dumps({"email": "vinayaksilswal@gmail.com", "password": "password"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as response:
        login_res = json.loads(response.read().decode())
        print("Login Success:", login_res)
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
