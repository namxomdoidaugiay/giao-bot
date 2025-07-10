# This script requires 'python-telegram-bot' and 'pandas'
# Make sure to install them with pip in your environment before running:
# pip install python-telegram-bot pandas

import pandas as pd
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = -4706174127

CLOUD_PHAT_URL = 'https://onedrive.live.com/personal/b7aa90cde401f698/_layouts/15/download.aspx?UniqueId=3fde7bdb-cd5e-4c4e-8e41-07821eda0c41'
CLOUD_GIAO_URL = 'https://onedrive.live.com/personal/b7aa90cde401f698/_layouts/15/download.aspx?UniqueId=5f03921e-2f25-491a-bcce-af8d3aa32d40'
CLOUD_LUONG_URL = 'https://onedrive.live.com/personal/b7aa90cde401f698/_layouts/15/download.aspx?UniqueId=8e28fbde-06b3-4071-9fb3-5ff5503a1d2a'

LOCAL_PHAT_FILE = 'Phat 07 2025.xlsx'
LOCAL_GIAO_FILE = 'Giao trong ngày 04 2025.xlsx'
LOCAL_LUONG_FILE = 'Giao hàng 04 2025 3 Sau Lỗi 2.xlsx'

FILE_PHAT = LOCAL_PHAT_FILE if os.path.exists(LOCAL_PHAT_FILE) else CLOUD_PHAT_URL
FILE_GIAO = LOCAL_GIAO_FILE if os.path.exists(LOCAL_GIAO_FILE) else CLOUD_GIAO_URL
FILE_LUONG = LOCAL_LUONG_FILE if os.path.exists(LOCAL_LUONG_FILE) else CLOUD_LUONG_URL

pending = {}
SHEET_GIAO = 'Tổng'
SHEET_CHECKIN = 'checkin'
SHEET_LUONG = 'Data'

def get_dates(file, sheet, column):
    df = pd.read_excel(file, sheet_name=sheet)
    df[column] = pd.to_datetime(df[column], errors='coerce')
    return sorted(df[column].dropna().dt.date.unique(), reverse=True)[:7]

def send_luong(year, month, ky, context):
    df = pd.read_excel(FILE_LUONG, sheet_name=SHEET_LUONG)
    df = df[(df["Năm"] == year) & (df["Tháng"].astype(str) == str(month)) & (df["Kỳ"].astype(str) == str(ky))]
    df = df[pd.to_numeric(df["Lương/Ngày"], errors="coerce") < 300000]
    if df.empty:
        context.bot.send_message(chat_id=CHAT_ID, text="✅ Không có nhân viên nào dưới 300K.")
        return

    dmin = pd.to_datetime(df["Ngay"], errors="coerce").min().strftime('%d/%m/%Y')
    dmax = pd.to_datetime(df["Ngay"], errors="coerce").max().strftime('%d/%m/%Y')

    msg_lines = [f"📉 Nhân viên lương < 300K ({dmin} → {dmax})"]
    for _, r in df.iterrows():
        msg_lines.append(
            f"📍 Bưu cục: {r['Bưu cục']}\n"
            f"👤 Nhân viên: {r['NhanVien']}\n"
            f"📦 Gán: {r['TongDon']}, GTC: {r['TongDonGTC']}, %GTC: {r['%GTC']}\n"
            f"💰 Lương/ngày: {r['Lương/Ngày']} đ\n"
            f"📆 Thâm niên: {r['Thân Niên Ngày']} ngày"
        )

    messages = []
    current = ""
    for line in msg_lines:
        if len(current + line) > 3900:
            messages.append(current)
            current = ""
        current += line + "\n"

    if current:
        messages.append(current)

    for m in messages:
        context.bot.send_message(chat_id=CHAT_ID, text=m)

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data

    if data == "choose_date":
        days = get_dates(FILE_GIAO, SHEET_GIAO, "Time")
        btns = [[InlineKeyboardButton(d.strftime('%d/%m/%Y'), callback_data=f"giao_{d}")] for d in days]
        query.message.reply_text("📆 Chọn ngày:", reply_markup=InlineKeyboardMarkup(btns))

    elif data == "choose_phat":
        days = get_dates(FILE_PHAT, 0, "Ngày")
        btns = [[InlineKeyboardButton(d.strftime('%d/%m/%Y'), callback_data=f"phat_{d}")] for d in days]
        query.message.reply_text("📆 Chọn ngày:", reply_markup=InlineKeyboardMarkup(btns))

    elif data == "choose_checkin":
        days = get_dates(FILE_PHAT, SHEET_CHECKIN, "Ngày")
        btns = [[InlineKeyboardButton(d.strftime('%d/%m/%Y'), callback_data=f"checkin_{d}")] for d in days]
        query.message.reply_text("📆 Chọn ngày:", reply_markup=InlineKeyboardMarkup(btns))

    elif data == "low_salary":
        df = pd.read_excel(FILE_LUONG, sheet_name=SHEET_LUONG)
        years = sorted(df["Năm"].dropna().unique())
        btns = [[InlineKeyboardButton(str(y), callback_data=f"year_{y}")] for y in years]
        query.message.reply_text("📆 Chọn năm:", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("year_"):
        pending["year"] = int(data.replace("year_", ""))
        df = pd.read_excel(FILE_LUONG, sheet_name=SHEET_LUONG)
        months = sorted(df[df["Năm"] == pending["year"]]["Tháng"].dropna().unique())
        btns = []
        for m in months:
            if not pd.isna(m):
                month_num = int(float(str(m).split("/")[0]))
                btns.append([InlineKeyboardButton(str(month_num), callback_data=f"month_{month_num}")])
        query.message.reply_text("📆 Chọn tháng:", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("month_"):
        month_val = data.replace("month_", "")
        if not month_val.isdigit():
            query.message.reply_text("❌ Dữ liệu tháng không hợp lệ: " + month_val)
            return
        pending["month"] = month_val.zfill(2) + "/" + str(pending["year"])
        df = pd.read_excel(FILE_LUONG, sheet_name=SHEET_LUONG)
        if "Kỳ" not in df.columns:
            query.message.reply_text("❌ Không tìm thấy cột 'Kỳ' trong dữ liệu.")
            return
        df = df[(df["Năm"] == pending["year"]) & (df["Tháng"].astype(str) == pending["month"])]
        periods = sorted(df["Kỳ"].dropna().unique())
        if not periods:
            query.message.reply_text("❌ Không tìm thấy kỳ nào phù hợp.")
            return
        btns = [[InlineKeyboardButton(str(k), callback_data=f"ky_{k}")] for k in periods]
        query.message.reply_text("📆 Chọn kỳ:", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("ky_"):
        ky = data.replace("ky_", "")
        send_luong(pending["year"], pending["month"], ky, context)

def start(update: Update, context: CallbackContext):
    buttons = [
        [InlineKeyboardButton("📤 %GTC BC", callback_data="choose_date")],
        [InlineKeyboardButton("⚠️ Gửi phạt", callback_data="choose_phat")],
        [InlineKeyboardButton("📍 Checkin", callback_data="choose_checkin")],
        [InlineKeyboardButton("📉 Nhân viên lương < 300K", callback_data="low_salary")]
    ]
    update.message.reply_text("📌 Chọn hành động:", reply_markup=InlineKeyboardMarkup(buttons))

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    updater.start_polling()
    print("🤖 Bot đang chạy... Gửi /start trong nhóm để sử dụng.")
    updater.idle()

if __name__ == "__main__":
    main()
