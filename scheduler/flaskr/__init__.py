"""Master job server"""
import os

from flask import Flask, request, current_app, jsonify

from . import db

def add_endpoints(app):
    @app.route('/start_split_job')
    def start_split_job():
        """Get a job id and mark it as "running" in the DB
        returns: a job JSON file"""
        c = db.get_db().cursor()
        states = db.acc_states()

        c.execute('BEGIN')
        # get an item where state = new and update its state
        c.execute('SELECT * FROM acc WHERE acc_state_id = ? LIMIT 1',
                  [states['new']])
        job = c.fetchone()
        if job is None:
            return jsonify({'action': 'shutdown'})

        # There's something left.
        c.execute('''UPDATE acc SET acc_state_id = ?
                     WHERE acc_id = ?''', (states['splitting'], job['acc_id']))

        # Stop transaction
        c.execute('COMMIT')

        response = dict(job)
        response['action'] = 'process'

        # Send the response as JSON
        return jsonify(response)

    @app.route('/finish_split_job')
    def finish_split_job():
        job_id = request.args.get('job_id')
        status = request.args.get('status')

        state_ids = db.acc_states()

        if status not in ('new', 'split_err', 'split_done'):
            raise ValueError()

        c = db.get_db().cursor()
        c.execute('''UPDATE acc SET acc_state_id = ?''', [state_ids[status]])

        return jsonify('success')

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite')
    )

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    add_endpoints(app)

    db.init_app(app)
    return app
