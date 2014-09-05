Django-Auto-API
===============

Inspects your django installation and creates an api from the existing models.  If you use in production, you should really audit and modify the security.  Great for prototyping.  

Requires Django-AppEngine conversion to deal with different datatypes
https://github.com/jmasonherr/Django-AppEngine-Conversion

### Features:
- Easy
- Built in filter/sort like Django ORM
- Automatic type conversions and serialization/deserialization
- Custom endpoints
- DATA attribute added to request object for easy retrieval of data from different request types
- Relationships automatically nested in API
- Login / CORS Support
- Only JSON
- Fat model design
- Query optimization and serialization optimization
- Control access on level of model and field
- Easy custom endpoints
- Conversion of datatypes
- Allows partial and incomplete data in update/create
- Works on AppEngine
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

- Include url in urls.py

```
...
    # API
    url(r'^' + settings.URL_PREFIX + r'/', include('auto_api.urls')),
...

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
    return request.user.is_superuser # Only allow object creation if is superuser

```

That's it!  Foo is now available for GET, POST, PUT, and DELETE

Relationships are available via their ORM names

### Part 2: Filtering, pagination and sorting

AutoApi allows filtering and sorting like the Django ORM

/api/foo/?sort=-name&other_model_id__gte=5

returns all of the Foo objects that are related to OtherModels with an id greater than 5

For simple equality, use __eq at the end of your filter

/api/foo/?name__eq=gonzo

returns a list of all Foo objects named gonzo

Sorting is available via 'sort', pagination via 'page'

The catch: Filtering on complex datatypes like dates and booleans are only available on the immediate model.  Filtering by date will not work across relationships.



### Part 3: Custom endpoints

Forward and reverse relationships are already included. (/api/foo/1/other_model/ ) will return all of the related OtherModel instances if you have the permission to see them

If you want to return custom data, just add a method to the model like so:

```

class Foo(models.Model, UpdateableMixin):
  ...
  
  # GET /foo/1/active_other_models/
  def GET_active_other_models(self, request): # Limited to GET requests
    """ You can return a JSON-ready dictionary or a Query object from these methods """
    return self.other_models.filter(active=True)
    # Equivalent to /api/foo/1/other_models/?active__eq=True

  # POST /foo/1/change_secret_key/?secret_key=asdf
  def POST_change_secret_key(self, request): # Limited to POST requests
    if request.user.is_superuser:
      self.secret_key = request.DATA.get('secret_key')
      self.save()
      return self.toJSON()
```

the format for custom endpoints is :
def METHOD_method_name(self, request):
  pass


#### There are still tons of undocumented features, more coming soon!
