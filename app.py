from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import mipsp  # Asegúrate de tener tu SDK real
import os

# Configuración de Flask
app = Flask(_name_)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pagos.db'  # Puedes cambiarlo por PostgreSQL o MySQL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar DB
db = SQLAlchemy(app)

# Modelo de orden de pago
class OrdenPago(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    orden_id_psp = db.Column(db.String(100), unique=True, nullable=False)
    descripcion = db.Column(db.String(255))
    monto = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(50), default='PENDIENTE')
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

# Inicializar base de datos
with app.app_context():
    db.create_all()

# Variables de entorno para credenciales
PSP_API_KEY = os.environ.get("PSP_API_KEY", "TU_API_KEY")
PSP_SECRET_KEY = os.environ.get("PSP_SECRET_KEY", "TU_SECRET_KEY")
psp_client = mipsp.Cliente(PSP_API_KEY, PSP_SECRET_KEY)

@app.route('/api/crear-orden-pago', methods=['POST'])
def crear_orden_pago():
    data = request.get_json()
    monto = data.get('monto')
    descripcion = data.get('descripcion', 'Pago de matrícula')

    if not monto or not isinstance(monto, (int, float)):
        return jsonify({'error': 'Monto inválido'}), 400

    try:
        orden = psp_client.crear_orden({
            'monto': monto,
            'descripcion': descripcion,
            'return_url': 'https://tu-sitio.com/confirmacion-pago',
            'webhook_url': 'https://tu-sitio.com/api/webhook-pago'
        })

        nueva_orden = OrdenPago(
            orden_id_psp=orden['id'],
            descripcion=descripcion,
            monto=monto
        )
        db.session.add(nueva_orden)
        db.session.commit()

        return jsonify({'orden_id': orden['id'], 'url_redireccion': orden.get('url_redireccion')}), 200
    except mipsp.Error as e:
        return jsonify({'error': str(e)}), 400

@app.route('/confirmacion-pago')
def confirmacion_pago():
    transaction_id = request.args.get('transaction_id')

    try:
        transaccion = psp_client.obtener_transaccion(transaction_id)
        if transaccion['estado'] == 'APROBADO':
            orden = OrdenPago.query.filter_by(orden_id_psp=transaction_id).first()
            if orden:
                orden.estado = 'APROBADO'
                db.session.commit()
            return "¡Pago exitoso! Gracias por tu matrícula."
        else:
            return "El pago no fue aprobado."
    except mipsp.Error as e:
        return f"Error al verificar el pago: {e}"

@app.route('/api/webhook-pago', methods=['POST'])
def webhook_pago():
    data = request.get_json()
    if psp_client.verificar_firma_webhook(request.headers, request.get_data()):
        transaction_id = data.get('id')
        status = data.get('status')

        orden = OrdenPago.query.filter_by(orden_id_psp=transaction_id).first()
        if orden:
            orden.estado = status
            db.session.commit()

        print(f"Webhook recibido para la transacción {transaction_id}: {status}")
        return jsonify({'status': 'OK'}), 200
    else:
        return jsonify({'error': 'Firma inválida'}), 400

if _name_ == '_main_':
    app.run(debug=True)