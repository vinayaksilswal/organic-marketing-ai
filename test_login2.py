import urllib.request
import urllib.error
import json

base_url = "https://organic-marketing-ai1.onrender.com/api/v1"

try:
    req = urllib.request.Request(
        f"{base_url}/auth/login",
        data=json.dumps({"email": "vinayaksilswal@gmail.com", "password": "12345678"}).encode("utf-8"),
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
            try:
                with urllib.request.urlopen(req_me) as response_me:
                    me_res = json.loads(response_me.read().decode())
                    print("Me Success:", me_res)
            except urllib.error.HTTPError as e:
                print(f"Me HTTPError: {e.code}")
                print(e.read().decode())
                
            print("Fetching /businesses...")
            req_biz = urllib.request.Request(
                f"{base_url}/businesses",
                headers={"Authorization": f"Bearer {token}"}
            )
            try:
                with urllib.request.urlopen(req_biz) as response_biz:
                    biz_res = json.loads(response_biz.read().decode())
                    print("Businesses Success:", biz_res)
            except urllib.error.HTTPError as e:
                print(f"Businesses HTTPError: {e.code}")
                print(e.read().decode())

            print("Fetching GET /social/recent-posts...")
            req_recent = urllib.request.Request(
                f"{base_url}/social/recent-posts",
                headers={"Authorization": f"Bearer {token}"}
            )
            try:
                with urllib.request.urlopen(req_recent) as response_recent:
                    recent_res = json.loads(response_recent.read().decode())
                    print("Recent Posts Success:", recent_res)
            except urllib.error.HTTPError as e:
                print(f"Recent Posts HTTPError: {e.code}")
                print(e.read().decode())
                
            print("Fetching GET /social/scheduler-status...")
            req_sched = urllib.request.Request(
                f"{base_url}/social/scheduler-status",
                headers={"Authorization": f"Bearer {token}"}
            )
            try:
                with urllib.request.urlopen(req_sched) as response_sched:
                    sched_res = json.loads(response_sched.read().decode())
                    print("Scheduler Status Success:", sched_res)
            except urllib.error.HTTPError as e:
                print(f"Scheduler Status HTTPError: {e.code}")
                print(e.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code}")
    print(e.read().decode())
except Exception as e:
    print("Error:", e)
