# This script requires 'python-telegram-bot' and 'pandas'
# Make sure to install them with pip in your environment before running:
# pip install python-telegram-bot pandas

import pandas as pd
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = -4706174127

FILE_GIAO = 'Giao trong ngày 04 2025.xlsx'
FILE_PHAT = 'Phat 07 2025.xlsx'
FILE_LUONG = 'Giao hàng 04 2025 3 Sau Lỗi 2.xlsx'
SHEET_GIAO = 'Tổng'
SHEET_CHECKIN = 'checkin'
SHEET_LUONG = 'Data'

pending = {}

def get_dates(file, sheet, column):
    df = pd.read_excel(file, sheet_name=sheet)
    df[column] = pd.to_datetime(df[column], errors='coerce')
    return sorted(df[column].dropna().dt.date.unique(), reverse=True)[:7]

def send_luong(year, month, ky, context):
    df = pd.read_excel(FILE_LUONG, sheet_name=SHEET_LUONG)
    df = df[
        (df["Năm"] == year) &
        (df["Tháng"].astype(str) == str(month)) &
        (df["Kỳ"].astype(str) == str(ky))
    ]
    df = df[pd.to_numeric(df["Lương/Ngày"], errors="coerce") < 300000]
    if df.empty:
        context.bot.send_message(chat_id=CHAT_ID, text="✅ Không có nhân viên nào dưới 300K.")
        return

    dmin = pd.to_datetime(df["Ngay"], errors="coerce").min().strftime('%d/%m/%Y')
    dmax = pd.to_datetime(df["Ngay"], errors="coerce").max().strftime('%d/%m/%Y')

    msg_lines = [f"📉 Nhân viên lương < 300K ({dmin} → {dmax})"]
    for _, r in df.iterrows():
        line = (
            f"📍 Bưu cục: {r['Bưu cục']}\n"
            f"👤 Nhân viên: {r['NhanVien']}\n"
            f"📦 Gán: {r['TongDon']}, GTC: {r['TongDonGTC']}, %GTC: {r['%GTC']}\n"
            f"💰 Lương/ngày: {r['Lương/Ngày']} đ\n"
            f"📆 Thâm niên: {r['Thân Niên Ngày']} ngày"
        )
        msg_lines.append(line)

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

    elif data.startswith("giao_"):
        d = pd.to_datetime(data.replace("giao_", "")).date()
        msg = generate_giao(d)
        context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

    elif data == "choose_phat":
        days = get_dates(FILE_PHAT, 0, "Ngày")
        btns = [[InlineKeyboardButton(d.strftime('%d/%m/%Y'), callback_data=f"phat_{d}")] for d in days]
        query.message.reply_text("📆 Chọn ngày:", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("phat_"):
        d = pd.to_datetime(data.replace("phat_", "")).date()
        send_phat(d, context)

    elif data == "choose_checkin":
        days = get_dates(FILE_PHAT, SHEET_CHECKIN, "Ngày")
        btns = [[InlineKeyboardButton(d.strftime('%d/%m/%Y'), callback_data=f"checkin_{d}")] for d in days]
        query.message.reply_text("📆 Chọn ngày:", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("checkin_"):
        d = pd.to_datetime(data.replace("checkin_", "")).date()
        send_checkin(d, context)

    elif data == "low_salary":
        df = pd.read_excel(FILE_LUONG, sheet_name=SHEET_LUONG)
        years = sorted(df["Năm"].dropna().unique())
        btns = [[InlineKeyboardButton(str(y), callback_data=f"year_{y}")] for y in years]
        query.message.reply_text("📆 Chọn năm:", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("year_"):
        pending["year"] = int(data.replace("year_", ""))
        df = pd.read_excel(FILE_LUONG, sheet_name=SHEET_LUONG)
        months = sorted(df[df["Năm"] == pending["year"]]["Tháng"].dropna().unique(), key=lambda x: int(str(x).split("/")[0]) if isinstance(x, str) and "/" in x else int(float(x)))
        btns = [[InlineKeyboardButton(str(int(float(str(m).split("/")[0]))), callback_data="month_{}".format(int(float(str(m).split("/")[0]))))] for m in months if not pd.isna(m)]
        query.message.reply_text("📆 Chọn tháng:", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("month_"):
        month_val = data.replace("month_", "")
        if not month_val.isdigit():
            query.message.reply_text("❌ Dữ liệu tháng không hợp lệ: " + month_val)
            return
        pending["month"] = month_val.zfill(2) + "/" + str(pending["year"])

        if "year" not in pending:
            query.message.reply_text("⚠️ Vui lòng chọn năm trước.")
            return

        df = pd.read_excel(FILE_LUONG, sheet_name=SHEET_LUONG)

        if "Kỳ" not in df.columns:
            query.message.reply_text("❌ Không tìm thấy cột 'Kỳ' trong dữ liệu.")
            return

        df = df[df["Năm"] == pending["year"]]
        df = df[df["Tháng"].astype(str) == pending["month"]]

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
