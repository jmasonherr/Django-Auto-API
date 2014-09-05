import re
import json
from conversion.conversionmap import conversionmap as cm



def build_filters(obj, data):
    """ Given a query, instance or model, and a dictionary like object of data passed through the request, build query filters and return a dictionary of filters and values.  Can figure out dates, times, and other special types on the IMMEDIATE model, but NOT on any reeached through double underscore ex: book__publisher__established
    
        Expects equality filters to have __eq appended like django uses __gte, __in, etc...
       """
    if not hasattr(obj, '_meta') and hasattr(obj, 'model'):
        obj = obj.model
    fc = dict([(x.name, x) for x in obj._meta.fields])
    filters = {}
    for k, v in data.iteritems():
        if '__' in k:
            try:
                v = json.loads(v)
            except:
                pass

            cleanKey = re.sub('__\w+$', '', k)
            if cleanKey in fc:
                filters[k.replace('__eq', '')] = cm[type(fc[cleanKey])]['fromRequest'](v)
            else:
                filters[k.replace('__eq', '')] = v
    return filters

