# pip install pymongo
from pymongo import MongoClient
#URL de MongoDB
client = MongoClient("mongodb+srv://grearte:xS8fu8gVPAz9qGWm@cluster0.dffoict.mongodb.net/?retryWrites=true&w=majority")
#Seleccionar o crear la DB
db = client['Estudiantes']
#Seleccionar o crear la colección
datos_estudiantes = db['turista']
