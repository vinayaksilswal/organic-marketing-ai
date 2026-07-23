import re

schema_content = open('schema_py.prisma', 'r').read()

models_to_update = [
    'Audience', 'SocialPost', 'EmailCampaign', 'Media', 
    'SocialCampaign', 'MarketingLog', 'EngagementMetrics', 
    'ContentCalendar', 'ABTest', 'DripSequence', 'Product', 'VideoApiConfig'
]

for model in models_to_update:
    # Find the model block
    pattern = r'(model ' + model + r' \{.*?)(\n\})'
    
    # We want to insert right before the closing brace if it doesn't already have businessProfileId
    def repl(m):
        block = m.group(1)
        if 'businessProfileId' not in block:
            insertion = "\n  businessProfileId String?\n  businessProfile   BusinessProfile? @relation(fields: [businessProfileId], references: [id], onDelete: Cascade)"
            return block + insertion + m.group(2)
        return m.group(0)
    
    schema_content = re.sub(pattern, repl, schema_content, flags=re.DOTALL)

# Now we need to add back-relations to BusinessProfile model
bp_pattern = r'(model BusinessProfile \{.*?)(\n\})'
def bp_repl(m):
    block = m.group(1)
    # We want to add all the arrays
    additions = ""
    arrays = {
        'audiences': 'Audience[]',
        'socialPosts': 'SocialPost[]',
        'emailCampaigns': 'EmailCampaign[]',
        'media': 'Media[]',
        'socialCampaigns': 'SocialCampaign[]',
        'marketingLogs': 'MarketingLog[]',
        'engagementMetrics': 'EngagementMetrics[]',
        'contentCalendars': 'ContentCalendar[]',
        'abTests': 'ABTest[]',
        'dripSequences': 'DripSequence[]',
        'products': 'Product[]',
        'videoApiConfigs': 'VideoApiConfig[]'
    }
    for field, type_name in arrays.items():
        if type_name not in block:
            additions += f"\n  {field:<18} {type_name}"
            
    if additions:
        return block + "\n" + additions + m.group(2)
    return m.group(0)
    
schema_content = re.sub(bp_pattern, bp_repl, schema_content, flags=re.DOTALL)

open('schema_py.prisma', 'w').write(schema_content)
print("Updated schema_py.prisma")
