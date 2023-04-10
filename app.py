import json

import paho.mqtt.client as mqtt
from flask import Flask, request, jsonify
from flask_httpauth import HTTPBasicAuth
from flask_restful import Api
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
api = Api(app, prefix="/api/v1")
auth = HTTPBasicAuth()

USER_DATA = {
    "admin": "admin"
}

broker_address = "test.mosquitto.org"
port = 1883


def on_disconnect(client, userdata, rc):
    if rc != 0:
        client.reconnect()


client = mqtt.Client()
client.on_disconnect = on_disconnect
client._reconnect_on_failure = True


# Connect to MQTT broker
# client.connect(broker_address, port, 60)
client.connect_async(broker_address, port, 60)


@auth.verify_password
def verify(username, password):
    if not (username and password):
        return False
    return USER_DATA.get(username) == password


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///iotalarmapp.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
app.app_context().push()


class Alarm(db.Model):
    index = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(10))
    state = db.Column(db.Boolean)

    def __init__(self, index, time, state):
        self.index = index
        self.time = time
        self.state = state

    def __repr__(self):
        return '<Alarm %r>' % self.index


@app.route('/set_alarm', methods=['POST'])
@auth.login_required
def set_alarm():
    json_data = request.get_json()
    # delete all rows in the database and add json_data to the database
    Alarm.query.delete()
    if json_data is not None:
        for alarm in json_data:
            db.session.add(Alarm(alarm['index'], alarm['time'], alarm['state']))
        db.session.commit()
    else:
        #   delete the row with an index of 0
        Alarm.query.delete()

    response = {
        'status': 'success',
        'message': 'JSON data received'
    }
    publish_data(json_data)
    return jsonify(response)


@app.route('/get_alarm', methods=['GET'])
@auth.login_required
def get_alarm():
    alarms = Alarm.query.all()
    alarm_list = []
    for alarm in alarms:
        alarm_list.append({'index': alarm.index, 'time': alarm.time, 'state': alarm.state})
    return jsonify(alarm_list)


def publish_data(data):
    payload = str(json.dumps(data)).encode() + b'\n'
    # send the payload in chunks of 255 bytes
    topic = "esp/alarm"
    client.loop_start()
    for i in range(0, len(payload), 255):
        client.publish(topic, payload[i:i + 255])
    client.loop_stop()



if __name__ == '__main__':
    # Start Flask application
    app.run(debug=False, host='0.0.0.0', port=5000)
