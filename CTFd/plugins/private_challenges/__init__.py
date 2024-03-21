from flask import Blueprint, render_template, request

from CTFd.models import Challenges, db
from CTFd.plugins import bypass_csrf_protection, register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES, BaseChallenge
from CTFd.plugins.private_challenges.decay import DECAY_FUNCTIONS, logarithmic
from CTFd.plugins.migrations import upgrade

from CTFd.utils import get_config, set_config
from CTFd.utils.modes import TEAMS_MODE
from CTFd.utils.decorators import admins_only, authed_only, ratelimit, during_ctf_time_only
from CTFd.utils.user import get_current_user

from os import path
from requests.auth import HTTPBasicAuth

import hashlib
import random
import re
import requests
import string

CONFIG_SERVICE_MANAGER_URL_PROPERTY_NAME = 'service_manager_url'
CONFIG_SERVICE_MANAGER_USERNAME_PROPERTY_NAME = 'service_manager_username'
CONFIG_SERVICE_MANAGER_PASSWORD_PROPERTY_NAME = 'service_manager_password'

PLUGIN_FOLDER_NAME = path.basename(path.dirname(__file__))


class PrivateChallenge(Challenges):
    __mapper_args__ = {"polymorphic_identity": "private"}
    id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    service_name = db.Column(db.String(100))
    initial = db.Column(db.Integer, default=0)
    minimum = db.Column(db.Integer, default=0)
    decay = db.Column(db.Integer, default=0)
    function = db.Column(db.String(32), default="logarithmic")

    def __init__(self, *args, **kwargs):
        super(PrivateChallenge, self).__init__(**kwargs)
        self.value = kwargs["initial"]


class PrivateValueChallenge(BaseChallenge):
    id = "private"  # Unique identifier used to register challenges
    name = "private"  # Name of a challenge type
    templates = (
        {  # Handlebars templates used for each aspect of challenge editing & viewing
            "create": f"/plugins/{PLUGIN_FOLDER_NAME}/assets/create.html",
            "update": f"/plugins/{PLUGIN_FOLDER_NAME}/assets/update.html",
            "view": f"/plugins/{PLUGIN_FOLDER_NAME}/assets/view.html",
        }
    )
    scripts = {  # Scripts that are loaded when a template is loaded
        "create": f"/plugins/{PLUGIN_FOLDER_NAME}/assets/create.js",
        "update": f"/plugins/{PLUGIN_FOLDER_NAME}/assets/update.js",
        "view": f"/plugins/{PLUGIN_FOLDER_NAME}/assets/view.js",
    }
    # Route at which files are accessible. This must be registered using register_plugin_assets_directory()
    route = f"/plugins/{PLUGIN_FOLDER_NAME}/assets/"
    # Blueprint used to access the static_folder directory.
    blueprint = Blueprint(
        "private_challenges",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )
    challenge_model = PrivateChallenge

    @classmethod
    def calculate_value(cls, challenge):
        f = DECAY_FUNCTIONS.get(challenge.function, logarithmic)
        value = f(challenge)

        challenge.value = value
        db.session.commit()
        return challenge

    @classmethod
    def read(cls, challenge):
        """
        This method is in used to access the data of a challenge in a format processable by the front end.

        :param challenge:
        :return: Challenge object, data dictionary to be returned to the user
        """
        challenge = PrivateChallenge.query.filter_by(id=challenge.id).first()
        data = {
            "id": challenge.id,
            "name": challenge.name,
            "value": challenge.value,
            "service_name": challenge.service_name,
            "initial": challenge.initial,
            "decay": challenge.decay,
            "minimum": challenge.minimum,
            "description": challenge.description,
            "connection_info": challenge.connection_info,
            "next_id": challenge.next_id,
            "category": challenge.category,
            "state": challenge.state,
            "max_attempts": challenge.max_attempts,
            "type": challenge.type,
            "type_data": {
                "id": cls.id,
                "name": cls.name,
                "templates": cls.templates,
                "scripts": cls.scripts,
            },
        }
        return data

    @classmethod
    def update(cls, challenge, request):
        """
        This method is used to update the information associated with a challenge. This should be kept strictly to the
        Challenges table and any child tables.

        :param challenge:
        :param request:
        :return:
        """
        data = request.form or request.get_json()

        for attr, value in data.items():
            # We need to set these to floats so that the next operations don't operate on strings
            if attr in ("initial", "minimum", "decay"):
                value = float(value)
            setattr(challenge, attr, value)

        return PrivateValueChallenge.calculate_value(challenge)

    @classmethod
    def solve(cls, user, team, challenge, request):
        super().solve(user, team, challenge, request)

        PrivateValueChallenge.calculate_value(challenge)


