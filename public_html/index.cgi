#!/usr/local/bin/python3.7
#!/usr/local/bin/python3.7
import cgi
import cgitb
cgitb.enable()
from wsgiref.handlers import CGIHandler
from app import app
class ProxyFix(object):
  def __init__(self, app):
      self.app = app
  def __call__(self, environ, start_response):
      environ['SERVER_NAME'] = "/ninta.main.jp/"
      return self.app(environ, start_response)
if __name__ == '__main__':
   app.wsgi_app = ProxyFix(app.wsgi_app)
   CGIHandler().run(app)