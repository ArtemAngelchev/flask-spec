# -*- coding: utf-8 -*-
import warnings

from apispec.ext.flask import FlaskPlugin
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec.ext.marshmallow.openapi import (MARSHMALLOW_VERSION_INFO,
                                             OpenAPIConverter)
from apispec.utils import load_yaml_from_docstring
from flask import Blueprint
from marshmallow import Schema, fields as mf


class CustomFlaskPlugin(FlaskPlugin):
    BP_PREFIX = None

    def path_helper(self, view, **kwargs):
        result = super().path_helper(view, **kwargs)
        if self.BP_PREFIX:
            result.path = result.path.replace(self.BP_PREFIX, '')
        return result

    @classmethod
    def trim_bp_prefix(cls, bp_prefix):
        cls.BP_PREFIX = bp_prefix


class CustomOpenAPIConverter(OpenAPIConverter):
    @staticmethod
    def _observed_name(field, name):
        if MARSHMALLOW_VERSION_INFO[0] < 3:
            load_from = getattr(field, 'load_from', None)
            return load_from or name
        return field.data_key or name

    def fields2jsonschema(
            self, fields, schema=None, use_refs=True, dump=True, name=None
    ):
        fields = {
            k: v
            for k, v in fields.items()
            if not (v.dump_only or isinstance(v, (mf.Method, mf.Function)))
        }
        return super().fields2jsonschema(fields, schema, use_refs, dump, name)


class CustomMarshmallowPlugin(MarshmallowPlugin):
    def init_spec(self, spec):
        super().init_spec(spec)
        self.openapi = CustomOpenAPIConverter(
            openapi_version=spec.openapi_version
        )


class SpecBlueprint(Blueprint):
    spec_views = []
    spec_schemas = []

    def route(self, rule, **options):
        has_spec = options.pop('add_to_spec', False)

        def decorator(func):
            endpoint = options.pop("endpoint", func.__name__)
            self.add_url_rule(rule, endpoint, func, **options)
            if has_spec:
                self.spec_views.append({'name': func.__name__, 'func': func})
            return func
        return decorator

    def add_schemas_to_spec(self, schemas):
        for schema in schemas:
            if not (issubclass(schema, Schema) or isinstance(schema, Schema)):
                raise ValueError('')
            schema = schema if issubclass(schema, Schema) else type(schema)
            self._add_schema_to_spec(schema)

    def _add_schema_to_spec(self, schema):
        schema_name = schema.__name__
        data = load_yaml_from_docstring(schema.__doc__) or {}

        missed = set(('name', 'description')) - data.keys()
        if missed:
            for attr in missed:
                data[attr] = schema_name

            missed = ', '.join(f'"{m}"' for m in missed)
            warnings.warn(
                f'For schema <{schema_name}> not provided {missed}.'
                ' Fail to default values.'
                ' Schema class name will be used insted.', RuntimeWarning
            )

        data['schema'] = schema
        self.spec_schemas.append(data)

    @property
    def has_spec(self):
        return len(self.spec_views) > 0
