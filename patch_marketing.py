import re

with open('routers/marketing.py', 'r') as f:
    content = f.read()

# Add workspace_id check to get_social_posts
post_func_pattern = r'(async def get_social_posts\(request: Request\) -> Any:.*?prisma = request\.app\.state\.prisma)'
def post_repl(m):
    return m.group(1) + """
    workspace_id = request.headers.get("x-workspace-id")
    if not workspace_id:
        return []
"""
content = re.sub(post_func_pattern, post_repl, content, flags=re.DOTALL)

post_find_pattern = r'(posts = await prisma\.socialpost\.find_many\(\n\s*)(order=)'
content = re.sub(post_find_pattern, r'\1where={"businessProfileId": workspace_id},\n        \2', content)

# Add workspace_id check to get_email_campaigns
email_func_pattern = r'(async def get_email_campaigns\(request: Request\) -> Any:.*?prisma = request\.app\.state\.prisma)'
def email_repl(m):
    return m.group(1) + """
    workspace_id = request.headers.get("x-workspace-id")
    if not workspace_id:
        return []
"""
content = re.sub(email_func_pattern, email_repl, content, flags=re.DOTALL)

email_find_pattern = r'(emails = await prisma\.emailcampaign\.find_many\(\n\s*)(order=)'
content = re.sub(email_find_pattern, r'\1where={"businessProfileId": workspace_id},\n        \2', content)

# When creating posts or emails, we should attach businessProfileId, but wait, those endpoints might also need workspace_id!
manual_post_pattern = r'(post = await prisma\.socialpost\.create\(\n\s*data=\{)'
def mp_repl(m):
    return """
    workspace_id = request.headers.get("x-workspace-id")
""" + m.group(1) + """
            "businessProfileId": workspace_id,
"""
content = re.sub(manual_post_pattern, mp_repl, content)

manual_email_pattern = r'(campaign = await prisma\.emailcampaign\.create\(\n\s*data=\{)'
def me_repl(m):
    return """
    workspace_id = request.headers.get("x-workspace-id")
""" + m.group(1) + """
            "businessProfileId": workspace_id,
"""
content = re.sub(manual_email_pattern, me_repl, content)

# For dashboard stats (using SQLAlchemy)
dash_pattern = r'(async def marketing_dashboard\(request: Request\) -> Any:.*?async with AsyncSessionLocal\(\) as session:)'
def dash_repl(m):
    return m.group(1) + """
        workspace_id = request.headers.get("x-workspace-id")
"""
content = re.sub(dash_pattern, dash_repl, content, flags=re.DOTALL)

astmt_pattern = r'(a_stmt = select\(Audience\))'
content = re.sub(astmt_pattern, r'\1.where(Audience.businessProfileId == workspace_id)', content)

mstmt_pattern = r'(m_stmt = select\(MarketingState\))'
content = re.sub(mstmt_pattern, r'\1.where(MarketingState.businessProfileId == workspace_id)', content)

# Create marketing state if not exists, attach businessProfileId
state_create_pattern = r'(state = MarketingState\(userId=first_user\.id)(, autoApprove=data\.autoApprove\))'
def sc_repl(m):
    return """workspace_id = request.headers.get("x-workspace-id")
                    """ + m.group(1) + """, businessProfileId=workspace_id""" + m.group(2)
content = re.sub(state_create_pattern, sc_repl, content)

# auto-approve setting filter
aa_pattern = r'(stmt = select\(MarketingState\))'
content = re.sub(aa_pattern, r'\1.where(MarketingState.businessProfileId == request.headers.get("x-workspace-id"))', content)


with open('routers/marketing.py', 'w') as f:
    f.write(content)

print("Updated routers/marketing.py")
