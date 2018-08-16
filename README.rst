=============
flask-spec
=============


Install
-------

::

    pip install flask-spec

Quickstart
----------

::

    from flask import Flask, Blueprint
    from flask_spec import FlaskSpec, SpecBlueprint

    app = Flask(__name__)
    spec = FlaskSpec(app)
