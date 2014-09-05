Django-Auto-API
===============

Inspects your django installation and creates an api from the existing models.  If you use in production, you should really audit and modify the security.  Great for prototyping.  

Requires Django-AppEngine conversion to deal with different datatypes
https://github.com/jmasonherr/Django-AppEngine-Conversion

### Features:
- Easy
- Login / CORS Support
- Only JSON
- Fat model design
- Query optimization and serialization optimization
- Control access on level of model and field
- Easy custom endpoints
- Conversion of datatypes
- Allows partial and incomplete data in update/create
- Integrates seamlessly with MicroRelate.js and Backbone.js.  Allows auto-copying and integration of models and collections to front-end apis

### Installation

- Clone into django project
- Add to installed apps
```
INSTALLED_APPS = [
  ...
  # Auto generated API for backbone relational
  'auto_api',
  ...

]
```

- Add necessary settings


```
# settings.py
API_REQUEST_LIMIT = 200 # Maximum items returned ever
API_PAGE_COUNT = 20 # number of items returned per page

URL_PREFIX = 'api' # this will make your models available at yoursite.com/api/modelname/

EXCLUDE_APPS = ['allauth', 'django_evolution'] # Do not include these apps' models in the API

EXCLUDE_MODELS = ['Site', 'Permission', ...] # Do not allow these models access through the API

XS_SHARING_ALLOWED_ORIGINS =  ['*' , 'http://localhost:8001', 'http://mysite.com', 'http://localhost:12080']
XS_SHARING_ALLOWED_METHODS = ['POST','GET','OPTIONS', 'PUT', 'DELETE']
```

- Mixin the UpdateableMixin for any models you want to see.

``` 
from auto_api.models import UpdateableMixin

class Foo(models.Model, UpdateableMixin):
  name = models.CharField(max_length=500)
  secret_key = models.CharField(max_length=500)

```

- Customize any permissions/field access on your models by overloading the methods from UpdateableMixin

```
class Foo(models.Model, UpdateableMixin):
  name = models.CharField(max_length=500)
  secret_key = models.CharField(max_length=500)
  other_model = models.ManyToManyField('otherapp.OtherModel')
  
  exclude_fields = ['secret_key'] # Control which fields to exclude
    
  @classmethod
  def cls_exclude_fields(cls, request):
    """ Should return a list, allows fine grain control of which to exclude based on request/user/etc.. for queries and lists"""
    return cls.exclude_fields

  def get_exclude_fields(self, request=None):
    """ Should return a list, allows fine grain control of which to exclude based on request/user/etc.. for individual models"""
    return self.__class__.exclude_fields

  @classmethod
  def get_related_objs(cls):
    """ Adds list of serialized OtherModels to results"""
    return ['other_model']

  @classmethod
  def get_count_of(cls):
    """ will add field 'other_model__count' on serialization """
    return ['other_model']

  @classmethod
  def has_POST_create_permission(cls, request):
    """ Customize access POST for creation purposes"""
    return request.user.is_superuser




```





