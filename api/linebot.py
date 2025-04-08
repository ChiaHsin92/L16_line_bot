from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    TemplateSendMessage,
    ButtonsTemplate,
    MessageAction,
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

# 設定日誌記錄
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 從環境變數中獲取 LINE Bot 的憑證
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
        logger.error("GOOGLE_APPLICATION_CREDENTIALS_CONTENT 環境變數未設定。")
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_CONTENT 環境變數未設定。")

    try:
        # 將憑證內容寫入臨時檔案
        with tempfile.NamedTemporaryFile(mode="w+", delete=True, suffix=".json") as temp_file:
            temp_file.write(credentials_content)
            temp_file.flush()  # 確保內容已寫入磁碟
            logger.info(f"Temporary credentials file: {temp_file.name}")

            # 設定 GOOGLE_APPLICATION_CREDENTIALS 環境變數
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_file.name
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                temp_file.name, scope
            )
            client = gspread.authorize(creds)
            return client
    except Exception as e:
        logger.error(f"Error authorizing with Google Sheets: {e}", exc_info=True)
        sys.exit(1)

@app.route("/")
def home():
    return "Hello, LINE Bot 正常運行中！"


@app.route("/webhook", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature error")
        abort(400)
    return "OK"


@line_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_msg = event.message.text
    logger.info(f"User message: {user_msg}, User ID: {user_id}")

    try:
        if user_msg == "會員專區":
            buttons_template = TemplateSendMessage(
                alt_text="會員福利選單",
                template=ButtonsTemplate(
                    title="會員專區",
                    text="請選擇功能",
                    actions=[
                        MessageAction(label="查詢會員資料", text="查詢會員資料")
                    ],
                ),
            )
            line_bot_api.reply_message(event.reply_token, buttons_template)
            logger.info("Sent '會員專區' menu")

        elif user_msg == "查詢會員資料":
            user_states[user_id] = "awaiting_member_id"
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="請輸入您的會員編號：")
            )
            logger.info(f"Sent '請輸入您的會員編號：' to user {user_id}")

        elif user_states.get(user_id) == "awaiting_member_id":
            member_id = user_msg.strip()
            user_states.pop(user_id)
            logger.info(f"Received member ID: {member_id} from user {user_id}")

            try:
                client = get_gspread_client()
                sheet = client.open("享瘦健身俱樂部").worksheet("會員資料")
                records = sheet.get_all_records()

                # 移除會員編號中的非數字字元，並與使用者輸入比對
                member_data = next(
                    (row for row in records if re.sub(r'\D', '', str(row["會員ID"])) == member_id), None
                )
                if member_data:
                    reply_text = (
                        f"✅ 查詢成功\n姓名：{member_data['姓名']}\n"
                        f"會員類型：{member_data['會員類型']}\n"
                        f"會員點數：{member_data['會員點數']}\n"
                        f"會員到期日：{member_data['會員到期日']}"
                    )
                    logger.info(f"Found member data for ID {member_id}: {reply_text}")
                else:
                    reply_text = "❌ 查無此會員編號，請確認後再試一次。"
                    logger.warning(f"Member ID {member_id} not found")

            except Exception as e:
                reply_text = f"❌ 查詢失敗：{str(e)}"
                logger.error(f"Error during member data retrieval: {e}", exc_info=True)

            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            logger.info(f"Sent reply: {reply_text} to user {user_id}")

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text=f"❌ 發生錯誤：{str(e)}")
        )



if __name__ == "__main__":
    app.run()

