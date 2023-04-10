import json
from threading import Thread

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

ALARM_JSON = [[], []]
counter = 0
json_data = []
most_current = 0


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
    global json_data
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
    # publish the data to the MQTT broker
    Thread(target=detect_change).start()
    return jsonify(response)


def initialize_alarm(alarm_list):
    global json_data
    if alarm_list is not None:
        json_data = alarm_list


@app.route('/get_alarm', methods=['GET'])
@auth.login_required
def get_alarm():
    alarms = Alarm.query.all()
    alarm_list = []
    for alarm in alarms:
        alarm_list.append({'index': alarm.index, 'time': alarm.time, 'state': alarm.state})
    initialize_alarm(alarm_list)
    return jsonify(alarm_list)


@app.route('/get_enabled_alarms', methods=['GET'])
@auth.login_required
def get_enabled_alarms():
    return filter_enabled_alarms(ALARM_JSON[most_current])


def publish_data(data):
    payload = str(json.dumps(data)).encode() + b'\n'
    # send the payload in chunks of 200 bytes
    topic = "esp/alarm"
    client.loop_start()
    for i in range(0, len(payload), 200):
        client.publish(topic, payload[i:i + 200])
    client.loop_stop()


def detect_change():
    global counter, most_current
    if counter == 0:
        ALARM_JSON[0] = json_data
        counter = 1
        most_current = 0
    else:
        ALARM_JSON[1] = json_data
        counter = 0
        most_current = 1

    if ALARM_JSON[0] != ALARM_JSON[1]:
        publish_data(filter_enabled_alarms(ALARM_JSON[most_current]))


def filter_enabled_alarms(alarms):
    enabled_alarms = []
    for alarm in alarms:
        if alarm['state'] is True:
            enabled_alarms.append(alarm['time'])
    return enabled_alarms


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
