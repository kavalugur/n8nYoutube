import json
import re

# Dosyayı oku
with open('My workflow 32.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Node type'larına göre originalName mapping
type_mapping = {
    'n8n-nodes-base.manualTrigger': 'Manual Trigger',
    'n8n-nodes-base.function': 'Function',
    'n8n-nodes-base.httpRequest': 'HTTP Request',
    'n8n-nodes-base.googleDrive': 'Google Drive',
    'n8n-nodes-base.youTube': 'YouTube',
    'n8n-nodes-base.if': 'If',
    'n8n-nodes-base.wait': 'Wait',
    'n8n-nodes-base.set': 'Set',
    'n8n-nodes-base.deepL': 'DeepL',
    'n8n-nodes-base.merge': 'Merge'
}

# Her node'a originalName ekle
for node in data['nodes']:
    if 'originalName' not in node:
        node_type = node.get('type', '')
        original_name = type_mapping.get(node_type, 'Unknown')
        node['originalName'] = original_name
        print(f"Added originalName '{original_name}' to node '{node.get('name', 'Unknown')}'")

# Dosyayı kaydet
with open('My workflow 32.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("\nOriginalName alanları başarıyla eklendi!")