def get_unique_chal_id(chal_owner_id):
    """
    Given a chal_owner_id, generate a deterministic but reasonably-unguessable
    unique string that can be included as part of the challenge
    domain/service name.  Can only contain lowercase alphanumerics.
    """

    # at least one way to turn a secret string into a secret number
    secret = get_config(CONFIG_SERVICE_MANAGER_PASSWORD_PROPERTY_NAME)
    m = hashlib.sha256()
    m.update(secret.encode('utf8'))
    secret_number = int(m.hexdigest(), 16)

    # ensure other threads don't bother us
    local_random = random.Random()
    local_random.seed(chal_owner_id * secret_number)
    unique_chal_id = ''.join(local_random.choices(string.ascii_lowercase + string.digits, k=20))
    return unique_chal_id


def getRequestAuth():
    service_manager_username=get_config(CONFIG_SERVICE_MANAGER_USERNAME_PROPERTY_NAME)
    service_manager_password=get_config(CONFIG_SERVICE_MANAGER_PASSWORD_PROPERTY_NAME)
    basic = HTTPBasicAuth(service_manager_username, service_manager_password)
    return basic


def load(app):
    app.db.create_all()
    upgrade(plugin_name="private_challenges")
    CHALLENGE_CLASSES["private"] = PrivateValueChallenge
    register_plugin_assets_directory(
        app, base_path=f"/plugins/{PLUGIN_FOLDER_NAME}/assets/"
    )


    @app.route('/api/private_challenge/<serviceName>', methods=['GET', 'POST'])
    @bypass_csrf_protection
    @during_ctf_time_only
    def privateChallengeService(serviceName):
        user = get_current_user()

        if not user or not user.id or not user.team_id:
            return {"message": "not authenticated"}, 401

        NO_SSRF_REGEX = '^[a-z0-9-]+$'
        if not re.match(NO_SSRF_REGEX, serviceName):
            return {"message": "invalid service name"}, 400

        chal_owner_id = user.id
        if get_config('user_mode') == TEAMS_MODE:
            chal_owner_id = user.team_id

        unique_chal_id = get_unique_chal_id(chal_owner_id)

        service_manager_url = get_config(CONFIG_SERVICE_MANAGER_URL_PROPERTY_NAME)
        url = f'{service_manager_url}/service/{serviceName}'

        params = {'unique_chal_id': unique_chal_id}

        if request.method == 'GET':
            res = requests.get(url, auth = getRequestAuth(), params = params)
        else:
            res = requests.post(url, auth = getRequestAuth(), params = params)

        print('res.status_code:', res.status_code)
        print('res.text', res.text)

        try:
            return res.json(), res.status_code
        except:
            return res.text, res.status_code


    @app.route('/admin/private_challenge', methods=['GET', 'POST'])
    @admins_only
    def get_config_page():
        alert = None
        if request.method == 'POST':
            service_manager_url = request.form.get('service_manager_url', '')
            service_manager_username = request.form.get('service_manager_username', '')
            service_manager_password = request.form.get('service_manager_password', '')
            if not isinstance(service_manager_url, str) or not isinstance(service_manager_username, str) or not isinstance(service_manager_password, str):
                alert = {'type': 'danger', 'message': 'Invalid config.'}
            else:
                alert = {
                    'type': 'success',
                    'message': 'Configuration successfully saved!'
                }
                set_config(CONFIG_SERVICE_MANAGER_URL_PROPERTY_NAME, service_manager_url)
                set_config(CONFIG_SERVICE_MANAGER_USERNAME_PROPERTY_NAME, service_manager_username)
                set_config(CONFIG_SERVICE_MANAGER_PASSWORD_PROPERTY_NAME, service_manager_password)

        return render_template(
            f'plugins/{PLUGIN_FOLDER_NAME}/templates/admin.html',
            service_manager_url=get_config(CONFIG_SERVICE_MANAGER_URL_PROPERTY_NAME, ''),
            service_manager_username=get_config(CONFIG_SERVICE_MANAGER_USERNAME_PROPERTY_NAME, ''),
            service_manager_password=get_config(CONFIG_SERVICE_MANAGER_PASSWORD_PROPERTY_NAME, ''),
            alert=alert)
