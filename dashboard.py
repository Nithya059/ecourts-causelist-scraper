import json

# Load JSON summary
with open('cause_list_summary_2025-10-18_130458.json', 'r') as f:
    data = json.load(f)

# Display dashboard
print("Court Cause List Dashboard")
print("==========================")
print("PDF File Name:", data['file'])
print("Status:", data['status'])
print("Generated At:", data['timestamp'])
