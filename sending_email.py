import smtplib                                              # Импортируем библиотеку по работе с SMTP
import os                                                   # Функции для работы с операционной системой, не зависящие от используемой операционной системы
import imaplib
import email
import boto3

# Добавляем необходимые подклассы - MIME-типы
import mimetypes                                            # Импорт класса для обработки неизвестных MIME-типов, базирующихся на расширении файла
from email import encoders                                  # Импортируем энкодер
from email.mime.base import MIMEBase                        # Общий тип
from email.mime.text import MIMEText                        # Текст/HTML
from email.mime.image import MIMEImage                      # Изображения
from email.mime.audio import MIMEAudio                      # Аудио
from email.mime.multipart import MIMEMultipart              # Многокомпонентный объект


def read_email(msg_subj, msg_text, files, region_name_, aws_access_key_id_, aws_secret_access_key_, bucket_):
    is_email = 0
    email_from = ['', '']
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login('python.arduino.rfbr@gmail.com', '8635255240')
    mail.select('inbox')
    result, data = mail.search(None, '(HEADER Subject "Need-data")')
    ids = data[0]
    id_list = ids.split()

    if len(id_list) != 0:
        is_email = 1
        latest_email_id = id_list[-1]
        result, data = mail.fetch(latest_email_id, '(RFC822)')
        raw_email = data[0][1]
        email_message = email.message_from_string(raw_email.decode())
        email_from = email.utils.parseaddr(email_message['From'])
        send_email(email_from[1], msg_subj, msg_text, files, region_name_, aws_access_key_id_, aws_secret_access_key_, bucket_)
        mail.store(latest_email_id, '+FLAGS', '\\Deleted')
        mail.expunge()

    result, data = mail.search(None, '(HEADER Subject "softwareupdate")')
    ids = data[0]
    id_list = ids.split()
    if len(id_list) != 0:
        is_email = 2
        latest_email_id = id_list[-1]
        result, data = mail.fetch(latest_email_id, '(RFC822)')
        raw_email = data[0][1]
        email_message = email.message_from_string(raw_email.decode())
        email_from = email.utils.parseaddr(email_message['From'])
        for part in email_message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue
            filename = part.get_filename()
            if not(filename): continue
            fp = open(os.path.join('./python_arduino', filename), 'wb')
            fp.write(part.get_payload(decode=1))
            fp.close
        mail.store(latest_email_id, '+FLAGS', '\\Deleted')
        mail.expunge()
    mail.close()
    mail.logout()
    if (len(email_from) != 0):
        ans = email_from[1]
    else:
        ans = ''
    return is_email, ans

def send_email(addr_to, msg_subj, msg_text, files, region_name_, aws_access_key_id_, aws_secret_access_key_, bucket_):
    addr_from = "python.arduino.rfbr@gmail.com"             # Отправитель
    password  = "8635255240"                                # Пароль

    msg = MIMEMultipart()                                   # Создаем сообщение
    msg['From']    = addr_from                              # Адресат
    msg['To']      = addr_to                                # Получатель
    msg['Subject'] = msg_subj                               # Тема сообщения

    body = msg_text                                         # Текст сообщения
    msg.attach(MIMEText(body, 'plain'))                     # Добавляем в сообщение текст

    process_attachement(msg, files)

    #======== Этот блок настраивается для каждого почтового провайдера отдельно ===============================================
    server = smtplib.SMTP('smtp.gmail.com', 587)            # Создаем объект SMTP
    server.starttls()                                       # Начинаем шифрованный обмен по TLS
    #server.set_debuglevel(True)                            # Включаем режим отладки, если не нужен - можно закомментировать
    server.login(addr_from, password)                       # Получаем доступ
    server.send_message(msg)                                # Отправляем сообщение
    server.quit()                                           # Выходим
    #==========================================================================================================================
    session = boto3.session.Session()
    s3 = session.client(
                        service_name='s3',
                        endpoint_url='https://storage.yandexcloud.net',
                        region_name=region_name_,
                        aws_access_key_id=aws_access_key_id_,
                        aws_secret_access_key=aws_secret_access_key_,)
    # Загрузить объекты в бакет
    ## Из файла
    for f in files:
        if (f.split('_')[0] == 'log'):
            try:
                forDeletion = [{'Key':'logs/'+f}]
                response = s3.delete_objects(Bucket=bucket_, Delete={'Objects': forDeletion})
            except Exception as e:
                pass
            s3.upload_file(f, bucket_, 'logs/'+f)
        else:
            try:
                forDeletion = [{'Key':'data/'+f}]
                response = s3.delete_objects(Bucket=bucket_, Delete={'Objects': forDeletion})
            except Exception as e:
                pass
            s3.upload_file(f, bucket_, 'data/'+f)



def process_attachement(msg, files):                        # Функция по обработке списка, добавляемых к сообщению файлов
    for f in files:
        if os.path.isfile(f):                               # Если файл существует
            try:
                attach_file(msg,f)                          # Добавляем файл к сообщению
            except Exception as e:
                pass
        elif os.path.exists(f):                             # Если путь не файл и существует, значит - папка
            dir = os.listdir(f)                             # Получаем список файлов в папке
            for file in dir:                                # Перебираем все файлы и...
                attach_file(msg,f+"/"+file)                 # ...добавляем каждый файл к сообщению

def attach_file(msg, filepath):                             # Функция по добавлению конкретного файла к сообщению
    filename = os.path.basename(filepath)                   # Получаем только имя файла
    ctype, encoding = mimetypes.guess_type(filepath)        # Определяем тип файла на основе его расширения
    if ctype is None or encoding is not None:               # Если тип файла не определяется
        ctype = 'application/octet-stream'                  # Будем использовать общий тип
    maintype, subtype = ctype.split('/', 1)                 # Получаем тип и подтип
    if maintype == 'text':                                  # Если текстовый файл
        with open(filepath) as fp:                          # Открываем файл для чтения
            file = MIMEText(fp.read(), _subtype=subtype)    # Используем тип MIMEText
            fp.close()                                      # После использования файл обязательно нужно закрыть
    elif maintype == 'image':                               # Если изображение
        with open(filepath, 'rb') as fp:
            file = MIMEImage(fp.read(), _subtype=subtype)
            fp.close()
    elif maintype == 'audio':                               # Если аудио
        with open(filepath, 'rb') as fp:
            file = MIMEAudio(fp.read(), _subtype=subtype)
            fp.close()
    else:                                                   # Неизвестный тип файла
        with open(filepath, 'rb') as fp:
            file = MIMEBase(maintype, subtype)              # Используем общий MIME-тип
            file.set_payload(fp.read())                     # Добавляем содержимое общего типа (полезную нагрузку)
            fp.close()
            encoders.encode_base64(file)                    # Содержимое должно кодироваться как Base64
    file.add_header('Content-Disposition', 'attachment', filename=filename) # Добавляем заголовки
    msg.attach(file)                                        # Присоединяем файл к сообщению


def main():
    # Использование функции send_email()
    '''files = ["test_data0.csv"],                                      # Список файлов, если вложений нет, то files=[]
             "file2_path",                                      
             "dir1_path"]                                       # Если нужно отправить все файлы из заданной папки, нужно указать её
    '''
    files = ["test_data0.csv"]
    addr_to   = "d.v.shaykhutdinov@gmail.com"                                # Получатель
    send_email(addr_to, "Отчет за день", "Уважаемые коллеги! \n См. приложенный файл. \n С уважением,\n Ваша Raspberry Pi", files)

if __name__ == '__main__': #if we run file directly
    main()
