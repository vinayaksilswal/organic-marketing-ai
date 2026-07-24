import re

def refactor():
    with open('routers/marketing.py', 'r') as f:
        content = f.read()

    # Update import
    content = content.replace("AsyncSessionLocal,", "get_tenant_session,")

    def replacer(match):
        indent = match.group(1)
        body = match.group(2)
        # Check if workspace_id is in the body of the async with block
        # We need to extract it to BEFORE the async with block
        
        # Is workspace_id defined inside?
        ws_match = re.search(r'([ \t]*)workspace_id = request\.headers\.get\(([^)]+)\)\n', body)
        if ws_match:
            # Remove it from the body
            body = body.replace(ws_match.group(0), "")
            return f"{indent}workspace_id = request.headers.get({ws_match.group(2)})\n{indent}async with get_tenant_session(workspace_id) as session:\n{body}"
        else:
            # If not defined inside, it might be defined before, or not at all.
            # If not at all, we can fallback to extracting from request if request is available,
            # or just rely on it being defined before.
            # Let's just define it if it's not present before
            return f"{indent}workspace_id = request.headers.get('x-workspace-id') if 'request' in locals() else None\n{indent}async with get_tenant_session(workspace_id) as session:\n{body}"

    # We can match `async with AsyncSessionLocal() as session:` and everything inside it up to the next unindented line
    # Actually, a simpler regex just matching the line itself:
    
    # Just do a manual pass line by line
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'async with AsyncSessionLocal() as session:' in line:
            indent = line[:line.find('async with')]
            # Check lines before and after
            has_ws_before = any('workspace_id =' in lines[j] for j in range(max(0, i-5), i))
            if has_ws_before:
                lines[i] = f"{indent}async with get_tenant_session(workspace_id) as session:"
            else:
                # find it after
                found_after = False
                for j in range(i+1, min(len(lines), i+6)):
                    if 'workspace_id = ' in lines[j]:
                        ws_line = lines[j].strip()
                        lines[i] = f"{indent}{ws_line}\n{indent}async with get_tenant_session(workspace_id) as session:"
                        lines[j] = ""  # remove the line from inside
                        found_after = True
                        break
                if not found_after:
                    lines[i] = f"{indent}workspace_id = request.headers.get('x-workspace-id')\n{indent}async with get_tenant_session(workspace_id) as session:"
                    
    with open('routers/marketing.py', 'w') as f:
        f.write("\n".join(lines).replace("\n\n\n", "\n\n"))

if __name__ == '__main__':
    refactor()
