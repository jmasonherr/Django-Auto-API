from django.conf import settings
from django.db import models



try:
    # On App engine
    from google.appengine.api import memcache as cache
    AE = True
except:
    from django.core.cache import cache
    AE = False



def build_routes():
    """ 
        THis method inspects your Django site and creates a dictionary of the models and relationships for the API router and the Javascript model generator.  Saved in memcache for speed
        
        Build a routes dictionary template below
        
        Expects settings to have the following variables:
        
            NAMESPACE - a string that will differentiate your test cache from your production cache
            EXCLUDE_MODELS - list of model names that you DO NOT want included in the API
            EXCLUDE_APPS - list of APPs that should bec excluded from the API
        
    """
#    routes = None
#    if AE:
#        routes = cache.get('api_routes', namespace=settings.NAMESPACE)
#    else:
#        routes = cache.get('api_routes')

    # Return cached version if it exists
#    if routes:
#        return routes

    allmodels = models.get_models()

    # Build a dictionary routes and their nested routes, as shown above
    routes = {}

    # Build a list of model objects and what their name is in the routes dict
    model2name = {}

    # Reverse many to manys
    reversem2m = {}

    # Run through once to de duplicate
    for model in allmodels:

        # Get the name of the model
        modelname =  model.__name__ #.lower()

        # If it has an app name, we want it in the project
        if hasattr(model._meta, 'app_label'):
            app_label = model._meta.app_label #.lower()

            # Check to see if it should be excluded
            if app_label in settings.EXCLUDE_APPS or '%s.%s' % (app_label, modelname) in settings.EXCLUDE_MODELS or modelname in settings.EXCLUDE_MODELS:
                continue

            # If there's a naming conflict, make the new name appname_modelname
            if modelname in model2name:
                modelname = '_'.join(app_label, modelname) #.lower()

            # Add to routes hash
            routes[modelname.lower()] = {
                'upper_modelname': modelname,
                'm2m': {},
                'fks': {},
                'model': model,
                'reverse_fks': {},
                'reverse_m2m': {},
            }

            # Add to model: modelname hash
            model2name[model] = modelname.lower()
            reversem2m[modelname.lower()] = {}

    # Create a repository for stored fields
    reverse_fk = {}
    rfks = {}

    for route, info in routes.iteritems():
        model = info['model']

        # Add Many to many to info hash
        for m2m in model._meta.many_to_many:
            relatedModel = m2m.rel.to
            if relatedModel in model2name:
                info['m2m'][m2m.name] = relatedModel

                # Set up reverse as well
                reversem2m[model2name[relatedModel]][m2m.related_query_name()] = model

        # Add foreign keys to info hash
        for field in model._meta.fields:
            if type(field) == models.ForeignKey:

                relatedModel = field.rel.to
                info['fks'][field.name] = relatedModel

        for ro in model._meta.get_all_related_objects():
            if ro.field.model in model2name:
                info['reverse_fks'][ro.get_accessor_name()] = ro.field.model

    # Add in reverse M2m
    for n, m in reversem2m.iteritems():
        routes[n]['reverse_m2m'] = m
    if AE:
        cache.add('api_routes', routes, 7200, namespace=settings.NAMESPACE)
    else:
        cache.add('api_routes', (routes, model2name), 7200)

    return routes, model2name