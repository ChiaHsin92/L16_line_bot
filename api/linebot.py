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

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
line_handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 用來追蹤每位用戶的狀態
user_states = {}

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

        try:
            # 掛載認證（這裡使用你剛剛上傳的 json 檔案）
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name('analog-marking-456108-f1-b9133a6bbffb.json', scope)
            client = gspread.authorize(creds)

            sheet = client.open("享受健身俱樂部").worksheet("會員資料")
            records = sheet.get_all_records()

            member_data = next((row for row in records if str(row['會員ID']) == member_id), None)
            if member_data:
                reply_text = f"✅ 查詢成功\n姓名：{member_data['姓名']}\n會員類型：{member_data['會員類型']}\n會員點數：{member_data['會員點數']}\n會員到期日：{member_data['會員到期日']}"
            else:
                reply_text = '❌ 查無此會員編號，請確認後再試一次。'

        except Exception as e:
            reply_text = f"❌ 查詢失敗：{str(e)}"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

if __name__ == "__main__":
    app.run()
