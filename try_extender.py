import os
import string
import requests
import urllib

from flask import Flask, request, jsonify, redirect, abort, session, render_template

from mozci.mozci import trigger_job
from mozci import query_jobs
from mozci.sources import buildjson
from mozci.sources.allthethings import list_builders
from mozci.utils.transfer import MEMORY_SAVING_MODE
from revision_info import jobs_per_revision

# Configuring app
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.debug = True
app.secret_key = os.environ.get('TE_KEY')
app.config['SESSION_TYPE'] = 'filesystem'

MEMORY_SAVING_MODE = True
USERS = ['alicescarpa@gmail.com', 'armenzg@mozilla.com']
PORT = os.environ.get('PORT', 8080)


@app.route("/backend/process_data", methods=['POST'])
def process_data():
    email = session.get('email', None)
    if email not in USERS:
        if email is None:
            abort(403, 'Access denied! Please log in first.')
        else:
            abort(403, 'Access denied! You are not in the list of beta users.')
    buildernames = map(urllib.unquote, request.form.keys())
    buildernames.remove('commit')
    commit = request.form['commit']

    assert all(c in string.hexdigits for c in commit)
    for buildername in buildernames:
        assert buildername in list_builders()

    for buildername in buildernames:
        trigger_job(buildername=buildername, revision=commit, dry_run=True)

    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    return jsonify(request.form)


@app.route("/backend/get_json")
def get_json():
    commit = request.args.get('commit')
    if commit is None:
        return redirect('/')

    assert all(c in string.hexdigits for c in commit)
    ret = jobs_per_revision(commit)

    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    return jsonify(ret)


@app.route("/")
def index():
    return render_template('index.html')


# Code from https://github.com/mozilla/browserid-cookbook/
@app.route('/auth/login', methods=["POST"])
def login():
    if 'assertion' not in request.form:
        abort(400)

    assertion_info = {'assertion': request.form['assertion'],
                      'audience': 'localhost:%d' % PORT}  # window.location.host
    resp = requests.post('https://verifier.login.persona.org/verify',
                         data=assertion_info, verify=True)

    if not resp.ok:
        abort(500)

    data = resp.json()

    if data['status'] == 'okay':
        session.update({'email': data['email']})
        return resp.content


@app.route('/auth/logout', methods=["POST"])
def logout():
    session.pop('email', None)
    return redirect('/')


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)
