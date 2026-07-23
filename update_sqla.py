import re

content = open('database.py', 'r').read()

models = [
    'Product', 'VideoApiConfig', 'Audience', 'MarketingState', 
    'SocialCampaign', 'SocialPost', 'EmailCampaign', 'Media', 
    'MarketingLog', 'EngagementMetrics', 'ContentCalendar', 'ABTest', 'DripSequence'
]

# We want to add:
# businessProfileId = Column(String, ForeignKey("BusinessProfile.id", ondelete="CASCADE"), nullable=True)
# businessProfile = relationship("BusinessProfile", back_populates="{field}")

# First let's check what models exist in database.py
existing_models = re.findall(r'class (\w+)\(Base\):', content)
print("Existing models:", existing_models)

for model in models:
    if model not in existing_models:
        continue
        
    pattern = r'(class ' + model + r'\(Base\):.*?)(?=class \w+\(Base\):|# ===|$)'
    def repl(m):
        block = m.group(1)
        if 'businessProfileId = Column' not in block:
            # Insert before the last relationship or at the end of the class body
            insertion = f"\n    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)\n    businessProfile = relationship('BusinessProfile', back_populates='{model.lower()}s')\n"
            # Find the last line that belongs to the class
            lines = block.split('\n')
            # insert before the first empty line at the end
            while lines and not lines[-1].strip():
                lines.pop()
            return '\n'.join(lines) + insertion + '\n\n'
        return m.group(0)
    
    content = re.sub(pattern, repl, content, flags=re.DOTALL)

# Add back-relationships to BusinessProfile
bp_pattern = r'(class BusinessProfile\(Base\):.*?)(?=class \w+\(Base\):|# ===|$)'
def bp_repl(m):
    block = m.group(1)
    for model in models:
        if model in existing_models:
            field = f"{model.lower()}s"
            if field not in block:
                # remove any trailing newlines from block, append relationships, add back newlines
                lines = block.split('\n')
                while lines and not lines[-1].strip():
                    lines.pop()
                rel = f"\n    {field} = relationship('{model}', back_populates='businessProfile', cascade='all, delete-orphan')"
                block = '\n'.join(lines) + rel + '\n\n'
    return block

content = re.sub(bp_pattern, bp_repl, content, flags=re.DOTALL)

open('database.py', 'w').write(content)
print("Updated database.py")
