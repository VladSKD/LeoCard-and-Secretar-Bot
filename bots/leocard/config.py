import os
from dotenv import load_dotenv

load_dotenv()

class BotConfig:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.google_root_folder_id = os.getenv("GOOGLE_ROOT_FOLDER_ID")
        self.payment_url = os.getenv("PAYMENT_URL")
        self.admin_chat_id = os.getenv("ADMIN_CHAT_ID")
        self.sample_form_path = "examples/4_Заява_на_отримання_Транспортної_картки_та_згода_на_обробку_3.pdf"
        self.instruction_path = "examples/Інструкція_Леокарт (2) (3) (2) (1).pdf"
        self.persistence_path = "bot_persistence/state.pkl"

    @classmethod
    def from_env(cls):
        return cls()

class GoogleConfig:
    def __init__(self):
        self.credentials_file = "credentials.json"
        self.token_file = "token.json"
        self.credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        self.token_json = os.getenv("GOOGLE_TOKEN_JSON")
        self.parties_root_folder_name = "Матеріали"
        self.party_folder_name_template = "{} партія ({})"
        self.party_spreadsheet_name_template = "Партія {}"
        self.student_folder_name_template = "{} - {}"
        self.main_documents_folder = "Documents"
        self.main_database_sheet = "database"
        self.main_worksheet_name = "Sheet1"
        self.template_spreadsheet_id = os.getenv("TEMPLATE_SPREADSHEET_ID")

class FileNames:
    def __init__(self):
        self.passport_front = "passport_front"
        self.passport_back = "passport_back"
        self.student_id = "student_id"
        self.tax_id = "tax_id"
        self.residency_extract = "residency_extract"
        self.photo_3x4 = "photo_3x4"
        self.form_page_1 = "form_page_1"
        self.form_page_2 = "form_page_2"
        self.payment_receipt = "payment_receipt"

class Messages:
    def __init__(self):
        self.greeting = "Привіт! Я допоможу тобі подати документи на ЛеоКарт. Давай почнемо. Який у тебе рівень освіти?"
        self.ask_assistance = "Тобі потрібна допомога з заповненням заяви, чи ти зробиш це самостійно?"
        self.photo_hint = "Фотографуй чітко, без відблисків, на рівній поверхні."
        self.start_assistance = "Добре, давай заповнимо все разом. Спочатку надішли фото лицьової сторони ID-картки. {photo_hint}"
        self.ask_residency = "Тепер надішли PDF-файл витягу про місце проживання (з Дії)."
        self.ask_politech_email = "Введіть вашу корпоративну пошту (...@lpnu.ua):"
        self.invalid_email = "Це не схоже на пошту Політехніки. Спробуйте ще раз."
        self.ask_phone = "Введіть ваш номер телефону:"
        self.ask_photo_3x4 = "Надішліть ваше фото 3x4 (як на документи, можна селфі на білому фоні)."
        self.renew_card = "Якщо у вас вже був ЛеоКарт, вам потрібно лише продовжити його дію в офісі Львівавтодор. Бот для цього не потрібен."
        self.self_service = ("Ось бланк заяви та інструкція з посиланням на Google-форму.\n"
                              "Заповніть форму за посиланням в інструкції, роздрукуйте заяву та принесіть у профком.")

class Buttons:
    def __init__(self):
        self.bachelor = "Бакалавр"
        self.master = "Магістр"
        self.yes = "Так"
        self.no = "Ні"
        self.help_me = "Допоможи мені"
        self.do_myself = "Зроблю сам"
        self.back = "🔙 Назад"