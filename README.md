Django-Auto-API
===============

Inspects your django installation and creates an api from the existing models

Requires Django-AppEngine conversion to deal with different datatypes
https://github.com/jmasonherr/Django-AppEngine-Conversion

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
class Foo(models.Model, UpdateableMixin):
  name = models.CharField(max_length=500)
```





