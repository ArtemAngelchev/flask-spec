# -*- coding: utf-8 -*-
import os
import pathlib
import warnings
from collections import OrderedDict
from functools import partialmethod
from urllib.parse import urlparse

import jinja2
import yaml
from apispec import APISpec
from apispec.core import Path
from apispec.lazy_dict import LazyDict
from flask import Response, render_template, send_from_directory
from flask.templating import TemplateNotFound
from markdown2 import markdown_path

from .extensions import CustomFlaskPlugin, CustomMarshmallowPlugin
from .utils import parse_env_file


def represent_dict(dumper, instance):
    return dumper.represent_mapping('tag:yaml.org,2002:map', instance.items())


yaml.add_representer(OrderedDict, represent_dict)
yaml.add_representer(LazyDict, represent_dict)
yaml.add_representer(Path, represent_dict)


class FlaskSpec:
    _plugins = {'flask': None, 'marshmallow': None}
    _drawings_extensions = {'png'}
    _drawings_sources_extensions = {'xml'}

    def __init__(
            self, app, app_name=None, app_url=None, env_file=None,
            env_name=None, drawings_dir='drawings',
            description_template='envs.html', trim_bp_prefix=True,
            schemes=('https',), openapi_version='2.0', basicauth=False,
    ):
        self.app = app
        self.app_name = app_name
        self.app_url = app_url
        self.env_file = env_file
        self.env_name = env_name

        self.trim_bp_prefix = trim_bp_prefix
        self.drawings_dir = drawings_dir
        self.description_template = description_template
        self.schemes = schemes
        self.openapi_version = openapi_version
        self.basicauth = basicauth
        self._cwd = pathlib.Path(os.getcwd())
        self._plugin_root = pathlib.Path(__file__).parents[0]

        self._register_default_template_filters()

    @property
    def app_name(self):
        return self._app_name

    @app_name.setter
    def app_name(self, value):
        value = (
            value or
            self._get_config('SPEC_APP_NAME') or
            self._get_config('APP_NAME')
        )
        if value is None:
            warnings.warn(
                'Application name not specified. Fall back to Falsk app name.'
                ' You can set application name at initialization or add'
                ' "APP_NAME" or "SPEC_APP_NAME" to Flask config or into envs.',
                RuntimeWarning,
            )
        self._app_name = value or self.app.name

    @property
    def app_url(self):
        return self._app_url

    @app_url.setter
    def app_url(self, value):
        value = (
            value or
            self._get_config('SPEC_APP_URL') or
            self._get_config('APP_URL')
        )

        if value is None:
            warnings.warn(
                'Application url not specified.'
                ' You can set application url at initialization or add'
                ' "SPEC_APP_URL" or "APP_URL" to Flask config or into envs.',
                RuntimeWarning,
            )
        self._app_url = value

    @property
    def env_name(self):
        return self._env_name

    @env_name.setter
    def env_name(self, value):
        value = (
            value or
            self._get_config('SPEC_APP_ENV') or
            self._get_config('APP_ENV')
        )
        if value is None:
            warnings.warn(
                'Environment name not specified.'
                ' You can set environment name at initialization or add'
                ' "SPEC_APP_ENV" or "APP_ENV" to Flask config or into envs.',
                RuntimeWarning,
            )
        self._env_name = value

    @property
    def app_apikey(self):
        return (
            self._get_config('SPEC_APP_APIKEY') or
            self._get_config('APP_APIKEY')
        )

    @property
    def env_file_path(self):
        if self.env_file is None:
            env = self.env_name or ''
            env_path = self._cwd / f'.env-{env.lower()}' if env else None
        else:
            env_path = self._cwd / self.env_file
        return env_path

    def _get_openshift_data(self):
        data = {
            'commit': os.getenv('OPENSHIFT_BUILD_COMMIT'),
            'ref':  os.getenv('OPENSHIFT_BUILD_REFERENCE'),
            'repository': os.getenv('OPENSHIFT_BUILD_SOURCE'),
        }
        return data if all(data.values()) else None

    def _get_config(self, config):
        return self.app.config.get(config) or os.getenv(config)

    def _register_default_template_filters(self):
        @self.app.template_filter('filename_to_title')
        def filename_to_title(value):
            value = value.split('.', 1)[0].split('_')
            return ' '.join((value[0].title(), *value[1:]))

        @self.app.template_filter('humanize_required')
        def humanize_required(value):
            if value is None:
                return 'не задано'
            elif int(value):
                return 'обязательно'
            else:
                return 'не обязательно'

        @self.app.context_processor
        def utility_processor():
            def compose_static_url(app_url, filename, apikey=None):
                url = f'{app_url.rstrip("/")}/static/{filename}'
                if apikey:
                    url = f'{url}?apikey={apikey}'
                return url
            return {'compose_static_url': compose_static_url}

    def create_spec_description(self, blueprint):
        blueprint_root = pathlib.Path(blueprint.root_path)
        drawings_folder = blueprint_root / self.drawings_dir

        kwargs = {}

        kwargs['app_url'] = self.app_url
        if self.app_apikey:
            kwargs['app_apikey'] = self.app_apikey

        try:
            kwargs['description'] = markdown_path(self._cwd / 'README.md')
        except FileNotFoundError:
            warnings.warn(
                'Discription not found. Please add README.md to the project',
                RuntimeWarning,
            )

        try:
            kwargs['drawings'] = [
                d for d in os.listdir(drawings_folder)
                if d.rsplit('.')[-1] in self._drawings_extensions
            ]
            kwargs['drawings_sources'] = [
                ds for ds in os.listdir(drawings_folder)
                if ds.rsplit('.')[-1] in self._drawings_sources_extensions
            ]
        except FileNotFoundError:
            warnings.warn(
                'Folder with drawings not found. '
                'Please add folder with drawnings to the path '
                f'<{blueprint_root}>',
                RuntimeWarning,
            )

        try:
            envs = parse_env_file(self.env_file_path)
            if envs:
                kwargs['envs'] = envs
                self._add_custom_static_route(
                    blueprint.url_prefix, drawings_folder
                )
        except (TypeError, FileNotFoundError):
            warnings.warn('Env file not found.' , RuntimeWarning)

        kwargs['openshift'] = self._get_openshift_data()

        try:
            _jinja_loader = self.app.jinja_loader
            jinja_loader = jinja2.ChoiceLoader([
                self.app.jinja_loader,
                jinja2.FileSystemLoader(
                    [
                        blueprint_root / 'templates',
                        self._cwd / 'templates',
                        self._plugin_root / 'templates',
                    ]
                ),
            ])

            self.app.jinja_loader = jinja_loader
            with self.app.test_request_context():
                tmplt = render_template(self.description_template, **kwargs)
            self.app.jinja_loader = _jinja_loader
            return tmplt
        except TemplateNotFound:
            warnings.warn(
                'Template file for description not found.', RuntimeWarning
            )
            return None

    def _add_custom_static_route(self, prefix, static_folder):
        @self.app.route(f'{prefix or ""}/static/<path:filename>')
        def custom_static(filename):
            return send_from_directory(static_folder, filename)

    def register_blueprint(self, blueprint):
        bp_prefix = blueprint.url_prefix or ''

        spec_descr = self.create_spec_description(blueprint)

        if blueprint.has_spec:
            plugins = self._get_plugins(
                bp_prefix if self.trim_bp_prefix else None
            )
            plugins = [p() for p in plugins]
            spec = self.compose_spec(bp_prefix.strip('/'), spec_descr, plugins)

            for view in blueprint.spec_views:
                with self.app.test_request_context():
                    spec.add_path(view=view['func'], blueprint=blueprint.name)

            for schema in blueprint.spec_schemas:
                spec.definition(**schema)

            @self.app.route(f'{bp_prefix}/swagger', methods=['GET'])
            def swagger():
                data = spec.to_dict()
                info = data.pop('info')
                yml_spec = yaml.dump(data, allow_unicode=True)
                desc = info.get("description", ' ').replace("\n", "")
                yml_spec = (
                    'info:\n'
                    f'  title: {info["title"]}\n'
                    f'  version: {info["version"]}\n'
                    f'  description:\n      {desc}\n'
                    f'{yml_spec}'
                )
                return Response(yml_spec, mimetype='text/yaml')

    def compose_spec(self, bp_version, description=None, plugins=None):
        if self.app_url:
            app_url = urlparse(self.app_url)
            app_url = {'host': app_url.hostname, 'basePath': app_url.path}
        else:
            app_url = {}

        title = self.app_name.title().replace('_', ' ')
        if self.env_name:
            title = f'{title} ({self.env_name})'

        if self.basicauth:
            settings = {
                'securityDefinitions': {
                    'basic_auth': {
                        'type': 'basic',
                    },
                },
            }
        else:
            settings = {}

        if self.app_apikey:
            if not settings:
                settings = {'securityDefinitions': {}}
            security = settings['securityDefinitions']
            security['apikey'] = {
                'type': 'apiKey',
                'in': 'query',
                'name': 'apikey',
                'description': f'apikey {self.app_apikey}'
            }
            settings['security'] = [{'apikey': []}]

        info = {'info': {'description': description}} if description else {}

        spec = APISpec(
            schemes=list(self.schemes),
            title=title,
            version=bp_version or 'v1',
            openapi_version=self.openapi_version,
            plugins=[*plugins],
            **app_url,
            **info,
            **settings,
        )
        return spec

    def _get_plugins(self, trim_prfix=None):
        fplugin = self._plugins['flask']
        mplugin = self._plugins['marshmallow']
        if fplugin is None:
            fplugin = CustomFlaskPlugin
            if trim_prfix:
                fplugin.trim_bp_prefix(trim_prfix)
        if mplugin is None:
            mplugin = CustomMarshmallowPlugin
        return fplugin, mplugin

    def _set_plugin(self, plugin, plugin_name):
        self._plugins[plugin_name] = plugin

    set_flask_plugin = partialmethod(_set_plugin, plugin_name='flask')
    set_marshmallow_plugin = partialmethod(
        _set_plugin, plugin_name='marshmallow'
    )
