from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta'
# Supondo que a estrutura seja:
# raiz/
#    config/serviceAccountKey.json
#    src/app.py

cred_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'olho-que-tudo-ve-firebase-adminsdk-fbsvc-490517c2ce.json')
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)

# Inicializa o Firestore
db = firestore.client()
veiculos_collection = db.collection('veiculos')
# Página principal – lista de veículos cadastrados
@app.route('/', methods=['GET'])
def index():
    docs = veiculos_collection.stream()
    placas = [doc.to_dict() for doc in docs]
    return render_template('update.html', placas=placas)

# Interface Admin para cadastro/exclusão
@app.route('/admin', methods=['GET'])
def admin():
    docs = veiculos_collection.stream()
    placas = [doc.to_dict() for doc in docs]
    return render_template('admin.html', placas=placas)

# Endpoint para cadastro ou atualização de veículo
@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    placa = request.form['placa'].strip().upper()
    alerta = request.form['alerta'].strip().lower()
    if not placa or not alerta:
        flash('Informe todos os campos!')
        return redirect(url_for('admin'))
    doc_ref = veiculos_collection.document(placa)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.update({'alerta': alerta})
        flash(f'Registro da placa {placa} atualizado com alerta: {alerta}')
    else:
        doc_ref.set({'placa': placa, 'alerta': alerta})
        flash(f'Registro da placa {placa} inserido com alerta: {alerta}')
    return redirect(url_for('admin'))

# Endpoint para exclusão de veículo
@app.route('/excluir/<placa>', methods=['POST'])
def excluir(placa):
    placa = placa.strip().upper()
    doc_ref = veiculos_collection.document(placa)
    if doc_ref.get().exists:
        doc_ref.delete()
        flash(f'Placa {placa} excluída com sucesso.')
    else:
        flash(f'Placa {placa} não encontrada.')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)

# Adiciona um documento de exemplo na coleção "veiculos"
veiculos_collection.document('ABC1234').set({'placa': 'ABC1234', 'alerta': 'furto'})
