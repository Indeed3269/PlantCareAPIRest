import os
from os.path import abspath, dirname, join

basedir = abspath(dirname(dirname(__file__)))

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{join(basedir, "app.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False