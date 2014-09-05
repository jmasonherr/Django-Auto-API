import os
import json

from django.db import models
from django.conf import settings

from inspector import build_routes


FINAL_MODEL_TEMPLATE = """{model_name} = {base_model}.extend({{
    storeIdentifier: '{model_name}',
    idAttribute: '{id_attribute}',
    urlRoot: '/{url_prefix}/{lower_name}/',
    relations: [
        {relations}
    ]
}});

"""


FINAL_FK_TEMPLATE = """
	{{
		type: '{rel_type}',
		key: '{field_name}',
		relatedModel: '{related_model_name}',
		reverseKey: '{reverse_relation}',
	}},
"""

FINAL_M2M_TEMPLATE = """
    {{
        type: 'many_many',
		relatedModel: '{related_model_name}',
		key: '{field_name}',
        reverseKey: '{reverse_relation}',
    }},
"""

STORE_DEFAULTS   = '''
        DEFAULT_COLL = {base_collection};
        DEFAULT_MODEL = {base_model};

        Backbone.store.registerModels({model_names});

'''

def pr(s):
    """ prevent reserved words from clobbering"""
    if s in settings.RESERVED_WORDS:
        return s + '_'
    return s


def model_js():
    """ Inspects your models, creates a Backbone mirror of them with all relationships"""
    routes, model2name = build_routes()

    modelNames = set()
    fh = open(os.path.join(settings.PARENT_DIR, settings.OUT_LOCATION), 'wb')

    for model, name in model2name.copy().iteritems():
        upper_modelname = routes[name]['upper_modelname']
        relationString = ''

        # Add FKS
        for field in model._meta.fields:
            if type(field) in [models.ForeignKey, models.OneToOneField]:
                if field.rel.to in model2name:
                        rel_type = 'one_one' if type(field) == models.OneToOneField else 'has_one'
                        relationString += FINAL_FK_TEMPLATE.format(
                            rel_type=rel_type,
                            reverse_relation=field.related_query_name(),
                            field_name=field.name,
                            related_model_name=routes[model2name[field.rel.to]]['upper_modelname'],
                        )


        # Add M2M
        for m2m in model._meta.many_to_many:
            if m2m.rel.to in model2name:
                relationString += FINAL_M2M_TEMPLATE.format(
                    field_name=m2m.name,
                    related_model_name=routes[model2name[m2m.rel.to]]['upper_modelname'],
                    reverse_relation=m2m.related_query_name(),
                )

        # Output model
        fh.write(
            FINAL_MODEL_TEMPLATE.format(
                model_name=upper_modelname,
                app_name=model._meta.app_label.lower(),
                base_model=settings.BASE_MODEL,
                url_prefix=settings.URL_PREFIX,
                lower_name=upper_modelname.lower(),
                relations=relationString,
                app_prefix=settings.APP_PREFIX,
                id_attribute=model._meta.pk.name,
            )
        )

        # Add to registry function
        modelNames.add(upper_modelname)

    # Write to file
    fh.write(STORE_DEFAULTS.format(
        model_names=', '.join(modelNames),
        base_model=settings.BASE_MODEL,
        base_collection=settings.BASE_COLLECTION
    ))

    fh.close()





