import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/'
    DB_NAME = os.environ.get('DB_NAME') or 'dynamic_crud_db'
