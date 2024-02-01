import os

from flask import Flask
from blueprints.hrms.hrms import hrms
from blueprints.cp.cp import cp
from blueprints.mtop_master.mtop_master import master
from blueprints.login.login import user_controller
from blueprints.cms.cms import cm

secret_key = os.urandom(24)
mtop = Flask(__name__)

mtop.secret_key = secret_key

mtop.register_blueprint(hrms)
mtop.register_blueprint(cp)
mtop.register_blueprint(master)
mtop.register_blueprint(user_controller)
mtop.register_blueprint(cm)

if __name__ == '__main__':
    mtop.run(debug=True)
