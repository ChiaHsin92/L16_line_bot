from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage,
    ButtonsTemplate, MessageAction
)
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import tempfile
import sys
import logging
import re

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
line_handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
user_states = {}

def get_gspread_client():
    credentials_content = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_CONTENT")
    if not credentials_content:
        logger.error("缺少 GOOGLE_APPLICATION_CREDENTIALS_CONTENT 環境變數")
        raise ValueError("環境變數未設定")
    try:
        with tempfile.NamedTemporaryFile(mode="w+", delete=True, suffix=".json") as temp_file:
            temp_file.write(credentials_content)
            temp_file.flush()
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_name(temp_file.name, scope)
            client = gspread.authorize(creds)
            return client
    except Exception as e:
        logger.error(f"Google Sheets 授權錯誤：{e}", exc_info=True)
        sys.exit(1)

@app.route("/")
def home():
    return "LINE Bot 正常運作中！"

@app.route("/webhook", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@line_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_msg = event.message.text.strip()
    logger.info(f"使用者 {user_id} 傳送訊息：{user_msg}")

    try:
        if user_msg == "會員專區":
            template = TemplateSendMessage(
                alt_text="會員功能選單",
                template=ButtonsTemplate(
                    title="會員專區",
                    text="請選擇功能",
                    actions=[
                        MessageAction(label="查詢會員資料", text="查詢會員資料")
                    ]
                )
            )
            line_bot_api.reply_message(event.reply_token, template)

        elif user_msg == "查詢會員資料":
            user_states[user_id] = "awaiting_member_id"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="請輸入您的會員編號：")
            )

        elif user_states.get(user_id) == "awaiting_member_id":
            member_id = re.sub(r"\D", "", user_msg)
            user_states.pop(user_id)

            try:
                client = get_gspread_client()
                spreadsheet_id = "1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg"
                sheet = client.open_by_key(spreadsheet_id).worksheet("會員資料")
                records = sheet.get_all_records()

                member_data = next(
                    (row for row in records if re.sub(r"\D", "", str(row["姓名"])) == member_id),
                    None
                )

                if member_data:
                    reply_text = (
                        f"✅ 查詢成功\n"
                        f"姓名：{member_data['姓名']}\n"
                        f"電話：{member_data['電話']}\n"
                        f"會員類型：{member_data['會員類型']}\n"
                        f"會員狀態：{member_data['會員狀態']}\n"
                        f"會員點數：{member_data['會員點數']}\n"
                        f"會員到期日：{member_data['會員到期日']}"
                    )
                else:
                    reply_text = "❌ 查無此會員編號，請確認後再試一次。"

            except Exception as e:
                reply_text = f"❌ 查詢失敗：{str(e)}"
                logger.error(f"查詢會員資料失敗：{e}", exc_info=True)

            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

    except Exception as e:
        logger.error(f"處理訊息錯誤：{e}", exc_info=True)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"❌ 發生錯誤：{str(e)}"))

if __name__ == "__main__":
    app.run()
