from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Resource, Api
from flask_httpauth import HTTPBasicAuth

app = Flask(__name__)
api = Api(app, prefix="/api/v1")
auth = HTTPBasicAuth()

USER_DATA = {
    "admin": "admin"
}


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


@app.route('/endpoint', methods=['POST'])
@auth.login_required
def endpoint():
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
    return jsonify(response)


@app.route('/get_alarm', methods=['GET'])
@auth.login_required
def get_alarm():
    alarms = Alarm.query.all()
    alarm_list = []
    for alarm in alarms:
        alarm_list.append({'index': alarm.index, 'time': alarm.time, 'state': alarm.state})
    return jsonify(alarm_list)


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
