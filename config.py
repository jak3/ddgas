class Config(object):
    DEBUG = True
    TESTING = False
    SECRET_KEY = 'dev'
    DATABASE_URI = 'delek'

class HerokuConfig(Config):
    DATABASE_URI = 'mysql://user@localhost/foo'

class TestingConfig(Config):
    TESTING = True
