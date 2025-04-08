import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

# 放你的 JSON 檔案路徑
with open('analog-marking-456108-f1-b9133a6bbffb.json') as f:
    creds_dict = json.load(f)

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# 這裡可以測試連線是否成功
sheet = client.open("享受健身俱樂部").sheet1
print(sheet.get_all_records())
