import cv2
import pytesseract
import sqlite3
import re
import time
import os
import winsound  # Módulo para emitir som (Windows)

# Configure o caminho, se necessário:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Caminhos
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'database', 'veiculos.db')
# Verifique se o cascade está correto para detectar placas. Se estiver usando um cascade para placas, ajuste o nome do arquivo:
CASCADE_PATH = os.path.join(BASE_DIR, 'data', 'haarcascade_russian_plate_number.xml')
SIREN_SOUND = os.path.join(BASE_DIR, 'data', 'police_siren.wav')  # Arquivo de áudio da sirene

# Garantir que a pasta do banco exista
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Conectar ou criar o banco de dados e a tabela se não existir
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS veiculos (
        placa TEXT PRIMARY KEY,
        alerta TEXT
    )
''')
conn.commit()

def consultar_placa(placa):
    cursor.execute("SELECT alerta FROM veiculos WHERE placa = ?", (placa,))
    resultado = cursor.fetchone()
    return resultado[0] if resultado else None

def cadastrar_placas():
    # Exemplo de placas cadastradas com status de alerta
    dados = [
        ('ABC1234', 'furto'),
        ('DEF5678', 'roubo'),
        ('BRA4E21', 'acao_criminosa'),
        ('FBI-5551', 'furto'),
        ('BRA2E19', 'furto')
    ]
    for placa, alerta in dados:
        try:
            cursor.execute("INSERT INTO veiculos (placa, alerta) VALUES (?, ?)", (placa, alerta))
        except sqlite3.IntegrityError:
            pass
    conn.commit()

cadastrar_placas()

# Inicializar a captura de vídeo
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Erro ao acessar a câmera.")
    exit()

if not os.path.exists(CASCADE_PATH):
    print("Arquivo cascade não encontrado em:", CASCADE_PATH)
    exit()

plate_cascade = cv2.CascadeClassifier(CASCADE_PATH)

# Expressão regular para reconhecer placas antigas e Mercosul
plate_pattern = re.compile(r'([A-Z]{3}[-\s]?[0-9]{4}|[A-Z]{3}[0-9][A-Z][0-9]{2})')

last_plate = None
last_time = 0 
wait_time = 5  # segundos para evitar múltiplos alertas para a mesma placa

# Variáveis para manter o alerta na tela por 10 segundos
current_alert = None
alert_end_time = 0

while True:
    ret, frame = cap.read()
    if not ret:
        print("Falha na captura do frame")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    plates = plate_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 20))
    for (x, y, w, h) in plates:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
        placa_roi = gray[y:y+h, x:x+w]

        # Pré-processamento: aumentar a imagem para melhorar detalhes
        placa_roi_resized = cv2.resize(placa_roi, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
        # Aplicar um desfoque leve para reduzir ruídos
        placa_roi_blurred = cv2.GaussianBlur(placa_roi_resized, (3, 3), 0)
        # Aplicar threshold adaptativo para melhorar o contraste
        placa_roi_thresh = cv2.adaptiveThreshold(placa_roi_blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                 cv2.THRESH_BINARY, 11, 2)

        custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        ocr_text = pytesseract.image_to_string(placa_roi_thresh, config=custom_config)
        print("OCR raw:", ocr_text)

        # Limpar o texto removendo todos os caracteres não alfanuméricos
        ocr_clean = "".join(char for char in ocr_text if char.isalnum()).upper()
        print("OCR cleaned:", ocr_clean)

        # Ajustar a regex para placas antigas (com ou sem hífen) e Mercosul
        match = re.search(r'([A-Z]{3}-?[0-9]{4}|[A-Z]{3}[0-9][A-Z][0-9]{2})', ocr_clean)
        if match:
            placa_encontrada = match.group(1).replace("-", "")
            if placa_encontrada != last_plate or time.time() - last_time > wait_time:
                status = consultar_placa(placa_encontrada)
                if status in ['furto', 'roubo', 'acao_criminosa']:
                    current_alert = f"ALERTA! {status.upper()}: {placa_encontrada}"
                    alert_end_time = time.time() + 10
                    cv2.putText(frame, current_alert, (x, y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                    print(f"ALERTA! Veículo {placa_encontrada} com {status.upper()}")
                    if os.path.exists(SIREN_SOUND):
                        winsound.PlaySound(SIREN_SOUND, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    else:
                        winsound.Beep(1000, 500)
                else:
                    cv2.putText(frame, placa_encontrada, (x, y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                last_plate = placa_encontrada
                last_time = time.time()

    if current_alert and time.time() < alert_end_time:
        cv2.putText(frame, current_alert, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
    else:
        current_alert = None

    cv2.imshow("Leitura de Placas", frame)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC para sair
        break
cap.release()
cv2.destroyAllWindows()
conn.close()