from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, CarouselColumn,
                           CarouselTemplate, MessageAction, URIAction, ImageCarouselColumn, ImageCarouselTemplate,
                           ImageSendMessage, ButtonsTemplate, ConfirmTemplate)
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import tempfile  # 引入 tempfile

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
line_handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 用來追蹤每位用戶的狀態
user_states = {}

def get_gspread_client():
    """
    使用環境變數中的憑證來獲取 gspread Client。
    """
    credentials_content = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_CONTENT")
    if not credentials_content:
        raise ValueError(
            "GOOGLE_APPLICATION_CREDENTIALS_CONTENT 環境變數未設定。"
        )

    try:
        # 將憑證內容寫入臨時檔案
        with tempfile.NamedTemporaryFile(mode='w+', delete=True, suffix='.json') as temp_file:
            temp_file.write(credentials_content)
            temp_file.flush()  # 確保內容寫入

            # 設定 GOOGLE_APPLICATION_CREDENTIALS 環境變數
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_file.name
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(temp_file.name, scope)
            client = gspread.authorize(creds)
            return client
    except Exception as e:
        print(f"Error authorizing with Google Sheets: {e}")
        sys.exit(1)

@app.route('/')
def home():
    return 'Hello, LINE Bot 正常運行中！'

@app.route("/webhook", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@line_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_msg = event.message.text

    if user_msg == '會員專區':
        buttons_template = TemplateSendMessage(
            alt_text='會員福利選單',
            template=ButtonsTemplate(
                title='會員專區',
                text='請選擇功能',
                actions=[
                    MessageAction(
                        label='查詢會員資料',
                        text='查詢會員資料')
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)

    elif user_msg == '查詢會員資料':
        user_states[user_id] = 'awaiting_member_id'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='請輸入您的會員編號：'))
      
    elif user_states.get(user_id) == 'awaiting_member_id':
        member_id = user_msg.strip()
        user_states.pop(user_id)
        logger.info(f"Searching for member ID: {member_id}")
    
        try:
            client = get_gspread_client()
            sheet = client.open("享瘦健身俱樂部").worksheet("會員資料")
            records = sheet.get_all_records()
    
            # 使用正則表達式提取數字部分並移除空格
            member_data = next((row for row in records if re.sub(r'\D', '', str(row['會員ID'])) == member_id), None)
            if member_data:
                reply_text = f"✅ 查詢成功\n姓名：{member_data['姓名']}\n會員類型：{member_data['會員類型']}\n會員點數：{member_data['會員點數']}\n會員到期日：{member_data['會員到期日']}"
                logger.info(f"Found member data: {member_data}")
            else:
                reply_text = '❌ 查無此會員編號，請確認後再試一次。'
                logger.info("Member data not found")
    
        except Exception as e:
            reply_text = f"❌ 查詢失敗：{str(e)}"
            logger.error(f"Error during data retrieval: {e}", exc_info=True)
    
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

if __name__ == "__main__":
    app.run()
