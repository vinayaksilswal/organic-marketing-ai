import urllib.request
import json
import ssl

def run_test():
    base_url = "https://organic-marketing-ai1.onrender.com/api/v1"
    
    # Login
    print("Logging in...")
    req = urllib.request.Request(
        f"{base_url}/auth/login",
        data=b'{"email":"vinayaksilswal@gmail.com","password":"12345678"}',
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            res_data = json.loads(response.read().decode())
            token = res_data.get("token")
            print("Login token received.")
            
            endpoints = [
                "/social/recent-posts",
                "/social/scheduler-status",
                "/marketing/media",
                "/creatives/queue",
                "/campaigns",
                "/marketing/logs",
                "/marketing/emails",
                "/marketing/audiences",
                "/marketing/posts"
            ]
            
            for endpoint in endpoints:
                print(f"Fetching GET {endpoint}...")
                req_ep = urllib.request.Request(
                    f"{base_url}{endpoint}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                try:
                    with urllib.request.urlopen(req_ep, context=ctx) as resp:
                        data = json.loads(resp.read().decode())
                        print(f"Success {endpoint}: {data.get('success')}")
                except urllib.error.HTTPError as e:
                    print(f"HTTPError {endpoint}: {e.code}")
                    print(e.read().decode())
                    
    except urllib.error.HTTPError as e:
        print(f"Login HTTPError: {e.code}")
        print(e.read().decode())

run_test()
